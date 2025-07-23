import logging
import schemathesis
import pytest

# ────────────────────────────────────────────────────────
# Logging para ver todas las peticiones/respuestas de schemathesis
# ────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logging.getLogger("schemathesis").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)

# ────────────────────────────────────────────────────────
# Cargar OpenAPI desde FastAPI en localhost
# ────────────────────────────────────────────────────────
schema = schemathesis.from_uri(
    "http://127.0.0.1:8000/openapi.json"  # Asegúrate de que FastAPI está corriendo
)

@schema.parametrize()
def test_api_contract(case):
    """
    Schemathesis:
      - Genera peticiones válidas e inválidas (fuzzing).
      - Llama a la API (GET/POST/etc).
      - Valida status code y esquema JSON.
    """
    logging.info("▶️  Case: %s %s", case.method, case.full_path)
    if case.body is not None:
        logging.info("    Body: %r", case.body)
    if case.headers:
        logging.info("    Headers: %r", case.headers)

    response = case.call()
    logging.info("⬅️  Status: %s", response.status_code)
    logging.info("    Response body: %s", response.text)

    case.validate_response(response)

if __name__ == "__main__":
    # Ejecutar directamente como script
    pytest.main(["-vv", "-s", __file__])
