#!/usr/bin/env python3
"""
🔍 Script de Debug para Detección de Intenciones
────────────────────────────────────────────────
Analiza exactamente por qué fallan ciertas consultas en la detección de intenciones.
"""
import sys
import asyncio
from pathlib import Path
from uuid import uuid4

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.context.schema_explorer_service import SchemaExplorerService
from app.services.context.synonyms_config_service import SynonymsConfigService

class MockCacheService:
    def get(self, key):
        return None
    def set(self, key, value, ttl=None):
        pass

class MockDatabaseService:
    def get_record(self, *args, **kwargs):
        return None

async def debug_intention_detection():
    """Debug de la detección de intenciones paso a paso."""
    
    print("🔍 DEBUG: Detección de Intenciones")
    print("=" * 60)
    
    # Inicializar servicio con mocks
    cache_service = MockCacheService()
    database_service = MockDatabaseService()
    service = SchemaExplorerService(cache_service=cache_service, database_service=database_service)
    
    # Consultas problemáticas identificadas en el test
    problematic_queries = [
        "¿cómo está estructurada la BD?",
        "¿cuál es el esquema de la base de datos?",
        "How is the database structured?",
        "Quel est le schéma de la base de données?",
        "Quelles entités y a-t-il dans ma base de données?",
        "Wie ist die Datenbank strukturiert?",
        "Qual è lo schema del database?",
        "Quali entità ci sono nel mio database?",
        "Como a base de dados está estruturada?",
        "Qual é o esquema da base de dados?"
    ]
    
    for query in problematic_queries:
        print(f"\n🔍 Analizando: '{query}'")
        print("-" * 40)
        
        # Normalizar consulta
        query_lower = query.lower()
        print(f"📝 Query normalizada: '{query_lower}'")
        
        # Extraer términos de búsqueda
        query_terms = service._extract_search_terms(query)
        print(f"🔤 Términos extraídos: {query_terms}")
        
        # Verificar cada indicador paso a paso
        print("\n🔍 Verificando indicadores:")
        
        # 1. Estructura
        structure_indicators = [
            'estructura', 'columna', 'campo', 'definicion', 'definición',
            'structure', 'column', 'field', 'definition',
            'structure', 'colonne', 'champ', 'définition',
            'struktur', 'spalte', 'feld', 'definition',
            'struttura', 'colonna', 'campo', 'definizione',
            'estrutura', 'coluna', 'campo', 'definição'
        ]
        structure_match = any(indicator in query_lower for indicator in structure_indicators)
        print(f"  🏗️  Estructura: {structure_match}")
        if structure_match:
            matching_indicators = [ind for ind in structure_indicators if ind in query_lower]
            print(f"     → Indicadores que coinciden: {matching_indicators}")
        
        # 2. Relaciones
        relationship_indicators = [
            'relacion', 'relación', 'foreign', 'key', 'conexion', 'conexión', 'vinculo', 'vínculo', 'link',
            'relationship', 'foreign', 'key', 'connection', 'link',
            'relation', 'étrangère', 'clé', 'connexion', 'lien',
            'beziehung', 'fremd', 'schlüssel', 'verbindung', 'verknüpfung',
            'relazione', 'straniera', 'chiave', 'connessione', 'collegamento',
            'relação', 'estrangeira', 'chave', 'conexão', 'ligação'
        ]
        relationship_match = any(indicator in query_lower for indicator in relationship_indicators)
        print(f"  🔗 Relaciones: {relationship_match}")
        
        # 3. Estadísticas
        stats_indicators = [
            'estadistica', 'estadística', 'tamaño', 'cantidad', 'numero', 'número', 'metrica', 'métrica',
            'stats', 'statistics', 'size', 'count', 'number', 'metric',
            'statistique', 'taille', 'compte', 'nombre', 'métrique',
            'statistik', 'größe', 'anzahl', 'zahl', 'metrik',
            'statistica', 'dimensione', 'conteggio', 'numero', 'metrica',
            'estatística', 'tamanho', 'contagem', 'número', 'métrica'
        ]
        stats_match = any(indicator in query_lower for indicator in stats_indicators)
        print(f"  📊 Estadísticas: {stats_match}")
        
        # 4. Listado (PRIORIDAD ALTA)
        list_indicators = [
            'tabla', 'tablas', 'lista', 'listado', 'todo', 'todas', 'disponible', 'disponibles',
            'table', 'tables', 'list', 'all', 'available',
            'table', 'tables', 'liste', 'tout', 'disponible',
            'tabelle', 'tabellen', 'liste', 'alle', 'verfügbar',
            'tabella', 'tabelle', 'lista', 'tutto', 'disponibile',
            'tabela', 'tabelas', 'lista', 'tudo', 'disponível'
        ]
        list_match = any(indicator in query_lower for indicator in list_indicators)
        print(f"  📋 Listado: {list_match}")
        if list_match:
            matching_indicators = [ind for ind in list_indicators if ind in query_lower]
            print(f"     → Indicadores que coinciden: {matching_indicators}")
        
        # 5. Búsqueda específica
        search_indicators = [
            'donde', 'buscar', 'encontrar', 'cual', 'cuál',
            'where', 'search', 'find', 'which',
            'où', 'rechercher', 'trouver', 'quel', 'quelle',
            'wo', 'suchen', 'finden', 'welche',
            'dove', 'cercare', 'trovare', 'quale',
            'onde', 'procurar', 'encontrar', 'qual'
        ]
        search_match = any(indicator in query_lower for indicator in search_indicators)
        print(f"  🔍 Búsqueda específica: {search_match}")
        if search_match:
            matching_indicators = [ind for ind in search_indicators if ind in query_lower]
            print(f"     → Indicadores que coinciden: {matching_indicators}")
        
        # 6. Esquema
        schema_indicators = [
            'esquema', 'base de datos', 'modelo', 'diseño', 'diseño',
            'schema', 'database', 'model', 'design',
            'schéma', 'base de données', 'modèle', 'conception',
            'schema', 'datenbank', 'modell', 'entwurf',
            'schema', 'database', 'modello', 'progetto',
            'esquema', 'banco de dados', 'modelo', 'design'
        ]
        schema_match = any(indicator in query_lower for indicator in schema_indicators)
        print(f"  🗃️  Esquema: {schema_match}")
        if schema_match:
            matching_indicators = [ind for ind in schema_indicators if ind in query_lower]
            print(f"     → Indicadores que coinciden: {matching_indicators}")
        
        # Verificar detección de idioma avanzada
        print("\n🌍 Verificando detección de idioma avanzada:")
        advanced_intention = service._detect_language_and_intention(query_lower)
        print(f"  🎯 Intención avanzada: {advanced_intention}")
        
        # Verificar detección inteligente
        print("\n🎯 Verificando detección inteligente:")
        if any(word in query_lower for word in ['qué', 'que', 'what', 'quelles', 'welche', 'quali', 'quais']):
            print("  ✅ Palabra interrogativa detectada")
            if any(word in query_lower for word in ['tabla', 'table', 'tables', 'tablas']):
                print("  ✅ Palabra 'tabla' detectada → list_tables")
            else:
                print("  ❌ Palabra 'tabla' NO detectada")
            if any(word in query_lower for word in ['hay', 'tiene', 'are', 'there', 'y a-t-il', 'gibt es', 'ci sono', 'existem']):
                print("  ✅ Palabra de existencia detectada → list_tables")
            else:
                print("  ❌ Palabra de existencia NO detectada")
        
        # Resultado final
        final_intention = service._detect_user_intention(query, query_terms)
        print(f"\n🎯 INTENCIÓN FINAL: {final_intention}")
        
        # Análisis del problema
        if final_intention != "list_tables" and any(word in query_lower for word in ['tabla', 'table', 'tables', 'tablas']):
            print("  ⚠️  PROBLEMA: Contiene 'tabla' pero no se detecta como list_tables")
            print("  💡 SOLUCIÓN: Revisar priorización de indicadores")
        elif final_intention == "list_tables":
            print("  ✅ CORRECTO: Se detecta como list_tables")
        
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(debug_intention_detection())
