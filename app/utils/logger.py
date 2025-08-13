import logging

# 🔧 FASE 9: Configurar logger principal sin duplicación
logger = logging.getLogger("apichat")
logger.setLevel(logging.INFO)

# 🔧 FASE 9: Evitar propagación al root para evitar duplicados
logger.propagate = False

# 🔧 FASE 9: Solo añadir handler si no existe ya
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
else:
    # 🔧 FASE 9: Log de debug para verificar configuración
    logger.debug("Logger 'apichat' ya tiene handlers configurados")
