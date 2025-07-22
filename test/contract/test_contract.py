# tests/contract/test_contract.py

import logging
import schemathesis
import pytest

# ────────────────────────────────────────────────────────
# Logging para ver todas las peticiones/respuestas de schemathesis
# ────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
# El logger "schemathesis" controla la salida interna de la herramienta
logging.getLogger("schemathesis").setLevel(logging.INFO)
# También verás los logs HTTP de urllib3 si quieres más detalle:
logging.getLogger("urllib3").setLevel(logging.INFO)

# ────────────────────────────────────────────────────────
# Carga tu spec OpenAPI. Ajusta la ruta si tu openapi.json está en otro sitio.
# ────────────────────────────────────────────────────────
schema = schemathesis.from_path(
    "../openapi.json",
    base_url="http://127.0.0.1:8000",  # dónde corre tu API durante el test
)

@schema.parametrize()
def test_api_contract(case):
    """
    Schemathesis:
      - Genera peticiones válidas e inválidas (fuzzing).
      - Llama la API (GET/POST/etc).
      - Valida status code y esquema JSON.
    """
    # Imprime en consola el caso (método, ruta, payload)
    logging.info("▶️  Case: %s %s", case.method, case.full_path)
    if case.body is not None:
        logging.info("    Body: %r", case.body)
    if case.headers:
        logging.info("    Headers: %r", case.headers)

    response = case.call()
    # Imprime status y respuesta cruda
    logging.info("⬅️  Status: %s", response.status_code)
    logging.info("    Response body: %s", response.text)

    case.validate_response(response)

if __name__ == "__main__":
    # Para poder ejecutarlo directamente
    pytest.main(["-vv", "-s", __file__])



### to run it: pytest tests/contract/test_contract.py -vv -s
