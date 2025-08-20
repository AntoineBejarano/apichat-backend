#!/usr/bin/env python3
"""
🔧 Script de validación para configuraciones de sinónimos
─────────────────────────────────────────────────────────
Valida que todos los archivos JSON de configuración sean válidos
y tengan la estructura correcta.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List

def validate_json_file(file_path: Path) -> tuple[bool, List[str]]:
    """Valida un archivo JSON específico"""
    errors = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Validaciones específicas según el tipo de archivo
        if file_path.name == "synonyms.json":
            errors.extend(validate_synonyms_structure(data))
        elif file_path.name == "translations.json":
            errors.extend(validate_translations_structure(data))
        elif file_path.name == "domain_synonyms.json":
            errors.extend(validate_domain_synonyms_structure(data))
        elif file_path.name == "synonyms_config.json":
            errors.extend(validate_main_config_structure(data))
        
        return len(errors) == 0, errors
        
    except json.JSONDecodeError as e:
        errors.append(f"Error de sintaxis JSON: {e}")
        return False, errors
    except Exception as e:
        errors.append(f"Error inesperado: {e}")
        return False, errors

def validate_synonyms_structure(data: Dict[str, Any]) -> List[str]:
    """Valida la estructura del archivo de sinónimos"""
    errors = []
    
    required_sections = ["field_synonyms", "table_synonyms"]
    
    for section in required_sections:
        if section not in data:
            errors.append(f"Sección requerida '{section}' no encontrada")
        elif not isinstance(data[section], dict):
            errors.append(f"Sección '{section}' debe ser un diccionario")
        else:
            # Validar que cada entrada sea una lista
            for term, synonyms in data[section].items():
                if not isinstance(synonyms, list):
                    errors.append(f"Sinónimos para '{term}' en '{section}' debe ser una lista")
                elif not all(isinstance(s, str) for s in synonyms):
                    errors.append(f"Todos los sinónimos para '{term}' en '{section}' deben ser strings")
    
    return errors

def validate_translations_structure(data: Dict[str, Any]) -> List[str]:
    """Valida la estructura del archivo de traducciones"""
    errors = []
    
    required_sections = ["es_to_en", "en_to_es"]
    
    for section in required_sections:
        if section not in data:
            errors.append(f"Sección requerida '{section}' no encontrada")
        elif not isinstance(data[section], dict):
            errors.append(f"Sección '{section}' debe ser un diccionario")
        else:
            # Validar que cada traducción sea un string
            for term, translation in data[section].items():
                if not isinstance(translation, str):
                    errors.append(f"Traducción para '{term}' en '{section}' debe ser un string")
    
    return errors

def validate_domain_synonyms_structure(data: Dict[str, Any]) -> List[str]:
    """Valida la estructura del archivo de sinónimos por dominio"""
    errors = []
    
    if not isinstance(data, dict):
        errors.append("El archivo debe ser un diccionario")
        return errors
    
    for domain, domain_data in data.items():
        if not isinstance(domain_data, dict):
            errors.append(f"Dominio '{domain}' debe ser un diccionario")
        else:
            for table, synonyms in domain_data.items():
                if not isinstance(synonyms, list):
                    errors.append(f"Sinónimos para tabla '{table}' en dominio '{domain}' debe ser una lista")
                elif not all(isinstance(s, str) for s in synonyms):
                    errors.append(f"Todos los sinónimos para tabla '{table}' en dominio '{domain}' deben ser strings")
    
    return errors

def validate_main_config_structure(data: Dict[str, Any]) -> List[str]:
    """Valida la estructura del archivo de configuración principal"""
    errors = []
    
    required_fields = ["version", "description", "config_files", "settings"]
    
    for field in required_fields:
        if field not in data:
            errors.append(f"Campo requerido '{field}' no encontrado")
    
    if "config_files" in data and isinstance(data["config_files"], dict):
        required_config_files = ["general_synonyms", "translations", "domain_synonyms"]
        for config_file in required_config_files:
            if config_file not in data["config_files"]:
                errors.append(f"Archivo de configuración requerido '{config_file}' no encontrado")
    
    if "settings" in data and isinstance(data["settings"], dict):
        if "confidence_thresholds" in data["settings"]:
            thresholds = data["settings"]["confidence_thresholds"]
            if not isinstance(thresholds, dict):
                errors.append("'confidence_thresholds' debe ser un diccionario")
            else:
                required_thresholds = ["exact_match", "synonym_match", "fuzzy_match", "domain_match"]
                for threshold in required_thresholds:
                    if threshold not in thresholds:
                        errors.append(f"Umbral requerido '{threshold}' no encontrado")
                    elif not isinstance(thresholds[threshold], (int, float)):
                        errors.append(f"Umbral '{threshold}' debe ser un número")
    
    return errors

def main():
    """Función principal del script"""
    print("🔧 Validando configuraciones de sinónimos...")
    print("=" * 50)
    
    config_dir = Path("config")
    if not config_dir.exists():
        print("❌ Directorio 'config' no encontrado")
        sys.exit(1)
    
    # Archivos de configuración requeridos
    required_files = [
        "synonyms.json",
        "translations.json",
        "domain_synonyms.json",
        "synonyms_config.json"
    ]
    
    all_valid = True
    total_errors = 0
    
    for config_file in required_files:
        file_path = config_dir / config_file
        print(f"\n📁 Validando: {config_file}")
        
        if not file_path.exists():
            print(f"  ❌ Archivo no encontrado")
            all_valid = False
            total_errors += 1
            continue
        
        is_valid, errors = validate_json_file(file_path)
        
        if is_valid:
            print(f"  ✅ Válido")
        else:
            print(f"  ❌ {len(errors)} errores encontrados:")
            for error in errors:
                print(f"    - {error}")
            all_valid = False
            total_errors += len(errors)
    
    print("\n" + "=" * 50)
    if all_valid:
        print("🎉 ¡Todas las configuraciones son válidas!")
        sys.exit(0)
    else:
        print(f"❌ Se encontraron {total_errors} errores en total")
        sys.exit(1)

if __name__ == "__main__":
    main()
