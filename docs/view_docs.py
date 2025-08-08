#!/usr/bin/env python3
"""
Servidor simple para visualizar la documentación markdown
Uso: python docs/view_docs.py
"""

import http.server
import socketserver
import os
import webbrowser
from pathlib import Path

class MarkdownHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

def main():
    # Cambiar al directorio docs
    docs_dir = Path(__file__).parent
    os.chdir(docs_dir)
    
    PORT = 8080
    
    with socketserver.TCPServer(("", PORT), MarkdownHandler) as httpd:
        print(f"🌐 Servidor de documentación iniciado en http://localhost:{PORT}")
        print(f"📁 Directorio: {docs_dir.absolute()}")
        print("\n📋 Archivos disponibles:")
        for file in docs_dir.glob("*.md"):
            print(f"   - {file.name}")
        print(f"\n🔗 Abre tu navegador en: http://localhost:{PORT}")
        print("⏹️  Presiona Ctrl+C para detener")
        
        # Abrir navegador automáticamente
        webbrowser.open(f'http://localhost:{PORT}')
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Servidor detenido")

if __name__ == "__main__":
    main()
