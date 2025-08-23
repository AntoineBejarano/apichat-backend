import time
import logging
from typing import Dict, Any, List

from app.core.service_factory import ServiceFactory
from ..state.exploration_state import ExplorationState
from ..cache.schema_cache import SchemaCache
from ..cache.service_cache import ServiceCache
from ..utils.performance_metrics import PerformanceMetrics

logger = logging.getLogger(__name__)


class ExecutionNode:
    """Nodo para ejecutar planes y enriquecer respuestas con datos"""
    
    def __init__(self, factory: ServiceFactory, schema_cache: SchemaCache, service_cache: ServiceCache):
        self.factory = factory
        self.schema_cache = schema_cache
        self.service_cache = service_cache
        self._processed_responses_cache = {}
    
    async def run(self, state: ExplorationState, performance_metrics: PerformanceMetrics) -> ExplorationState:
        """Ejecuta el plan generado por OpenAI"""
        node_start_time = time.time()
        
        try:
            plan = state.get("plan")
            if not plan:
                logger.info("[ExecutionNode] ℹ️ No hay plan para ejecutar")
                return state
            
            logger.info(f"[ExecutionNode] 🚀 Ejecutando plan con {len(plan.actions)} acciones")
            
            # Obtener servicios
            execution_engine = self._get_service_lazy("execution_engine_service", self.factory.get_execution_engine_service)
            if not execution_engine:
                logger.error("[ExecutionNode] ❌ ExecutionEngineService no disponible")
                return {**state, "error": "Servicio de ejecución no disponible"}
            
            # Preparar contexto para ejecución
            execution_context = {
                "chat_id": state["chat_id"],
                "user_id": self.factory.user.id if hasattr(self.factory, 'user') else None,
                "db_ids": state.get("db_ids", []),
                "app_ids": state.get("app_ids", []),
                "compact_schemas": state.get("compact_schemas", {}),
                "functions": state.get("functions", []),
                "history": state.get("history", [])
            }
            
            # Ejecutar el plan
            execution_result = await execution_engine.run(
                plan=plan.model_dump(),
                chat_id=state["chat_id"],
                ctx=execution_context
            )
            
            logger.info(f"[ExecutionNode] ✅ Plan ejecutado exitosamente")
            
            # 🔧 DEBUG: Inspeccionar estructura completa del resultado
            self._debug_execution_result(execution_result)
            
            # Limpiar y cachear schemas
            cleaned_schemas = await self._process_schema_cleaning(state)
            
            # 🔧 DEBUG: Verificar que los schemas se limpiaron correctamente
            if cleaned_schemas:
                for db_id, schema in cleaned_schemas.items():
                    original_length = len(state.get("compact_schemas", {}).get(db_id, ""))
                    cleaned_length = len(schema)
                    logger.info(f"[ExecutionNode] 🔍 Schema DB {db_id}: {original_length} → {cleaned_length} caracteres")
            else:
                logger.warning(f"[ExecutionNode] ⚠️ No se obtuvieron schemas limpios")
            
            # Construir respuesta enriquecida
            enriched_response = await self._build_enriched_response(plan, execution_result)
            
            # Verificar duplicados
            response_signature = f"{plan.assistant_response}_{len(execution_result.get('variables', {}))}"
            if response_signature in self._processed_responses_cache:
                logger.info(f"[ExecutionNode] 🔄 Respuesta ya procesada, evitando duplicado")
                return self._processed_responses_cache[response_signature]
            
            # Preparar respuesta final - USAR SCHEMAS LIMPIOS, NO LOS ORIGINALES
            final_response = {
                **state,
                "execution_results": execution_result,
                "assistant_response": enriched_response,
                "compact_schemas": cleaned_schemas,  # Schema LIMPIO, no el original
                "data": self._extract_execution_data(execution_result)
            }
            
            # 🔧 CRÍTICO: Reemplazar el schema original con el limpio en la respuesta final
            if cleaned_schemas:
                logger.info(f"[ExecutionNode] ✅ Schema LIMPIO aplicado a respuesta final: {len(cleaned_schemas)} DBs")
                # Asegurar que el usuario vea el schema limpio, no el original
                final_response["compact_schemas"] = cleaned_schemas
            else:
                logger.warning(f"[ExecutionNode] ⚠️ No se pudieron limpiar schemas, usando originales")
            
            # Cachear respuesta procesada
            self._processed_responses_cache[response_signature] = final_response
            
            # Limpieza de cache
            self._cleanup_response_cache()
            
            # Registrar métricas
            node_time = time.time() - node_start_time
            performance_metrics.record_node_time("sql_exec", node_time)
            performance_metrics.calculate_total_time()
            performance_metrics.log_breakdown()
            
            final_response["performance_metrics"] = performance_metrics.get_metrics()
            
            return final_response
            
        except Exception as e:
            logger.exception(f"[ExecutionNode] ❌ Error ejecutando plan: {e}")
            return {
                **state,
                "error": str(e),
                "assistant_response": f"Error ejecutando el plan: {str(e)}"
            }
    
    def _debug_execution_result(self, execution_result: Dict[str, Any]):
        """🔧 DEBUG: Inspecciona la estructura completa del resultado de ejecución"""
        logger.info(f"[ExecutionNode] 🔍 === DEBUG EXECUTION RESULT ===")
        logger.info(f"[ExecutionNode] 🔍 Tipo: {type(execution_result)}")
        logger.info(f"[ExecutionNode] 🔍 Keys: {list(execution_result.keys())}")
        
        # Inspeccionar variables
        variables = execution_result.get("variables", {})
        logger.info(f"[ExecutionNode] 🔍 Variables tipo: {type(variables)}")
        
        if isinstance(variables, dict):
            for key, value in variables.items():
                logger.info(f"[ExecutionNode] 🔍   {key}: {type(value)} - {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
        else:
            logger.info(f"[ExecutionNode] 🔍   Variables no es dict: {variables}")
        
        # Inspeccionar otros campos importantes
        for key in ["result", "data", "rows", "content", "error"]:
            if key in execution_result:
                value = execution_result[key]
                logger.info(f"[ExecutionNode] 🔍   {key}: {type(value)} - {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
        
        logger.info(f"[ExecutionNode] 🔍 === FIN DEBUG ===")
    
    async def _process_schema_cleaning(self, state: ExplorationState) -> Dict[str, str]:
        """Procesa la limpieza y cache de schemas"""
        cleaned_schemas = {}
        
        if not state.get("compact_schemas"):
            return cleaned_schemas
        
        try:
            # Cachear schema limpio por usuario + DB para evitar re-limpieza
            cache_key = f"cleaned_schema_{self.factory.user.id}"
            
            # Verificar si ya tenemos schemas limpios en cache
            cached_schemas = {}
            for db_id in state["compact_schemas"].keys():
                cached_schema = self.schema_cache.get_cleaned_schema(self.factory.user.id, db_id)
                if cached_schema:
                    cached_schemas[db_id] = cached_schema
            
            if cached_schemas:
                # Cache parcial - limpiar solo los que faltan
                missing_db_ids = [db_id for db_id in state["compact_schemas"].keys() if db_id not in cached_schemas]
                
                if missing_db_ids:
                    logger.info(f"[ExecutionNode] 🔄 Cache parcial: Limpiando {len(missing_db_ids)} schemas faltantes")
                    await self._clean_missing_schemas(state["compact_schemas"], missing_db_ids, cache_key)
                
                # 🔧 CRÍTICO: Combinar schemas del cache con los recién limpiados
                cleaned_schemas = {**cached_schemas}
                
                # Obtener los schemas recién limpiados del cache
                for db_id in missing_db_ids:
                    fresh_cleaned = self.schema_cache.get_cleaned_schema(self.factory.user.id, db_id)
                    if fresh_cleaned:
                        cleaned_schemas[db_id] = fresh_cleaned
                        logger.info(f"[ExecutionNode] ✅ Schema recién limpiado agregado para DB {db_id}")
            else:
                # Primera vez: limpiar todos los schemas
                logger.info(f"[ExecutionNode] 🆕 Cache MISS: Limpiando todos los schemas para usuario {self.factory.user.id}")
                await self._clean_all_schemas(state["compact_schemas"], cache_key)
                
                # 🔧 CRÍTICO: Obtener todos los schemas limpios del cache
                cleaned_schemas = {}
                for db_id in state["compact_schemas"].keys():
                    cleaned_schema = self.schema_cache.get_cleaned_schema(self.factory.user.id, db_id)
                    if cleaned_schema:
                        cleaned_schemas[db_id] = cleaned_schema
                        logger.info(f"[ExecutionNode] ✅ Schema limpio obtenido del cache para DB {db_id}")
                    else:
                        logger.warning(f"[ExecutionNode] ⚠️ No se pudo obtener schema limpio para DB {db_id}")
            
            # Limpieza de cache: mantener solo los últimos 10 usuarios
            self._cleanup_schema_cache()
            
        except Exception as e:
            logger.warning(f"[ExecutionNode] ⚠️ Error limpiando schema: {e}")
            cleaned_schemas = state.get("compact_schemas", {})
        
        # 🔧 DEBUG FINAL: Verificar resultado de la limpieza
        if cleaned_schemas:
            total_original = sum(len(schema) for schema in state.get("compact_schemas", {}).values())
            total_cleaned = sum(len(schema) for schema in cleaned_schemas.values())
            logger.info(f"[ExecutionNode] 📊 RESUMEN LIMPIEZA: Total original: {total_original} → Total limpio: {total_cleaned} caracteres")
        else:
            logger.warning(f"[ExecutionNode] ⚠️ No se obtuvieron schemas limpios, usando originales")
        
        return cleaned_schemas
    
    async def _clean_missing_schemas(self, schemas: Dict[str, str], missing_db_ids: List[str], cache_key: str):
        """Limpia solo los schemas que faltan en el cache"""
        openai_service = self._get_service_lazy("openai_service", self.factory.get_openai_service)
        
        if not openai_service:
            logger.error("[ExecutionNode] ❌ OpenAI service no disponible para limpiar schemas faltantes")
            return
        
        for db_id in missing_db_ids:
            try:
                schema = schemas[db_id]
                original_length = len(schema)
                
                # 🔧 CRÍTICO: Usar el método correcto para limpiar schema
                if hasattr(openai_service, '_optimize_schema_for_query'):
                    cleaned_schema = openai_service._optimize_schema_for_query(schema, "")
                elif hasattr(openai_service, 'optimize_schema_for_query'):
                    cleaned_schema = openai_service.optimize_schema_for_query(schema, "")
                else:
                    logger.error("[ExecutionNode] ❌ Método de limpieza de schema no encontrado en OpenAI service")
                    cleaned_schema = schema  # Usar original si no se puede limpiar
                
                # Cachear schema limpio
                self.schema_cache.set_cleaned_schema(self.factory.user.id, db_id, cleaned_schema)
                cleaned_length = len(cleaned_schema)
                logger.info(f"[ExecutionNode] 🧹 Schema limpiado para DB {db_id}: {original_length} → {cleaned_length} caracteres")
                
            except Exception as e:
                logger.error(f"[ExecutionNode] ❌ Error limpiando schema faltante para DB {db_id}: {e}")
                # En caso de error, usar schema original
                self.schema_cache.set_cleaned_schema(self.factory.user.id, db_id, schema)
    
    async def _clean_all_schemas(self, schemas: Dict[str, str], cache_key: str):
        """Limpia todos los schemas y los cachea"""
        openai_service = self._get_service_lazy("openai_service", self.factory.get_openai_service)
        
        if not openai_service:
            logger.error("[ExecutionNode] ❌ OpenAI service no disponible para limpiar schemas")
            return
        
        for db_id, schema in schemas.items():
            try:
                # Optimización: reducir tamaño del schema antes de limpiar
                original_length = len(schema)
                if original_length > 50000:
                    logger.info(f"[ExecutionNode] ⚡ Schema muy grande ({original_length} chars), truncando antes de limpiar")
                    schema = schema[:50000] + "\n-- [TRUNCATED FOR OPTIMIZATION] --"
                
                # 🔧 CRÍTICO: Usar el método correcto para limpiar schema
                if hasattr(openai_service, '_optimize_schema_for_query'):
                    cleaned_schema = openai_service._optimize_schema_for_query(schema, "")
                elif hasattr(openai_service, 'optimize_schema_for_query'):
                    cleaned_schema = openai_service.optimize_schema_for_query(schema, "")
                else:
                    logger.error("[ExecutionNode] ❌ Método de limpieza de schema no encontrado en OpenAI service")
                    cleaned_schema = schema  # Usar original si no se puede limpiar
                
                # Cachear schema limpio
                self.schema_cache.set_cleaned_schema(self.factory.user.id, db_id, cleaned_schema)
                cleaned_length = len(cleaned_schema)
                logger.info(f"[ExecutionNode] 🧹 Schema limpiado para DB {db_id}: {original_length} → {cleaned_length} caracteres")
                
            except Exception as e:
                logger.error(f"[ExecutionNode] ❌ Error limpiando schema para DB {db_id}: {e}")
                # En caso de error, usar schema original
                self.schema_cache.set_cleaned_schema(self.factory.user.id, db_id, schema)
    
    async def _build_enriched_response(self, plan, execution_result: Dict[str, Any]) -> str:
        """Construye la respuesta enriquecida con los datos obtenidos"""
        enriched_response = plan.assistant_response or "Plan ejecutado exitosamente"
        
        # 🔧 REFORZADO: Extraer datos de múltiples fuentes posibles
        variables = execution_result.get("variables", {})
        
        # Buscar datos en diferentes ubicaciones
        invitations = self._find_data_in_result(execution_result, "invitations")
        tables = self._find_data_in_result(execution_result, "tables")
        
        logger.info(f"[ExecutionNode] 🔍 Datos encontrados - invitations: {type(invitations)} ({len(invitations) if hasattr(invitations, '__len__') else 'N/A'}), tables: {type(tables)} ({len(tables) if hasattr(tables, '__len__') else 'N/A'})")
        
        # Enriquecer con datos reales
        if invitations:
            enriched_response = self._enrich_with_invitations(enriched_response, invitations)
        elif tables:
            enriched_response = self._enrich_with_tables(enriched_response, tables)
        else:
            logger.info("[ExecutionNode] ℹ️ No se encontraron datos para enriquecer la respuesta")
        
        return enriched_response
    
    def _find_data_in_result(self, execution_result: Dict[str, Any], data_key: str) -> Any:
        """🔧 Busca datos en múltiples ubicaciones del resultado de ejecución"""
        logger.info(f"[ExecutionNode] 🔍 Buscando '{data_key}' en execution_result...")
        
        # Buscar en variables
        variables = execution_result.get("variables", {})
        if isinstance(variables, dict) and data_key in variables:
            logger.info(f"[ExecutionNode] ✅ '{data_key}' encontrado en variables")
            return variables[data_key]
        
        # Buscar en el nivel raíz
        if data_key in execution_result:
            logger.info(f"[ExecutionNode] ✅ '{data_key}' encontrado en nivel raíz")
            return execution_result[data_key]
        
        # Buscar en result
        result = execution_result.get("result", {})
        if isinstance(result, dict) and data_key in result:
            logger.info(f"[ExecutionNode] ✅ '{data_key}' encontrado en result")
            return result[data_key]
        
        # Buscar en data
        data = execution_result.get("data", {})
        if isinstance(data, dict) and data_key in data:
            logger.info(f"[ExecutionNode] ✅ '{data_key}' encontrado en data")
            return data[data_key]
        
        # Buscar en rows
        rows = execution_result.get("rows", {})
        if isinstance(rows, dict) and data_key in rows:
            logger.info(f"[ExecutionNode] ✅ '{data_key}' encontrado en rows")
            return rows[data_key]
        
        logger.warning(f"[ExecutionNode] ⚠️ '{data_key}' no encontrado en ninguna ubicación")
        return []
    
    def _enrich_with_invitations(self, response: str, invitations: Any) -> str:
        """Enriquece la respuesta con datos de invitaciones de manera genérica"""
        # 🔧 REFACTORIZADO: Función completamente genérica para cualquier tipo de dato
        logger.info(f"[ExecutionNode] 🔍 Tipo de invitations recibido: {type(invitations)}")
        
        # Normalizar datos de manera genérica
        normalized_data = self._normalize_data_generic(invitations, "invitations")
        
        if not normalized_data:
            logger.warning("[ExecutionNode] ⚠️ No se pudieron normalizar los datos de invitations")
            response += f"\n\n❌ **ERROR:** No se pudieron procesar los datos de invitaciones"
            return response
        
        data_count = len(normalized_data)
        response += f"\n\n✅ **RESULTADOS OBTENIDOS:**\n"
        response += f"📊 Se encontraron **{data_count} invitaciones** en la tabla `invitation_requests`:\n\n"
        
        if data_count > 0:
            # Mostrar los primeros 5 elementos
            for i, item in enumerate(normalized_data[:5], 1):
                response += f"**{i}.** "
                if isinstance(item, dict):
                    # Extraer campos comunes de manera genérica
                    name = item.get('name', item.get('full_name', item.get('first_name', 'N/A')))
                    email = item.get('email', item.get('email_address', 'N/A'))
                    club_name = item.get('club_name', item.get('club', item.get('organization', 'N/A')))
                    message = item.get('message', item.get('comment', item.get('notes', 'N/A')))
                    
                    response += f"**{name}** ({email}) - Club: {club_name}\n"
                    if message and message != 'N/A':
                        response += f"   💬 {message[:100]}{'...' if len(message) > 100 else ''}\n"
                else:
                    # Si no es diccionario, mostrar como string
                    response += f"{str(item)[:100]}\n"
                response += "\n"
            
            if data_count > 5:
                response += f"... y **{data_count - 5} invitaciones más**\n"
        
        return response
    
    def _normalize_data_generic(self, data: Any, data_name: str) -> List[Any]:
        """
        🔧 NUEVO: Función genérica para normalizar cualquier tipo de dato
        Convierte cualquier estructura de datos en una lista iterable
        """
        logger.info(f"[ExecutionNode] 🔧 Normalizando {data_name}: {type(data)}")
        
        # Si es None o vacío
        if data is None:
            logger.info(f"[ExecutionNode] ℹ️ {data_name} es None")
            return []
        
        # Si es string, intentar parsearlo
        if isinstance(data, str):
            return self._parse_string_data(data, data_name)
        
        # Si es diccionario, extraer datos
        if isinstance(data, dict):
            return self._extract_from_dict(data, data_name)
        
        # Si es lista o tupla, devolver tal cual
        if isinstance(data, (list, tuple)):
            logger.info(f"[ExecutionNode] ✅ {data_name} es {type(data)} con {len(data)} elementos")
            return list(data)
        
        # Si es iterable pero no string, convertir a lista
        if hasattr(data, '__iter__') and not isinstance(data, str):
            try:
                result = list(data)
                logger.info(f"[ExecutionNode] ✅ {data_name} convertido a lista usando __iter__: {len(result)} elementos")
                return result
            except Exception as e:
                logger.error(f"[ExecutionNode] ❌ Error convirtiendo {data_name} a lista: {e}")
                return []
        
        # Otros tipos: convertir a lista de un elemento
        logger.warning(f"[ExecutionNode] ⚠️ {data_name} tipo inesperado: {type(data)}, convirtiendo a lista de un elemento")
        return [data]
    
    def _parse_string_data(self, data: str, data_name: str) -> List[Any]:
        """Parsea datos string de manera robusta"""
        logger.info(f"[ExecutionNode] 🔧 Parseando string {data_name}: {data[:100]}...")
        
        # Intentar JSON primero
        try:
            import json
            parsed = json.loads(data)
            logger.info(f"[ExecutionNode] ✅ {data_name} parseado como JSON: {type(parsed)}")
            return self._normalize_data_generic(parsed, f"{data_name}_parsed")
        except json.JSONDecodeError:
            logger.debug(f"[ExecutionNode] 🔍 {data_name} no es JSON válido")
        
        # Intentar ast.literal_eval si parece una estructura
        if data.startswith('[') or data.startswith('{'):
            try:
                import ast
                parsed = ast.literal_eval(data)
                logger.info(f"[ExecutionNode] ✅ {data_name} parseado con ast.literal_eval: {type(parsed)}")
                return self._normalize_data_generic(parsed, f"{data_name}_parsed")
            except Exception as e:
                logger.debug(f"[ExecutionNode] 🔍 {data_name} no se pudo parsear con ast.literal_eval: {e}")
        
        # Si no se puede parsear, tratar como texto plano
        logger.warning(f"[ExecutionNode] ⚠️ {data_name} no se pudo parsear, tratando como texto plano")
        return [data]
    
    def _extract_from_dict(self, data: Dict[str, Any], data_name: str) -> List[Any]:
        """Extrae datos de un diccionario de manera genérica"""
        logger.info(f"[ExecutionNode] 🔍 {data_name} es dict con keys: {list(data.keys())}")
        
        # Buscar en campos comunes de datos
        common_data_keys = ["rows", "data", "result", "content", "items", "records", "list"]
        for key in common_data_keys:
            if key in data:
                result = data[key]
                logger.info(f"[ExecutionNode] ✅ {data_name} extraído de '{key}': {type(result)}")
                return self._normalize_data_generic(result, f"{data_name}_{key}")
        
        # Si no hay campos de datos comunes, buscar en variables anidadas
        if "variables" in data:
            variables = data["variables"]
            if isinstance(variables, dict):
                # Buscar el mismo nombre de dato en variables anidadas
                if data_name in variables:
                    nested_data = variables[data_name]
                    logger.info(f"[ExecutionNode] ✅ {data_name} encontrado en variables anidadas: {type(nested_data)}")
                    return self._normalize_data_generic(nested_data, f"{data_name}_nested")
        
        # Si no se encuentra estructura esperada, usar el diccionario completo
        logger.warning(f"[ExecutionNode] ⚠️ {data_name} dict sin estructura esperada, usando completo")
        return [data]
    
    def _enrich_with_tables(self, response: str, tables: Any) -> str:
        """Enriquece la respuesta con datos de tablas de manera genérica"""
        # 🔧 REFACTORIZADO: Usar el mismo sistema genérico
        logger.info(f"[ExecutionNode] 🔍 Tipo de tables recibido: {type(tables)}")
        
        # Normalizar datos de manera genérica
        normalized_data = self._normalize_data_generic(tables, "tables")
        
        if not normalized_data:
            logger.warning("[ExecutionNode] ⚠️ No se pudieron normalizar los datos de tables")
            response += f"\n\n❌ **ERROR:** No se pudieron procesar los datos de tablas"
            return response
        
        data_count = len(normalized_data)
        response += f"\n\n✅ **RESULTADOS OBTENIDOS:**\n"
        response += f"📊 Se encontraron **{data_count} registros** en la consulta ejecutada.\n"
        
        if data_count > 0:
            # Mostrar los primeros 5 elementos
            for i, item in enumerate(normalized_data[:5], 1):
                response += f"**{i}.** "
                if isinstance(item, dict):
                    # Mostrar campos del diccionario de manera genérica
                    fields = []
                    for key, value in item.items():
                        if isinstance(value, (str, int, float)) and str(value) != 'None':
                            fields.append(f"{key}: {value}")
                    response += ", ".join(fields[:3])  # Mostrar solo los primeros 3 campos
                else:
                    # Si no es diccionario, mostrar como string
                    response += f"{str(item)[:100]}"
                response += "\n"
            
            if data_count > 5:
                response += f"... y **{data_count - 5} registros más**\n"
        
        return response
    
    def _extract_execution_data(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae los datos de la ejecución usando el sistema genérico"""
        logger.info(f"[ExecutionNode] 🔍 Estructura de execution_result: {list(execution_result.keys())}")
        
        variables = execution_result.get("variables", {})
        logger.info(f"[ExecutionNode] 🔍 Estructura de variables: {type(variables)} - {list(variables.keys()) if isinstance(variables, dict) else 'No es dict'}")
        
        # 🔧 REFACTORIZADO: Usar el sistema genérico de normalización
        tables = self._normalize_data_generic(variables.get("tables", []), "tables")
        invitations = self._normalize_data_generic(variables.get("invitations", []), "invitations")
        
        # Log del resultado final
        logger.info(f"[ExecutionNode] 📊 Datos normalizados - tables: {type(tables)} ({len(tables)}), invitations: {type(invitations)} ({len(invitations)})")
        
        return {
            "tables": tables,
            "invitations": invitations,
            "other_data": variables.get("other_data", {}),
            "raw_variables": variables  # Incluir variables raw para debugging
        }
    
    def _cleanup_response_cache(self):
        """Limpia el cache de respuestas procesadas"""
        if len(self._processed_responses_cache) > 50:
            oldest_keys = list(self._processed_responses_cache.keys())[:-50]
            for old_key in oldest_keys:
                del self._processed_responses_cache[old_key]
            logger.info(f"[ExecutionNode] 🧹 Cache de respuestas limpiado: {len(oldest_keys)} entradas antiguas removidas")
    
    def _cleanup_schema_cache(self):
        """Limpia el cache de schemas"""
        # Esta funcionalidad está en SchemaCache, pero podríamos llamarla aquí si es necesario
        pass
    
    def _get_service_lazy(self, service_name: str, service_factory_method):
        """Obtiene un servicio solo cuando se necesita"""
        # Verificar si ya tenemos el servicio en cache
        service_instance = self.service_cache.get_service(service_name)
        if service_instance:
            return service_instance
        
        # Crear nueva instancia
        try:
            service_instance = service_factory_method()
            if service_instance:
                # Usar register_service en lugar de set_service
                if hasattr(self.service_cache, 'register_service'):
                    self.service_cache.register_service(service_name, lambda: service_instance)
                else:
                    logger.warning(f"[ExecutionNode] ⚠️ Cache no soporta register_service para {service_name}")
                
                logger.info(f"[ExecutionNode] 🆕 Cache MISS: {service_name} inicializado")
                return service_instance
            else:
                logger.warning(f"[ExecutionNode] ⚠️ {service_name} no disponible")
                return None
                
        except Exception as e:
            logger.error(f"[ExecutionNode] ❌ Error inicializando {service_name}: {e}")
            return None
