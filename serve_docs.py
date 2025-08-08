#!/usr/bin/env python3
"""
Script para servir la documentación de MkDocs
Uso: python serve_docs.py
"""

import subprocess
import sys
import webbrowser
import time
from pathlib import Path

def main():
    """Función principal para servir la documentación"""
    print("🚀 Iniciando servidor de documentación MkDocs...")
    
    # Verificar que estamos en el directorio correcto
    if not Path("mkdocs.yml").exists():
        print("❌ Error: No se encontró mkdocs.yml en el directorio actual")
        print("💡 Asegúrate de estar en el directorio raíz del proyecto")
        sys.exit(1)
    
    # Verificar que MkDocs está instalado
    try:
        subprocess.run(["mkdocs", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Error: MkDocs no está instalado")
        print("💡 Instala con: pip install mkdocs mkdocs-material mkdocstrings mkdocstrings-python")
        sys.exit(1)
    
    print("📚 Documentación disponible en: http://localhost:8001")
    print("🔍 Swagger UI en: http://localhost:8000/docs")
    print("📖 ReDoc en: http://localhost:8000/redoc")
    print("\n📋 Archivos de documentación:")
    
    # Listar archivos de documentación
    docs_dir = Path("docs")
    if docs_dir.exists():
        for file in docs_dir.rglob("*.md"):
            print(f"   - {file.relative_to(docs_dir)}")
    
    print("\n🌐 Abriendo navegador automáticamente...")
    
    # Abrir navegador después de un breve delay
    def open_browser():
        time.sleep(2)
        webbrowser.open("http://localhost:8001")
    
    import threading
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    try:
        # Iniciar servidor MkDocs
        print("⏹️  Presiona Ctrl+C para detener el servidor")
        subprocess.run([
            "mkdocs", "serve", 
            "--dev-addr=localhost:8001",
            "--livereload"
        ], check=True)
    except KeyboardInterrupt:
        print("\n👋 Servidor detenido por el usuario")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error iniciando servidor: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
