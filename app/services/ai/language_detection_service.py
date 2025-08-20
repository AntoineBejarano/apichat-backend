"""
🔧 FASE 1: Servicio de detección de idioma y búsqueda difusa
────────────────────────────────────────────────────────────
Implementa detección automática de idioma y búsqueda con coincidencia difusa
para mejorar el Fast Schema Path en múltiples idiomas.
"""

import logging
from typing import List, Dict, Tuple, Optional
from langdetect import detect, DetectorFactory
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

# Configurar detector de idioma para ser determinístico
DetectorFactory.seed = 0

class LanguageDetectionService:
    """Servicio para detección de idioma y búsqueda difusa"""
    
    def __init__(self):
        self.language_mappings = {
            'es': 'en',  # Español → Inglés
            'fr': 'en',  # Francés → Inglés
            'de': 'en',  # Alemán → Inglés
            'it': 'en',  # Italiano → Inglés
            'pt': 'en',  # Portugués → Inglés
            'ru': 'en',  # Ruso → Inglés
            'ja': 'en',  # Japonés → Inglés
            'zh': 'en',  # Chino → Inglés
            'ko': 'en',  # Coreano → Inglés
            'ar': 'en',  # Árabe → Inglés
        }
        
        # Palabras clave comunes en diferentes idiomas
        self.keyword_translations = {
            'es': {
                'tabla': 'table',
                'esquema': 'schema',
                'base de datos': 'database',
                'datos': 'data',
                'columna': 'column',
                'registro': 'record',
                'consulta': 'query',
                'seleccionar': 'select',
                'donde': 'where',
                'ordenar': 'order',
                'agrupar': 'group',
                'contar': 'count',
                'sumar': 'sum',
                'promedio': 'average',
                'máximo': 'max',
                'mínimo': 'min'
            },
            'fr': {
                'table': 'table',
                'schéma': 'schema',
                'base de données': 'database',
                'données': 'data',
                'colonne': 'column',
                'enregistrement': 'record',
                'requête': 'query',
                'sélectionner': 'select',
                'où': 'where',
                'trier': 'order',
                'grouper': 'group',
                'compter': 'count',
                'somme': 'sum',
                'moyenne': 'average',
                'maximum': 'max',
                'minimum': 'min'
            },
            'de': {
                'tabelle': 'table',
                'schema': 'schema',
                'datenbank': 'database',
                'daten': 'data',
                'spalte': 'column',
                'datensatz': 'record',
                'abfrage': 'query',
                'auswählen': 'select',
                'wo': 'where',
                'sortieren': 'order',
                'gruppieren': 'group',
                'zählen': 'count',
                'summe': 'sum',
                'durchschnitt': 'average',
                'maximum': 'max',
                'minimum': 'min'
            }
        }
    
    def detect_language(self, text: str) -> str:
        """
        Detecta el idioma del texto proporcionado
        
        Args:
            text: Texto para analizar
            
        Returns:
            Código de idioma ISO 639-1 (ej: 'es', 'en', 'fr')
        """
        try:
            if not text or len(text.strip()) < 3:
                return 'en'  # Default a inglés para textos muy cortos
            
            detected_lang = detect(text)
            logger.debug(f"[LanguageDetectionService] Idioma detectado: {detected_lang} para texto: '{text[:50]}...'")
            return detected_lang
            
        except Exception as e:
            logger.warning(f"[LanguageDetectionService] Error detectando idioma: {e}, usando inglés por defecto")
            return 'en'
    
    def translate_keywords(self, text: str, source_lang: str) -> str:
        """
        Traduce palabras clave del idioma detectado al inglés
        
        Args:
            text: Texto original
            source_lang: Idioma de origen
            
        Returns:
            Texto con palabras clave traducidas
        """
        if source_lang == 'en':
            return text
        
        translations = self.keyword_translations.get(source_lang, {})
        translated_text = text.lower()
        
        for original, translation in translations.items():
            translated_text = translated_text.replace(original, translation)
        
        logger.debug(f"[LanguageDetectionService] Traducción de '{source_lang}' a 'en': '{text[:50]}...' → '{translated_text[:50]}...'")
        return translated_text
    
    def fuzzy_search(self, query: str, candidates: List[str], threshold: float = 70.0) -> List[Tuple[str, float]]:
        """
        Realiza búsqueda difusa entre la consulta y una lista de candidatos
        
        Args:
            query: Consulta de búsqueda
            candidates: Lista de candidatos para buscar
            threshold: Umbral mínimo de similitud (0-100)
            
        Returns:
            Lista de tuplas (candidato, score) ordenadas por relevancia
        """
        try:
            # Usar rapidfuzz para búsqueda difusa
            results = process.extract(
                query.lower(),
                [c.lower() for c in candidates],
                scorer=fuzz.token_sort_ratio,
                limit=len(candidates)
            )
            
            # Filtrar por umbral y ordenar por score
            filtered_results = [
                (candidates[i], score) 
                for i, score in results 
                if score >= threshold
            ]
            
            # Ordenar por score descendente
            filtered_results.sort(key=lambda x: x[1], reverse=True)
            
            logger.debug(f"[LanguageDetectionService] Búsqueda difusa: '{query}' → {len(filtered_results)} resultados (umbral: {threshold})")
            return filtered_results
            
        except Exception as e:
            logger.error(f"[LanguageDetectionService] Error en búsqueda difusa: {e}")
            return []
    
    def enhance_query_for_schema_search(self, query: str) -> Dict[str, str]:
        """
        Mejora la consulta para búsqueda en esquema usando detección de idioma
        
        Args:
            query: Consulta original del usuario
            
        Returns:
            Dict con consulta original, idioma detectado y consulta mejorada
        """
        # Detectar idioma
        detected_lang = self.detect_language(query)
        
        # Traducir palabras clave si no es inglés
        enhanced_query = self.translate_keywords(query, detected_lang)
        
        # Añadir sinónimos y variaciones
        enhanced_query = self._add_synonyms(enhanced_query)
        
        result = {
            'original_query': query,
            'detected_language': detected_lang,
            'enhanced_query': enhanced_query,
            'translation_applied': detected_lang != 'en'
        }
        
        logger.info(f"[LanguageDetectionService] Consulta mejorada: '{query[:50]}...' → '{enhanced_query[:50]}...' (idioma: {detected_lang})")
        return result
    
    def _add_synonyms(self, query: str) -> str:
        """
        Añade sinónimos y variaciones a la consulta para mejorar la búsqueda
        """
        synonyms = {
            'table': 'table,tabla,table_name,table_name',
            'schema': 'schema,esquema,database_schema',
            'database': 'database,base,base de datos,db',
            'data': 'data,datos,information,info',
            'column': 'column,columna,field,campo',
            'record': 'record,registro,row,fila',
            'query': 'query,consulta,search,buscar',
            'select': 'select,seleccionar,get,obtener',
            'where': 'where,donde,filter,filtro',
            'count': 'count,contar,number,numero',
            'sum': 'sum,sumar,total,adicionar',
            'average': 'average,promedio,mean,media',
            'max': 'max,maximum,maximo,mayor',
            'min': 'min,minimum,minimo,menor'
        }
        
        enhanced = query
        for word, synonym_list in synonyms.items():
            if word in enhanced:
                enhanced = enhanced.replace(word, synonym_list)
        
        return enhanced
    
    def get_search_suggestions(self, partial_query: str, language: str = 'en') -> List[str]:
        """
        Genera sugerencias de búsqueda basadas en la consulta parcial
        
        Args:
            partial_query: Consulta parcial del usuario
            language: Idioma preferido para las sugerencias
            
        Returns:
            Lista de sugerencias de búsqueda
        """
        suggestions = []
        
        if language == 'es':
            suggestions = [
                f"Mostrar {partial_query}",
                f"Listar {partial_query}",
                f"Buscar en {partial_query}",
                f"Explorar {partial_query}",
                f"Ver estructura de {partial_query}"
            ]
        elif language == 'fr':
            suggestions = [
                f"Afficher {partial_query}",
                f"Lister {partial_query}",
                f"Rechercher dans {partial_query}",
                f"Explorer {partial_query}",
                f"Voir la structure de {partial_query}"
            ]
        elif language == 'de':
            suggestions = [
                f"{partial_query} anzeigen",
                f"{partial_query} auflisten",
                f"In {partial_query} suchen",
                f"{partial_query} erkunden",
                f"Struktur von {partial_query} anzeigen"
            ]
        else:  # English
            suggestions = [
                f"Show {partial_query}",
                f"List {partial_query}",
                f"Search in {partial_query}",
                f"Explore {partial_query}",
                f"View structure of {partial_query}"
            ]
        
        return suggestions
