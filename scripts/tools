#!/usr/bin/env python3
"""
Script para generar documentación automática de APIchat
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_command(command, cwd=None):
    """Ejecuta un comando y retorna el resultado"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"✅ Comando ejecutado: {command}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error ejecutando comando: {command}")
        logger.error(f"Error: {e.stderr}")
        return None

def check_dependencies():
    """Verifica que las dependencias de documentación estén instaladas"""
    logger.info("🔍 Verificando dependencias de documentación...")
    
    required_packages = [
        "mkdocs",
        "mkdocs-material",
        "mkdocstrings",
        "mkdocstrings-python"
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.warning(f"⚠️ Paquetes faltantes: {missing_packages}")
        logger.info("Instalando dependencias...")
        install_cmd = f"pip install {' '.join(missing_packages)}"
        run_command(install_cmd)
    else:
        logger.info("✅ Todas las dependencias están instaladas")

def generate_api_docs():
    """Genera documentación automática de la API"""
    logger.info("📚 Generando documentación de la API...")
    
    # Crear directorio docs si no existe
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)
    
    # Generar documentación con mkdocstrings
    cmd = "mkdocs build --clean"
    result = run_command(cmd)
    
    if result:
        logger.info("✅ Documentación generada exitosamente")
        return True
    else:
        logger.error("❌ Error generando documentación")
        return False

def serve_docs():
    """Sirve la documentación localmente"""
    logger.info("🌐 Iniciando servidor de documentación...")
    logger.info("📖 Documentación disponible en: http://localhost:8001")
    
    cmd = "mkdocs serve --dev-addr=localhost:8001"
    try:
        subprocess.run(cmd, shell=True, check=True)
    except KeyboardInterrupt:
        logger.info("🛑 Servidor detenido por el usuario")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error iniciando servidor: {e}")

def build_docs():
    """Construye la documentación para producción"""
    logger.info("🏗️ Construyendo documentación para producción...")
    
    cmd = "mkdocs build --clean --site-dir=site"
    result = run_command(cmd)
    
    if result:
        logger.info("✅ Documentación construida en directorio 'site'")
        return True
    else:
        logger.error("❌ Error construyendo documentación")
        return False

def validate_docs():
    """Valida la documentación generada"""
    logger.info("🔍 Validando documentación...")
    
    # Verificar que el directorio site existe
    site_dir = Path("site")
    if not site_dir.exists():
        logger.error("❌ Directorio 'site' no encontrado")
        return False
    
    # Verificar archivos principales
    required_files = ["index.html", "404.html"]
    for file in required_files:
        if not (site_dir / file).exists():
            logger.error(f"❌ Archivo requerido no encontrado: {file}")
            return False
    
    logger.info("✅ Documentación validada correctamente")
    return True

def main():
    """Función principal"""
    logger.info("🚀 Iniciando generación de documentación...")
    
    # Verificar dependencias
    check_dependencies()
    
    # Generar documentación
    if generate_api_docs():
        # Construir para producción
        if build_docs():
            # Validar
            if validate_docs():
                logger.info("🎉 Documentación generada exitosamente!")
                
                # Preguntar si quiere servir localmente
                response = input("¿Quieres servir la documentación localmente? (y/n): ")
                if response.lower() in ['y', 'yes', 'sí', 'si']:
                    serve_docs()
            else:
                logger.error("❌ Error validando documentación")
                sys.exit(1)
        else:
            logger.error("❌ Error construyendo documentación")
            sys.exit(1)
    else:
        logger.error("❌ Error generando documentación")
        sys.exit(1)

if __name__ == "__main__":
    main() 