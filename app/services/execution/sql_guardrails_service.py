"""
Servicio de guardrails SQL para prevenir queries problemáticas.

Implementa:
- Validación de tablas existentes
- Prohibición de SELECT *
- Forzado de LIMIT en queries grandes
- Detección de queries peligrosas
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.utils.logger import logger


class SQLGuardrailsService:
    """
    Servicio de guardrails para queries SQL.
    
    Previene:
    - Queries a tablas inexistentes
    - SELECT * sin LIMIT
    - Queries potencialmente peligrosas
    - Queries sin contexto de schema
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.max_limit = 100  # Límite máximo por defecto
        self.default_limit = 10  # Límite por defecto si no se especifica
    
    # =====================================================
    # VALIDACIÓN PRINCIPAL
    # =====================================================
    
    def validate_and_fix_query(
        self, 
        query: str, 
        user_id: UUID, 
        db_id: UUID,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, List[str], bool]:
        """
        Valida y corrige una query SQL.
        
        Args:
            query: Query SQL original
            user_id: ID del usuario
            db_id: ID de la base de datos
            context: Contexto adicional
            
        Returns:
            Tuple de (query_corregida, warnings, es_segura)
        """
        logger.info(f"[SQLGuardrails] 🛡️ Validando query para db={db_id}")
        
        warnings = []
        is_safe = True
        fixed_query = query.strip()
        
        try:
            # 1. Obtener schema cache para validación
            schema_cache = self._get_schema_cache(user_id, db_id)
            if not schema_cache:
                warnings.append("⚠️ No hay cache de schema disponible - validación limitada")
                logger.warning("[SQLGuardrails] No se pudo obtener cache de schema")
            
            # 2. Validar tablas existentes
            if schema_cache:
                table_warnings = self._validate_tables_exist(fixed_query, schema_cache)
                warnings.extend(table_warnings)
                
                # Si hay tablas inexistentes, marcar como no segura
                if any("no existe" in w for w in table_warnings):
                    is_safe = False
            
            # 3. Detectar y corregir SELECT *
            fixed_query, select_warnings = self._fix_select_star(fixed_query, schema_cache)
            warnings.extend(select_warnings)
            
            # 4. Agregar LIMIT si es necesario
            fixed_query, limit_warnings = self._enforce_limit(fixed_query)
            warnings.extend(limit_warnings)
            
            # 5. Detectar queries peligrosas
            danger_warnings = self._detect_dangerous_patterns(fixed_query)
            warnings.extend(danger_warnings)
            if danger_warnings:
                is_safe = False
            
            # 6. Validar sintaxis básica
            syntax_warnings = self._validate_syntax(fixed_query)
            warnings.extend(syntax_warnings)
            if syntax_warnings:
                is_safe = False
            
            logger.info(f"[SQLGuardrails] ✅ Validación completada - Segura: {is_safe}, Warnings: {len(warnings)}")
            
            return fixed_query, warnings, is_safe
            
        except Exception as e:
            logger.exception(f"[SQLGuardrails] ❌ Error validando query: {e}")
            return query, [f"❌ Error de validación: {str(e)}"], False
    
    # =====================================================
    # VALIDACIONES ESPECÍFICAS
    # =====================================================
    
    def _get_schema_cache(self, user_id: UUID, db_id: UUID) -> Optional[Dict[str, Any]]:
        """Obtiene cache de schema para validación"""
        try:
            cache_service = self.factory.get_detailed_schema_cache_service()
            cache = cache_service.get_schema_cache(user_id, db_id)
            
            if cache and cache.snapshot:
                return {
                    'tables': list(cache.snapshot.tables.keys()),
                    'table_details': cache.snapshot.tables,
                    'compact': cache.compact
                }
        except Exception as e:
            logger.warning(f"[SQLGuardrails] No se pudo obtener cache: {e}")
        
        return None
    
    def _validate_tables_exist(self, query: str, schema_cache: Dict[str, Any]) -> List[str]:
        """Valida que las tablas referenciadas existan"""
        warnings = []
        available_tables = set(schema_cache.get('tables', []))
        
        # Extraer nombres de tablas de la query
        referenced_tables = self._extract_table_names(query)
        
        for table in referenced_tables:
            if table.lower() not in [t.lower() for t in available_tables]:
                warnings.append(f"🚫 Tabla '{table}' no existe en la base de datos")
                logger.warning(f"[SQLGuardrails] Tabla inexistente: {table}")
        
        return warnings
    
    def _extract_table_names(self, query: str) -> List[str]:
        """Extrae nombres de tablas de una query SQL"""
        # Patrones para diferentes tipos de referencias a tablas
        patterns = [
            r'\bFROM\s+(\w+)',
            r'\bJOIN\s+(\w+)',
            r'\bINTO\s+(\w+)',
            r'\bUPDATE\s+(\w+)',
            r'\bDELETE\s+FROM\s+(\w+)',
        ]
        
        tables = set()
        query_upper = query.upper()
        
        for pattern in patterns:
            matches = re.findall(pattern, query_upper, re.IGNORECASE)
            tables.update(matches)
        
        return list(tables)
    
    def _fix_select_star(self, query: str, schema_cache: Optional[Dict[str, Any]] = None) -> Tuple[str, List[str]]:
        """Detecta y corrige SELECT *"""
        warnings = []
        
        # Detectar SELECT *
        if re.search(r'\bSELECT\s+\*', query, re.IGNORECASE):
            warnings.append("⚠️ SELECT * detectado - considera especificar columnas")
            
            # Si tenemos schema cache, intentar sugerir columnas
            if schema_cache:
                table_names = self._extract_table_names(query)
                if len(table_names) == 1:
                    table_name = table_names[0].lower()
                    table_details = schema_cache.get('table_details', {})
                    
                    # Buscar tabla (case insensitive)
                    matching_table = None
                    for t_name, t_details in table_details.items():
                        if t_name.lower() == table_name:
                            matching_table = t_details
                            break
                    
                    if matching_table:
                        columns = list(matching_table.get('columns', {}).keys())
                        if columns:
                            # Limitar a primeras 10 columnas para evitar queries muy largas
                            selected_columns = columns[:10]
                            column_list = ', '.join(selected_columns)
                            
                            # Reemplazar SELECT *
                            fixed_query = re.sub(
                                r'\bSELECT\s+\*', 
                                f'SELECT {column_list}',
                                query,
                                flags=re.IGNORECASE
                            )
                            
                            if len(columns) > 10:
                                warnings.append(f"ℹ️ Mostrando solo {len(selected_columns)} de {len(columns)} columnas disponibles")
                            
                            return fixed_query, warnings
        
        return query, warnings
    
    def _enforce_limit(self, query: str) -> Tuple[str, List[str]]:
        """Agrega LIMIT si no existe en queries SELECT"""
        warnings = []
        
        # Solo aplicar a queries SELECT
        if not re.search(r'\bSELECT\b', query, re.IGNORECASE):
            return query, warnings
        
        # Verificar si ya tiene LIMIT
        if re.search(r'\bLIMIT\s+\d+', query, re.IGNORECASE):
            # Verificar que el LIMIT no sea excesivo
            limit_match = re.search(r'\bLIMIT\s+(\d+)', query, re.IGNORECASE)
            if limit_match:
                limit_value = int(limit_match.group(1))
                if limit_value > self.max_limit:
                    # Reemplazar con límite máximo
                    fixed_query = re.sub(
                        r'\bLIMIT\s+\d+',
                        f'LIMIT {self.max_limit}',
                        query,
                        flags=re.IGNORECASE
                    )
                    warnings.append(f"⚠️ LIMIT reducido de {limit_value} a {self.max_limit}")
                    return fixed_query, warnings
            return query, warnings
        
        # Agregar LIMIT por defecto
        fixed_query = f"{query.rstrip(';')} LIMIT {self.default_limit}"
        warnings.append(f"ℹ️ LIMIT {self.default_limit} agregado automáticamente")
        
        return fixed_query, warnings
    
    def _detect_dangerous_patterns(self, query: str) -> List[str]:
        """Detecta patrones peligrosos en la query"""
        warnings = []
        query_upper = query.upper()
        
        dangerous_patterns = [
            (r'\bDROP\s+TABLE\b', "🚫 DROP TABLE no permitido"),
            (r'\bTRUNCATE\b', "🚫 TRUNCATE no permitido"),
            (r'\bDELETE\s+FROM\s+\w+\s*(?!WHERE)', "🚫 DELETE sin WHERE no permitido"),
            (r'\bUPDATE\s+\w+\s+SET\s+.*(?!WHERE)', "🚫 UPDATE sin WHERE no permitido"),
            (r'\bALTER\s+TABLE\b', "🚫 ALTER TABLE no permitido"),
            (r'\bCREATE\s+TABLE\b', "🚫 CREATE TABLE no permitido"),
            (r';.*SELECT', "🚫 Múltiples statements no permitidos"),
        ]
        
        for pattern, message in dangerous_patterns:
            if re.search(pattern, query_upper, re.IGNORECASE):
                warnings.append(message)
        
        return warnings
    
    def _validate_syntax(self, query: str) -> List[str]:
        """Validación básica de sintaxis SQL"""
        warnings = []
        
        # Verificar balance de paréntesis
        if query.count('(') != query.count(')'):
            warnings.append("🚫 Paréntesis desbalanceados")
        
        # Verificar que no esté vacía
        if not query.strip():
            warnings.append("🚫 Query vacía")
        
        # Verificar palabras clave básicas
        if not re.search(r'\b(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER)\b', query, re.IGNORECASE):
            warnings.append("🚫 No se detectó comando SQL válido")
        
        return warnings
    
    # =====================================================
    # UTILIDADES
    # =====================================================
    
    def get_query_info(self, query: str) -> Dict[str, Any]:
        """Obtiene información sobre una query"""
        return {
            'type': self._get_query_type(query),
            'tables': self._extract_table_names(query),
            'has_limit': bool(re.search(r'\bLIMIT\s+\d+', query, re.IGNORECASE)),
            'has_where': bool(re.search(r'\bWHERE\b', query, re.IGNORECASE)),
            'has_select_star': bool(re.search(r'\bSELECT\s+\*', query, re.IGNORECASE)),
            'estimated_safety': self._estimate_safety(query)
        }
    
    def _get_query_type(self, query: str) -> str:
        """Determina el tipo de query"""
        query_upper = query.upper().strip()
        
        if query_upper.startswith('SELECT'):
            return 'SELECT'
        elif query_upper.startswith('INSERT'):
            return 'INSERT'
        elif query_upper.startswith('UPDATE'):
            return 'UPDATE'
        elif query_upper.startswith('DELETE'):
            return 'DELETE'
        elif query_upper.startswith('CREATE'):
            return 'CREATE'
        elif query_upper.startswith('DROP'):
            return 'DROP'
        elif query_upper.startswith('ALTER'):
            return 'ALTER'
        else:
            return 'UNKNOWN'
    
    def _estimate_safety(self, query: str) -> float:
        """Estima la seguridad de una query (0.0 = peligrosa, 1.0 = segura)"""
        score = 1.0
        
        # Penalizar patrones peligrosos
        dangerous_patterns = [
            r'\bDROP\b', r'\bTRUNCATE\b', r'\bDELETE\s+FROM\s+\w+\s*(?!WHERE)',
            r'\bUPDATE\s+\w+\s+SET\s+.*(?!WHERE)', r'\bALTER\b'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                score -= 0.3
        
        # Penalizar SELECT * sin LIMIT
        if re.search(r'\bSELECT\s+\*', query, re.IGNORECASE) and not re.search(r'\bLIMIT\b', query, re.IGNORECASE):
            score -= 0.2
        
        # Bonificar buenas prácticas
        if re.search(r'\bLIMIT\s+\d+', query, re.IGNORECASE):
            score += 0.1
        
        if re.search(r'\bWHERE\b', query, re.IGNORECASE):
            score += 0.1
        
        return max(0.0, min(1.0, score))
