import logging

logger = logging.getLogger("apichat")
logger.setLevel(logging.INFO)

# Evita duplicados
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
