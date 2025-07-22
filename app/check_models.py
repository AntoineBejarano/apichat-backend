# app/check_models.py

import sys, os

# 1) Inserta la carpeta raíz en sys.path
root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root not in sys.path:
    sys.path.insert(0, root)

from sqlalchemy.orm import configure_mappers

try:
    import app.models
    configure_mappers()
    print("✅ Todos los mappers configurados correctamente.")
except Exception as e:
    print("❌ Error al configurar mappers:\n", e, file=sys.stderr)
    sys.exit(1)
