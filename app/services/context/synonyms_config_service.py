"""
🔧 FASE 8: Servicio de configuración de sinónimos
─────────────────────────────────────────────────
Gestiona la carga y cache de configuraciones de sinónimos desde archivos JSON.
Permite configuración dinámica sin modificar código.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SynonymsConfigService:
    """Servicio para gestionar configuraciones de sinónimos desde archivos JSON"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_cache = {}
        self.last_loaded = {}
        self.cache_ttl = 300  # 5 minutos por defecto
        
        # Configuración por defecto
        self.default_config = {
            "confidence_thresholds": {
                "exact_match": 1.0,
                "synonym_match": 0.8,
                "fuzzy_match": 0.6,
                "domain_match": 0.7
            }
        }
        
        logger.info(f"[SynonymsConfigService] 🧠 Inicializado con directorio: {self.config_dir}")
        self._load_all_configs()
    
    def _load_all_configs(self) -> None:
        """Carga todas las configuraciones disponibles"""
        try:
            # Cargar configuración principal
            main_config = self._load_config_file("synonyms_config.json")
            if main_config:
                self.cache_ttl = main_config.get("settings", {}).get("cache_ttl_seconds", 300)
                logger.info(f"[SynonymsConfigService] ✅ Configuración principal cargada, TTL: {self.cache_ttl}s")
            
            # Cargar archivos de sinónimos
            config_files = [
                "synonyms.json",
                "translations.json", 
                "domain_synonyms.json"
            ]
            
            for config_file in config_files:
                self._load_config_file(config_file)
                
            logger.info(f"[SynonymsConfigService] ✅ Todas las configuraciones cargadas")
            
        except Exception as e:
            logger.error(f"[SynonymsConfigService] ❌ Error cargando configuraciones: {e}")
    
    def _load_config_file(self, filename: str) -> Optional[Dict[str, Any]]:
        """Carga un archivo de configuración específico"""
        try:
            file_path = self.config_dir / filename
            if not file_path.exists():
                logger.warning(f"[SynonymsConfigService] ⚠️ Archivo no encontrado: {filename}")
                return None
            
            # Verificar si necesitamos recargar
            if self._should_reload_file(filename, file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                self.config_cache[filename] = config_data
                self.last_loaded[filename] = datetime.now()
                
                logger.info(f"[SynonymsConfigService] ✅ Configuración cargada: {filename}")
                return config_data
            else:
                return self.config_cache.get(filename)
                
        except Exception as e:
            logger.error(f"[SynonymsConfigService] ❌ Error cargando {filename}: {e}")
            return None
    
    def _should_reload_file(self, filename: str, file_path: Path) -> bool:
        """Determina si un archivo necesita ser recargado"""
        if filename not in self.config_cache:
            return True
        
        if filename not in self.last_loaded:
            return True
        
        # Verificar TTL
        if datetime.now() - self.last_loaded[filename] > timedelta(seconds=self.cache_ttl):
            return True
        
        # Verificar si el archivo ha cambiado
        try:
            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if file_mtime > self.last_loaded[filename]:
                return True
        except:
            pass
        
        return False
    
    def get_field_synonyms(self, term: str) -> List[str]:
        """Obtiene sinónimos para un campo específico"""
        try:
            synonyms_data = self.config_cache.get("synonyms.json", {})
            field_synonyms = synonyms_data.get("field_synonyms", {})
            
            # Buscar coincidencia exacta
            if term in field_synonyms:
                return field_synonyms[term]
            
            # Buscar coincidencia en sinónimos
            for field, synonyms in field_synonyms.items():
                if term in synonyms:
                    return [field] + [s for s in synonyms if s != term]
            
            return []
            
        except Exception as e:
            logger.error(f"[SynonymsConfigService] ❌ Error obteniendo sinónimos para '{term}': {e}")
            return []
    
    def get_table_synonyms(self, term: str) -> List[str]:
        """Obtiene sinónimos para una tabla específica"""
        try:
            synonyms_data = self.config_cache.get("synonyms.json", {})
            table_synonyms = synonyms_data.get("table_synonyms", {})
            
            # Buscar coincidencia exacta
            if term in table_synonyms:
                return table_synonyms[term]
            
            # Buscar coincidencia en sinónimos
            for table, synonyms in table_synonyms.items():
                if term in synonyms:
                    return [table] + [s for s in synonyms if s != term]
            
            return []
            
        except Exception as e:
            logger.error(f"[SynonymsConfigService] ❌ Error obteniendo sinónimos de tabla para '{term}': {e}")
            return []
    
    def get_translation(self, term: str, from_lang: str = "es", to_lang: str = "en") -> Optional[str]:
        """Obtiene traducción de un término entre idiomas"""
        try:
            translations_data = self.config_cache.get("translations.json", {})
            
            if from_lang == "es" and to_lang == "en":
                return translations_data.get("es_to_en", {}).get(term)
            elif from_lang == "en" and to_lang == "es":
                return translations_data.get("en_to_es", {}).get(term)
            
            return None
            
        except Exception as e:
            logger.error(f"[SynonymsConfigService] ❌ Error traduciendo '{term}' de {from_lang} a {to_lang}: {e}")
            return None
    
    def get_domain_synonyms(self, term: str, domain: Optional[str] = None) -> List[str]:
        """Obtiene sinónimos específicos de un dominio"""
        try:
            domain_data = self.config_cache.get("domain_synonyms.json", {})
            
            if domain and domain in domain_data:
                # Buscar en dominio específico
                domain_synonyms = domain_data[domain]
                for table, synonyms in domain_synonyms.items():
                    if term in synonyms:
                        return [table] + [s for s in synonyms if s != term]
                    elif term == table:
                        return synonyms
            else:
                # Buscar en todos los dominios
                all_synonyms = []
                for domain_name, domain_synonyms in domain_data.items():
                    for table, synonyms in domain_synonyms.items():
                        if term in synonyms:
                            all_synonyms.extend([table] + [s for s in synonyms if s != term])
                        elif term == table:
                            all_synonyms.extend(synonyms)
                
                return list(set(all_synonyms))  # Remover duplicados
            
            return []
            
        except Exception as e:
            logger.error(f"[SynonymsConfigService] ❌ Error obteniendo sinónimos de dominio para '{term}': {e}")
            return []
    
    def get_all_synonyms_for_term(self, term: str) -> List[str]:
        """Obtiene todos los sinónimos disponibles para un término"""
        try:
            all_synonyms = []
            
            # Sinónimos de campos
            field_syns = self.get_field_synonyms(term)
            all_synonyms.extend(field_syns)
            
            # Sinónimos de tablas
            table_syns = self.get_table_synonyms(term)
            all_synonyms.extend(table_syns)
            
            # Sinónimos de dominios
            domain_syns = self.get_domain_synonyms(term)
            all_synonyms.extend(domain_syns)
            
            # Traducciones
            es_translation = self.get_translation(term, "es", "en")
            if es_translation:
                all_synonyms.append(es_translation)
            
            en_translation = self.get_translation(term, "en", "es")
            if en_translation:
                all_synonyms.append(en_translation)
            
            # Remover duplicados y el término original
            unique_synonyms = list(set(all_synonyms))
            if term in unique_synonyms:
                unique_synonyms.remove(term)
            
            return unique_synonyms
            
        except Exception as e:
            logger.error(f"[SynonymsConfigService] ❌ Error obteniendo todos los sinónimos para '{term}': {e}")
            return []
    
    def reload_configs(self) -> None:
        """Recarga todas las configuraciones"""
        logger.info("[SynonymsConfigService] 🔄 Recargando configuraciones...")
        self.config_cache.clear()
        self.last_loaded.clear()
        self._load_all_configs()
        logger.info("[SynonymsConfigService] ✅ Configuraciones recargadas")
    
    def get_config_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de la configuración cargada"""
        try:
            stats = {
                "total_config_files": len(self.config_cache),
                "cache_ttl_seconds": self.cache_ttl,
                "last_reload": max(self.last_loaded.values()) if self.last_loaded else None,
                "config_files": list(self.config_cache.keys())
            }
            
            # Contar sinónimos
            if "synonyms.json" in self.config_cache:
                field_count = len(self.config_cache["synonyms.json"].get("field_synonyms", {}))
                table_count = len(self.config_cache["synonyms.json"].get("table_synonyms", {}))
                stats["field_synonyms"] = field_count
                stats["table_synonyms"] = table_count
            
            # Contar traducciones
            if "translations.json" in self.config_cache:
                es_count = len(self.config_cache["translations.json"].get("es_to_en", {}))
                en_count = len(self.config_cache["translations.json"].get("en_to_es", {}))
                stats["translations_es_to_en"] = es_count
                stats["translations_en_to_es"] = en_count
            
            # Contar dominios
            if "domain_synonyms.json" in self.config_cache:
                domain_count = len(self.config_cache["domain_synonyms.json"])
                stats["domains"] = domain_count
            
            return stats
            
        except Exception as e:
            logger.error(f"[SynonymsConfigService] ❌ Error obteniendo estadísticas: {e}")
            return {"error": str(e)}
