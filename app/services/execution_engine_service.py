# app/services/execution_engine_service.py
from __future__ import annotations

import json, re, logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING, TypedDict
from uuid import UUID

from langgraph.graph import StateGraph, START, END

from app.utils.text import format_database_tables, format_query_results

if TYPE_CHECKING:                       # evita import cíclicos en tiempo real
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class ExecutionEngineService:
    def __init__(self, factory: "ServiceFactory") -> None:
        self.factory = factory
        self.user_id: UUID = factory.user.id
        self.history_service = factory.get_chat_history_service()

    # ────────────────────────────────────────────────────────────────
    #   PÚBLICO · Entry-point
    # ────────────────────────────────────────────────────────────────
    def run(
        self,
        plan: Dict[str, Any],
        chat_id: UUID,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        logger.info("[ExecutionEngine] 🚀 Ejecutando plan…")

        actions: List[Dict[str, Any]] = plan.get("actions", [])
        if not actions:
            logger.warning("[ExecutionEngine] Plan sin acciones → nada que ejecutar")
            return {
                "assistant_response": plan.get("assistant_response", ""),
                "variables": {},
            }

        ctx = ctx or {}
        variables = ctx.copy()

        # 🔧 FIX: Ejecutar acciones secuencialmente en lugar de usar StateGraph
        logger.info(f"[ExecutionEngine] 🎯 Ejecutando {len(actions)} acciones secuencialmente")
        
        for idx, action in enumerate(actions, start=1):
            logger.info(f"[ExecutionEngine] ▶️ Ejecutando acción {idx}/{len(actions)}: {action['type']}")
            
            # 🛡️ Aplicar guardrails SQL si es query de BD
            if action['type'] == 'db_query':
                action = self._apply_sql_guardrails(action, variables)
            
            # 🛡️ NUEVO: Aplicar guardrails de formato para chat
            if action['type'] == 'db_query':
                action = self._apply_chat_format_guardrails(action, variables)
            
            try:
                if action["type"] == "db_query":
                    # Verificar si guardrails bloquearon la query
                    if action.get('_guardrails_error'):
                        warnings = action.get('_guardrails_warnings', [])
                        error_msg = "Query bloqueada por guardrails de seguridad:\n" + "\n".join(warnings)
                        logger.error(f"[ExecutionEngine] 🚫 {error_msg}")
                        result = {"error": error_msg, "blocked_by_guardrails": True}
                    else:
                        result = self._run_db_query(action, variables)
                elif action["type"] == "api_function":
                    result = self._run_api_function(action, variables, chat_id)
                elif action["type"] == "mcp_tool":
                    result = self._run_mcp_tool(action, variables)
                else:
                    raise ValueError(f"Tipo de acción desconocido: {action['type']}")

                key = action.get("store_as") or f"result_{len(variables)}"
                variables[key] = result
                logger.info(f"[ExecutionEngine] ✅ Resultado guardado en '{key}'")

                # 👉 Extras normalizados para plantillas: {{key_list}} y {{key_pretty}}
                extras = self._normalize_extras(result)
                for suffix, value in extras.items():
                    variables[f"{key}_{suffix}"] = value

            except Exception as e:
                logger.exception(f"[ExecutionEngine] ❌ Error en acción {idx}: {e}")
                error_key = f"error_{action['type']}_{idx}"
                variables[error_key] = str(e)
                
                # Si es la primera acción, continuar; si no, parar la ejecución
                if idx > 1:
                    logger.warning(f"[ExecutionEngine] ⚠️ Parando ejecución debido a error en acción {idx}")
                    break

        # 🔧 NUEVO: Resolver placeholders faltantes antes del renderizado
        variables = self._resolve_missing_placeholders(variables, plan.get("assistant_response", ""))

        # 3) ────── Render final de assistant_response ──────
        assistant_resp = self._render_text(
            plan.get("assistant_response", ""),
            variables,
        )

        logger.info("[ExecutionEngine] ✅ Plan ejecutado y respuesta renderizada")
        return {
            "assistant_response": assistant_resp,
            "variables": variables,
        }

    # ────────────────────────────────────────────────────────────────
    #   HANDLERS INDIVIDUALES
    # ────────────────────────────────────────────────────────────────
    # … dentro de class ExecutionEngineService …

    def _run_db_query(self, action: Dict[str, Any], ctx: Dict[str, Any]):
        # 1) Resolver database_id (igual que ya lo tienes)
        db_id = action.get("database_id")
        if not db_id:
            ctx_db_ids = (ctx.get("db_ids") or []) if isinstance(ctx.get("db_ids"), list) else []
            if len(ctx_db_ids) == 1:
                db_id = ctx_db_ids[0]
            else:
                raise ValueError("Acción db_query sin 'database_id' y no se puede inferir uno único")

        # 2) Dialecto
        db_service = self.factory.get_database_service()
        dialect = (db_service.get_dialect_name(db_id) or "").lower()

        # 3) Conexión (directa; si tienes proxy, mantén tu lógica de proxy)
        proxy_cfg = None
        if action.get("proxy_id"):
            proxy_cfg = self.factory.get_proxy_service().get_sql_config(action["proxy_id"])
            logger.warning("[ExecutionEngine] Proxy SQL no soportado en DatabaseService.get_sql_instance; usando conexión directa")

        db_conn = db_service.get_sql_instance(db_id)

        # 4) Ejecutar por SQL directo o pregunta NL → pero reescribiendo si hace falta
        if sql := action.get("sql"):
            rendered_sql = self._render_text(sql, ctx)
            fixed_sql = self._rewrite_sql_for_dialect(rendered_sql, dialect)
            try:
                raw_result = db_service.execute_sql(db_conn, fixed_sql)
                
                # 🔧 NUEVO: Aplicar formateo automático para chat
                formatted_result = self._format_result_for_chat(raw_result, "db_query")
                
                # 🔧 NUEVO: Agregar metadata de guardrails si se aplicaron
                if action.get('_chat_guardrails_applied'):
                    formatted_result['_guardrails_info'] = action['_chat_guardrails_applied']
                
                return formatted_result
            except Exception as e:
                logger.error(f"[ExecutionEngine] ❌ Error ejecutando SQL: {e}")
                error_msg = str(e).lower()
                
                # 🔄 NUEVO: Detectar errores de drift de esquema y activar refresh
                if self._is_schema_drift_error(error_msg):
                    logger.warning(f"[ExecutionEngine] 🔄 Detectado posible drift de esquema, intentando refresh del cache")
                    
                    # Intentar refresh del cache y reintentar UNA vez
                    if not ctx.get('_cache_refreshed'):  # Evitar loops infinitos
                        refresh_success = self._refresh_schema_cache(db_id)
                        if refresh_success:
                            ctx['_cache_refreshed'] = True  # Marcar que ya se hizo refresh
                            logger.info(f"[ExecutionEngine] ♻️ Cache refrescado, reintentando query...")
                            try:
                                return db_service.execute_sql(db_conn, fixed_sql)
                            except Exception as retry_error:
                                logger.error(f"[ExecutionEngine] ❌ Error después del refresh: {retry_error}")
                                # Continuar con el manejo normal de errores
                                pass
                
                # Manejo original de errores de columnas
                if "column" in error_msg and ("does not exist" in error_msg or "undefined" in error_msg):
                    logger.info("[ExecutionEngine] 🔍 Intentando obtener información de la tabla...")
                    # Extraer nombre de tabla del error o SQL
                    table_name = self._extract_table_name_from_error(str(e), fixed_sql)
                    if table_name:
                        try:
                            # Obtener estructura de la tabla
                            schema_sql = self._get_table_schema_sql(table_name, dialect)
                            schema_result = db_service.execute_sql(db_conn, schema_sql)
                            
                            # Extraer columnas disponibles del resultado
                            available_columns = []
                            if isinstance(schema_result, list):
                                for row in schema_result:
                                    if isinstance(row, dict) and 'column_name' in row:
                                        available_columns.append(row['column_name'])
                                    elif isinstance(row, (list, tuple)) and len(row) > 0:
                                        available_columns.append(str(row[0]))
                            
                            # 🔧 FIX: Detectar columnas específicas que podrían ser alternativas
                            suggested_columns = []
                            if "location" in fixed_sql.lower() and "address" in available_columns:
                                suggested_columns.append("address")
                            if "city" in fixed_sql.lower() and "address" in available_columns:
                                suggested_columns.append("address")
                            if "description" in available_columns:
                                suggested_columns.append("description")
                            
                            error_message = f"❌ Error: Columna no encontrada en la tabla '{table_name}'.\n"
                            error_message += f"📋 Columnas disponibles: {', '.join(available_columns) if available_columns else 'No se pudieron obtener'}\n"
                            if suggested_columns:
                                error_message += f"💡 Columnas sugeridas para búsquedas: {', '.join(suggested_columns)}\n"
                            error_message += f"🔍 SQL que causó el error: {fixed_sql}\n"
                            error_message += f"💡 Sugerencia: Usa LIKE '%valor%' en lugar de = 'valor' para búsquedas flexibles"
                            
                            return {
                                "error": error_message,
                                "original_error": str(e),
                                "available_columns": available_columns,
                                "table_name": table_name,
                                "failed_sql": fixed_sql,
                                "suggested_columns": suggested_columns
                            }
                        except Exception as schema_error:
                            logger.error(f"[ExecutionEngine] ❌ Error obteniendo schema: {schema_error}")
                            return {
                                "error": f"❌ Error ejecutando consulta: {str(e)}\n💡 No se pudo obtener la estructura de la tabla para ayudarte.",
                                "original_error": str(e)
                            }
                    else:
                        return {
                            "error": f"❌ Error ejecutando consulta: {str(e)}\n💡 No se pudo identificar la tabla en el error.",
                            "original_error": str(e)
                        }
                
                # Si hay error de tabla que no existe
                elif "relation" in error_msg and "does not exist" in error_msg:
                    logger.info("[ExecutionEngine] 🔍 Tabla no encontrada...")
                    error_message = f"❌ Error: La tabla no existe en la base de datos.\n"
                    error_message += f"🔍 SQL que causó el error: {fixed_sql}\n"
                    error_message += f"💡 Sugerencia: Verifica que la tabla existe o usa una consulta diferente."
                    
                    return {
                        "error": error_message,
                        "original_error": str(e),
                        "failed_sql": fixed_sql,
                        "suggestion": "table_not_found"
                    }
                
                # Si no se encuentran resultados, sugerir búsquedas más flexibles
                elif "no rows" in error_msg or "empty result" in error_msg or "0 rows" in error_msg:
                    logger.info("[ExecutionEngine] 🔍 No se encontraron resultados, sugiriendo búsquedas flexibles...")
                    
                    # Extraer información del SQL para sugerir mejoras
                    suggestions = []
                    if "WHERE" in fixed_sql.upper():
                        if "=" in fixed_sql and "LIKE" not in fixed_sql.upper():
                            suggestions.append("💡 Sugerencia: Usa LIKE '%valor%' en lugar de = 'valor' para búsquedas más flexibles")
                        if "ILIKE" not in fixed_sql.upper() and "postgresql" in dialect.lower():
                            suggestions.append("💡 Sugerencia: Usa ILIKE para búsquedas case-insensitive en PostgreSQL")
                    
                    error_message = f"🔍 No se encontraron resultados con la consulta actual.\n"
                    error_message += f"🔍 SQL ejecutado: {fixed_sql}\n"
                    if suggestions:
                        error_message += "\n".join(suggestions)
                    error_message += f"\n💡 Intenta con búsquedas más flexibles usando LIKE o ILIKE"
                    
                    return {
                        "error": error_message,
                        "original_error": str(e),
                        "failed_sql": fixed_sql,
                        "suggestion": "use_flexible_search"
                    }
                else:
                    # Para otros tipos de errores, devolver el error directamente
                    return {
                        "error": f"❌ Error ejecutando consulta: {str(e)}",
                        "original_error": str(e)
                    }

        if question := action.get("question"):
            rendered_q = self._render_text(question, ctx)
            # Obtener el DatabaseConnection para pasar a ask_database_question
            db_record = db_service.get_record(db_id)
            return self.factory.get_langchain_service().ask_database_question(db_record, rendered_q)

        raise ValueError("Acción db_query sin 'sql' ni 'question'")


    def _run_api_function(self, action: Dict[str, Any], ctx: Dict[str, Any], chat_id: UUID):
        self.factory.get_usage_service().check_limit()
        params = self._render_params(action.get("params", {}), ctx)

        proxy = None
        if action.get("proxy_id"):
            proxy = self.factory.get_proxy_service().get_http_config(action["proxy_id"])

        result, tokens_used, call_id = self.factory.get_executor_service().execute_and_log(
            function_id=action["function_id"],
            params=params,
            proxy=proxy,
        )

        # Registrar en historial como función
        self.history_service.create_message({
            "chat_id": chat_id,
            "user_id": self.user_id,
            "role": "function",
            "content": str(result),
            "name": action.get("tool_name") or "api_function",
            "token_count": tokens_used,
            "is_function_call": True,
            "function_call_id": call_id,
        })
        return result

    def _run_mcp_tool(self, action: Dict[str, Any], ctx: Dict[str, Any]):
        params = self._render_params(action.get("params", {}), ctx)

        proxy = None
        if action.get("proxy_id"):
            proxy = self.factory.get_proxy_service().get_http_config(action["proxy_id"])

        return self.factory.get_mcp_integration_service().execute(
            action["tool_name"], params, proxy
        )

    # ────────────────────────────────────────────────────────────────
    #   HELPERS
    # ────────────────────────────────────────────────────────────────
    @staticmethod
    def _has_dependency(action: Dict[str, Any]) -> bool:
        return bool(re.findall(r"\{\{(.*?)\}\}", json.dumps(action)))

    @staticmethod
    def _render_text(template: str, variables: Dict[str, Any]) -> str:
        """
        Sustituye {{variable}} y (de forma tolerante) {variable}
        por str(variables[variable]) si existe.
        
        🔧 NUEVO: Valida que no queden placeholders sin resolver
        """
        # 1) {{var}}
        def repl_double(m):
            key = m.group(1).strip()
            if key in variables:
                return str(variables[key])
            else:
                # 🔧 NUEVO: Log de placeholder no resuelto
                logger.warning(f"[ExecutionEngine] 🚫 Placeholder no resuelto en renderizado: {{{{key}}}}")
                return f"{{{{{key}}}}}"
        
        out = re.sub(r"\{\{(.*?)\}\}", repl_double, template)

        # 2) {var}  -> solo identificadores simples para evitar romper JSON/SQL
        def repl_single(m):
            key = m.group(1)
            if key in variables:
                return str(variables[key])
            else:
                # 🔧 NUEVO: Log de placeholder no resuelto
                logger.warning(f"[ExecutionEngine] 🚫 Placeholder no resuelto en renderizado: {key}")
                return m.group(0)
        
        out = re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", repl_single, out)

        # 🔧 NUEVO: Validación final - verificar si quedan placeholders
        remaining_placeholders = re.findall(r'\{\{([^}]+)\}\}', out)
        if remaining_placeholders:
            logger.error(f"[ExecutionEngine] 🚫 Placeholders sin resolver después del renderizado: {remaining_placeholders}")
            # 🔧 NUEVO: Reemplazar con mensaje de error controlado
            out = re.sub(r'\{\{[^}]+\}\}', "[VARIABLE NO DISPONIBLE]", out)
            out += "\n\n⚠️ *Algunas variables no pudieron ser resueltas en la respuesta.*"

        return out

    def _render_params(self, params: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {k: self._render_text(str(v), ctx) if isinstance(v, str) else v for k, v in params.items()}

    @staticmethod
    def _rewrite_sql_for_dialect(sql: str, dialect: str) -> str:
        s = sql.strip().lower()

        # SHOW TABLES
        if s.startswith("show tables"):
            if dialect in ("postgresql", "postgres", "pg"):
                return (
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema NOT IN ('pg_catalog','information_schema');"
                )
            if dialect in ("sqlite",):
                return "SELECT name AS table_name FROM sqlite_master WHERE type='table';"
            if dialect in ("mssql", "sqlserver"):
                return "SELECT name AS table_name FROM sys.tables;"
            # mysql sí soporta SHOW TABLES → no tocar

        # DESCRIBE <table>
        m = re.match(r"^describe\s+([a-z0-9_\.]+)\s*;?$", s, re.IGNORECASE)
        if m:
            tbl = m.group(1)
            if dialect in ("postgresql", "postgres", "pg"):
                return (
                    "SELECT column_name, data_type, is_nullable "
                    f"FROM information_schema.columns WHERE table_name = '{tbl}';"
                )
            if dialect in ("sqlite",):
                return f"PRAGMA table_info('{tbl}');"
            if dialect in ("mssql", "sqlserver"):
                return (
                    "SELECT c.name AS column_name, t.Name AS data_type, c.is_nullable "
                    "FROM sys.columns c "
                    "INNER JOIN sys.types t ON c.user_type_id = t.user_type_id "
                    f"WHERE c.object_id = OBJECT_ID('{tbl}');"
                )
            # mysql soporta DESCRIBE → no tocar

        # Por defecto, devolver tal cual
        return sql
    
    def _normalize_extras(self, result):
        """
        Si result es una lista de filas (tuplas o dicts), genera:
        - list: lista simple de valores (si son de 1 columna o dict de 1 clave)
        - pretty: string bonito con comas
        - formatted: versión formateada para mostrar al usuario
        """
        items = []
        if isinstance(result, list):
            for r in result:
                if isinstance(r, tuple) or isinstance(r, list):
                    items.append(r[0] if len(r) == 1 else str(r))
                elif isinstance(r, dict):
                    if "table_name" in r:
                        items.append(r["table_name"])
                    elif len(r) == 1:
                        items.append(next(iter(r.values())))
                    else:
                        items.append(str(r))
                else:
                    items.append(str(r))
        else:
            return {}

        pretty = ", ".join(map(str, items)) if items else ""
        
        # Generar versión formateada
        formatted = format_database_tables(items) if items else ""
        
        return {
            "list": items, 
            "pretty": pretty,
            "formatted": formatted
        }

    def _extract_table_name_from_error(self, error_msg: str, sql: str) -> Optional[str]:
        """Extrae el nombre de la tabla del error o SQL"""
        import re
        
        # Buscar en el error
        table_match = re.search(r'FROM\s+(\w+)', sql, re.IGNORECASE)
        if table_match:
            return table_match.group(1)
        
        # Buscar en el error message
        table_match = re.search(r'table\s+(\w+)', error_msg, re.IGNORECASE)
        if table_match:
            return table_match.group(1)
        
        return None

    def _get_table_schema_sql(self, table_name: str, dialect: str) -> str:
        """Genera SQL para obtener la estructura de una tabla"""
        if dialect in ("postgresql", "postgres", "pg"):
            return f"""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position;
            """
        elif dialect in ("mysql", "mariadb"):
            return f"DESCRIBE {table_name};"
        elif dialect in ("sqlite",):
            return f"PRAGMA table_info('{table_name}');"
        else:
            return f"SELECT * FROM {table_name} LIMIT 0;"
    
    # =====================================================
    # GUARDRAILS SQL
    # =====================================================
    
    def _apply_sql_guardrails(self, action: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aplica guardrails SQL a una acción de query.
        
        Args:
            action: Acción de tipo db_query
            variables: Variables del contexto
            
        Returns:
            Acción modificada con query validada/corregida
        """
        try:
            from app.services.sql_guardrails_service import SQLGuardrailsService
            
            guardrails = SQLGuardrailsService(self.factory)
            
            original_query = action.get('sql', '')
            db_id = action.get('database_id')
            
            if not original_query or not db_id:
                logger.warning("[ExecutionEngine] 🛡️ Acción sin sql o database_id - saltando guardrails")
                return action
            
            # Validar y corregir query
            fixed_query, warnings, is_safe = guardrails.validate_and_fix_query(
                query=original_query,
                user_id=self.user_id,
                db_id=db_id,  # 🔧 Siempre UUID ahora
                context=variables
            )
            
            # Log de guardrails
            if warnings:
                logger.info(f"[ExecutionEngine] 🛡️ Guardrails aplicados - {len(warnings)} warnings:")
                for warning in warnings:
                    logger.info(f"  {warning}")
            
            if not is_safe:
                logger.error("[ExecutionEngine] 🚫 Query marcada como no segura por guardrails")
                # En lugar de ejecutar, devolver error
                action_copy = action.copy()
                action_copy['_guardrails_error'] = True
                action_copy['_guardrails_warnings'] = warnings
                return action_copy
            
            # Actualizar query si fue modificada
            if fixed_query != original_query:
                logger.info("[ExecutionEngine] 🔧 Query corregida por guardrails")
                action_copy = action.copy()
                action_copy['sql'] = fixed_query
                action_copy['_original_sql'] = original_query
                action_copy['_guardrails_applied'] = True
                action_copy['_guardrails_warnings'] = warnings
                return action_copy
            
            # Query no modificada pero validada
            if warnings:
                action_copy = action.copy()
                action_copy['_guardrails_warnings'] = warnings
                return action_copy
            
            return action
            
        except Exception as e:
            logger.exception(f"[ExecutionEngine] ❌ Error aplicando guardrails: {e}")
            # En caso de error, devolver acción original pero con advertencia
            action_copy = action.copy()
            action_copy['_guardrails_error'] = True
            action_copy['_guardrails_warnings'] = [f"❌ Error en guardrails: {str(e)}"]
            return action_copy
    
    # ────────────────────────────────────────────────────────────────
    #   RECUPERACIÓN DE ERRORES CON CACHE REFRESH
    # ────────────────────────────────────────────────────────────────
    def _is_schema_drift_error(self, error_msg: str) -> bool:
        """Detecta si un error podría ser causado por drift de esquema"""
        drift_indicators = [
            "relation does not exist",
            "table does not exist", 
            "column does not exist",
            "undefined table",
            "undefined column",
            "no such table",
            "no such column",
            "unknown column",
            "unknown table",
            "invalid column name",
            "invalid table name"
        ]
        
        error_lower = error_msg.lower()
        return any(indicator in error_lower for indicator in drift_indicators)
    
    def _refresh_schema_cache(self, db_id: UUID) -> bool:
        """
        Refresca el cache de esquema para una base de datos específica.
        Retorna True si el refresh fue exitoso.
        """
        try:
            logger.info(f"[ExecutionEngine] 🔄 Refrescando cache de esquema para DB {db_id}")
            
            # Invalidar cache existente
            cache_service = self.factory.get_detailed_schema_cache_service()
            cache_service.invalidate_cache(self.user_id, db_id)
            
            # Generar nuevo cache
            # Usamos el mismo método que usa el orchestrator para generar schemas
            from app.models.detailed_schema_cache_model import SchemaSnapshot, EnrichmentLevel
            
            # Introspección directa usando DatabaseService
            database_service = self.factory.get_database_service()
            sql_instance = database_service.get_sql_instance(db_id)
            
            if not sql_instance:
                logger.error(f"[ExecutionEngine] ❌ No se pudo obtener instancia SQL para DB {db_id}")
                return False
            
            # Query para obtener información de tablas y columnas
            tables_query = """
                SELECT table_name, column_name, data_type, is_nullable, column_default 
                FROM information_schema.columns 
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
            """
            
            # Usar el engine directamente para obtener resultados estructurados
            from sqlalchemy import text
            if hasattr(sql_instance, '_engine'):
                engine = sql_instance._engine
                
                with engine.connect() as conn:
                    result = conn.execute(text(tables_query))
                    rows = [dict(row._mapping) for row in result]
                    
                    # Procesar filas en estructura de tablas
                    tables = {}
                    for row in rows:
                        table_name = row['table_name']
                        column_name = row['column_name']
                        data_type = row['data_type']
                        is_nullable = row['is_nullable']
                        column_default = row['column_default']
                        
                        if table_name not in tables:
                            tables[table_name] = {
                                'columns': {},
                                'primary_keys': [],
                                'foreign_keys': [],
                                'indexes': []
                            }
                        
                        tables[table_name]['columns'][column_name] = {
                            'type': data_type,
                            'nullable': is_nullable == 'YES',
                            'default': column_default,
                            'primary_key': False
                        }
                    
                    if tables:
                        # Crear snapshot y actualizar cache
                        dialect = database_service.get_dialect_name(db_id) or 'postgresql'
                        snapshot = SchemaSnapshot(
                            tables=tables,
                            enrichment_level=EnrichmentLevel.BASIC,
                            dialect=dialect,
                            generated_at=datetime.now(timezone.utc)
                        )
                        
                        cache_entry = cache_service.create_or_update_cache(
                            user_id=self.user_id,
                            db_id=db_id,
                            snapshot=snapshot,
                            enrichment_level=EnrichmentLevel.BASIC
                        )
                        
                        if cache_entry:
                            logger.info(f"[ExecutionEngine] ✅ Cache refrescado exitosamente para DB {db_id}: {len(tables)} tablas")
                            return True
                        else:
                            logger.error(f"[ExecutionEngine] ❌ Error creando entrada de cache para DB {db_id}")
                            return False
                    else:
                        logger.warning(f"[ExecutionEngine] ⚠️ No se encontraron tablas en DB {db_id}")
                        return False
            else:
                logger.error(f"[ExecutionEngine] ❌ No se pudo acceder al engine para DB {db_id}")
                return False
                
        except Exception as e:
            logger.exception(f"[ExecutionEngine] ❌ Error refrescando cache para DB {db_id}: {e}")
            return False

    # ────────────────────────────────────────────────────────────────
    #   NUEVO: Resolución de placeholders faltantes
    # ────────────────────────────────────────────────────────────────
    def _resolve_missing_placeholders(self, variables: Dict[str, Any], template: str) -> Dict[str, Any]:
        """
        Resuelve placeholders faltantes en la plantilla:
        1. Detecta todos los placeholders {{...}}
        2. Genera automáticamente variables *_formatted faltantes
        3. Registra telemetría de placeholders faltantes
        """
        if not template:
            return variables

        # Extraer todos los placeholders del template
        placeholders = re.findall(r'\{\{([^}]+)\}\}', template)
        logger.info(f"[ExecutionEngine] 🔍 Detectados {len(placeholders)} placeholders en template")

        missing_placeholders = []
        auto_generated = []
        blocked_placeholders = []

        for placeholder in placeholders:
            placeholder = placeholder.strip()
            
            # Si ya existe la variable, está bien
            if placeholder in variables:
                logger.debug(f"[ExecutionEngine] ✅ Placeholder '{placeholder}' ya resuelto")
                continue

            # Si termina en _formatted, intentar generar automáticamente
            if placeholder.endswith('_formatted'):
                base_var = placeholder[:-10]  # Remover '_formatted'
                if base_var in variables:
                    formatted_value = self._auto_format_variable(base_var, variables[base_var])
                    variables[placeholder] = formatted_value
                    auto_generated.append(placeholder)
                    logger.info(f"[ExecutionEngine] 🔧 Auto-generado '{placeholder}' para '{base_var}'")
                    continue
                else:
                    missing_placeholders.append(placeholder)
                    logger.warning(f"[ExecutionEngine] ⚠️ Placeholder '{placeholder}' requiere '{base_var}' que no existe")
                    continue

            # Si no existe de ninguna forma, es un placeholder faltante
            missing_placeholders.append(placeholder)
            logger.warning(f"[ExecutionEngine] ❌ Placeholder '{placeholder}' no existe en variables")

        # Telemetría y logging
        if missing_placeholders:
            logger.warning(f"[ExecutionEngine] 🚫 Placeholders faltantes: {missing_placeholders}")
            # Registrar evento de telemetría si está disponible
            try:
                telemetry = self.factory.get_telemetry_service()
                telemetry.record_event(
                    event_type="missing_placeholders_detected",
                    user_id=self.user_id,
                    metadata={
                        "missing_placeholders": missing_placeholders,
                        "auto_generated": auto_generated,
                        "template_length": len(template),
                        "variables_count": len(variables)
                    }
                )
            except Exception as e:
                logger.debug(f"[ExecutionEngine] No se pudo registrar telemetría: {e}")

        if auto_generated:
            logger.info(f"[ExecutionEngine] ✅ Placeholders auto-generados: {auto_generated}")

        return variables

    def _auto_format_variable(self, var_name: str, value: Any) -> str:
        """
        Genera automáticamente una versión formateada de una variable.
        Aplica formateo inteligente basado en el tipo de dato.
        """
        try:
            if isinstance(value, list):
                if not value:
                    return "No hay datos disponibles"
                
                # Si es lista homogénea, crear tabla Markdown
                if len(value) <= 20:
                    return self._format_list_as_table(value)
                else:
                    # Truncar y mostrar contador
                    truncated = value[:20]
                    table = self._format_list_as_table(truncated)
                    return f"{table}\n\n*+{len(value) - 20} elementos más*"
            
            elif isinstance(value, dict):
                # Pretty-print JSON compacto
                return json.dumps(value, indent=2, ensure_ascii=False, default=str)
            
            elif isinstance(value, (str, int, float, bool)):
                return str(value)
            
            else:
                # Para otros tipos, usar representación string
                return str(value)
                
        except Exception as e:
            logger.warning(f"[ExecutionEngine] ⚠️ Error auto-formateando '{var_name}': {e}")
            return str(value)

    def _format_list_as_table(self, items: List[Any]) -> str:
        """
        Formatea una lista como tabla Markdown.
        Detecta automáticamente si es lista de dicts o valores simples.
        """
        if not items:
            return "No hay datos"
        
        # Si es lista de dicts, crear tabla con columnas
        if isinstance(items[0], dict):
            if not items[0]:
                return "Datos vacíos"
            
            # Obtener todas las claves únicas
            all_keys = set()
            for item in items:
                if isinstance(item, dict):
                    all_keys.update(item.keys())
            
            if not all_keys:
                return "Datos sin estructura"
            
            # Crear tabla Markdown
            keys_list = sorted(all_keys)
            table = "| " + " | ".join(keys_list) + " |\n"
            table += "|" + "|".join(["---"] * len(keys_list)) + "|\n"
            
            for item in items:
                if isinstance(item, dict):
                    row = []
                    for key in keys_list:
                        value = item.get(key, "")
                        # Truncar valores muy largos
                        if isinstance(value, str) and len(value) > 50:
                            value = value[:47] + "..."
                        row.append(str(value))
                    table += "| " + " | ".join(row) + " |\n"
            
            return table
        
        else:
            # Lista simple de valores
            return "\n".join([f"• {item}" for item in items])

    def _apply_chat_format_guardrails(self, action: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if action.get('type') != 'db_query':
                return action

            # si guardrails SQL ya marcó error, no tocar
            if action.get('_guardrails_error'):
                return action

            original_sql = action.get('sql')
            # si no hay SQL (modo NL2SQL por 'question'), no aplicamos guardrails de chat
            if not original_sql or not isinstance(original_sql, str) or not original_sql.strip():
                logger.debug("[ExecutionEngine] chat guardrails: no 'sql' present (NL2SQL flow) -> skip")
                return action

            sql_upper = original_sql.upper()

            # bloquear SELECT * (pero permitir COUNT(*))
            if re.search(r'\bSELECT\s+\*\b', sql_upper) and 'COUNT(*)' not in sql_upper:
                logger.warning("[ExecutionEngine] 🚫 SELECT * detectado - bloqueando query")
                ac = action.copy()
                ac['_guardrails_error'] = True
                ac['_guardrails_warnings'] = [
                    "SELECT * no permitido por seguridad",
                    "Especifica columnas concretas (ej.: SELECT id, nombre FROM tabla LIMIT 20)"
                ]
                return ac

            # si no hay LIMIT, añadirlo solo para SELECTs (no DDL/DML)
            is_select = sql_upper.strip().startswith("SELECT")
            has_limit = re.search(r'\bLIMIT\s+\d+\b', sql_upper) is not None
            if is_select and not has_limit:
                logger.info("[ExecutionEngine] 🔒 Agregando LIMIT 20 a query sin límite")
                base = original_sql.rstrip().rstrip(';')
                ac = action.copy()
                ac['sql'] = f"{base} LIMIT 20;"
                meta = ac.get('_chat_guardrails_applied', {})
                meta.update({'limit_added': True, 'max_rows': 20})
                ac['_chat_guardrails_applied'] = meta
                action = ac
                sql_upper = ac['sql'].upper()

            # advertencia: SELECT sin WHERE (solo aviso si tampoco hay LIMIT explícito)
            if is_select and 'WHERE' not in sql_upper and not has_limit:
                ac = action.copy()
                meta = ac.get('_chat_guardrails_applied', {})
                meta.update({'warning': "Query sin filtros WHERE – puede devolver demasiadas filas"})
                ac['_chat_guardrails_applied'] = meta
                action = ac

            return action

        except Exception as e:
            logger.error(f"[ExecutionEngine] ❌ Error aplicando guardrails de chat: {e}")
            return action


    def _format_result_for_chat(self, result: Any, action_type: str = "db_query") -> Dict[str, Any]:
        """
        Formatea resultados para ser apropiados y legibles en chat.
        Aplica límites automáticos y formateo inteligente.
        """
        try:
            if action_type == "db_query":
                if isinstance(result, list):
                    # 🔒 LIMITAR resultados para chat
                    if len(result) > 20:
                        preview_result = result[:20]
                        return {
                            "data": preview_result,
                            "total_rows": len(result),
                            "is_preview": True,
                            "preview_limit": 20,
                            "message": f"Mostrando vista previa de {len(result)} filas (limitado a 20 para chat)",
                            "formatted": True,
                            "format_type": "preview_with_count"
                        }
                    
                    # Formatear como tabla legible
                    if result:
                        return {
                            "data": result,
                            "total_rows": len(result),
                            "is_preview": False,
                            "formatted": True,
                            "format_type": "full_table",
                            "table_markdown": self._format_list_as_table(result)
                        }
                    
                    # Sin resultados
                    return {
                        "data": [],
                        "total_rows": 0,
                        "is_preview": False,
                        "formatted": True,
                        "format_type": "no_results",
                        "message": "No se encontraron resultados"
                    }
                
                elif isinstance(result, dict):
                    # Resultado ya formateado
                    return result
                
                else:
                    # Otros tipos de resultado
                    return {
                        "data": result,
                        "formatted": True,
                        "format_type": "raw_data"
                    }
            
            return result
            
        except Exception as e:
            logger.error(f"[ExecutionEngine] ❌ Error formateando resultado para chat: {e}")
            return {
                "data": result,
                "formatted": False,
                "error": f"Error formateando: {str(e)}"
            }
