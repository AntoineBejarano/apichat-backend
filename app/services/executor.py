import json
import requests
import logging
from typing import Any
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.function_model import Function
from app.core.servicefactory import ServiceFactory  # ✅ nuevo import

logger = logging.getLogger(__name__)


class FunctionExecutor:
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.db: Session = factory.db
        self.user_id: int = factory.user.id

    def execute_by_name(self, name: str, arguments: str) -> Any:
        logger.info(f"[FunctionExecutor] 🚀 Ejecutando función '{name}' para user {self.user_id}")
        try:
            args = json.loads(arguments)
        except json.JSONDecodeError:
            logger.warning("[FunctionExecutor] ❌ Argumentos no son JSON válido")
            raise HTTPException(status_code=400, detail="Invalid JSON en los argumentos.")

        fn: Function = (
            self.db.query(Function)
            .filter(Function.user_id == self.user_id, Function.name == name, Function.active == True)
            .first()
        )

        if not fn:
            logger.warning(f"[FunctionExecutor] ❌ Función '{name}' no encontrada para user {self.user_id}")
            raise HTTPException(status_code=404, detail=f"Function '{name}' no encontrada.")

        if fn.execution_type == "python":
            logger.debug("[FunctionExecutor] 🐍 Tipo de ejecución: Python")
            return self._exec_python(fn, args)
        elif fn.execution_type == "http":
            logger.debug("[FunctionExecutor] 🌐 Tipo de ejecución: HTTP")
            return self._exec_http(fn, args)
        else:
            logger.error(f"[FunctionExecutor] ❌ Tipo de ejecución '{fn.execution_type}' no soportado.")
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de ejecución '{fn.execution_type}' no soportado."
            )

    def _exec_python(self, fn: Function, args: dict) -> Any:
        local_scope = {}
        try:
            exec(fn.code, {}, local_scope)
            if fn.name not in local_scope or not callable(local_scope[fn.name]):
                logger.error("[FunctionExecutor] ❌ Código Python mal definido")
                raise HTTPException(status_code=500, detail="Función mal definida.")
            result = local_scope[fn.name](**args)
            logger.debug("[FunctionExecutor] ✅ Python ejecutado correctamente")
            return result
        except Exception as e:
            logger.exception("[FunctionExecutor] ❌ Error al ejecutar Python")
            raise HTTPException(status_code=500, detail=f"Error al ejecutar: {str(e)}")

    def _exec_http(self, fn: Function, args: dict) -> Any:
        url = self._render_template(fn.url, args)
        headers = {k: self._render_template(v, args) for k, v in (fn.headers or {}).items()}
        body = self._render_dict(fn.body or {}, args)

        try:
            logger.debug(f"[FunctionExecutor] 🌍 Realizando request a {url}")
            response = requests.request(fn.method or "POST", url, headers=headers, json=body)
            logger.debug("[FunctionExecutor] ✅ Respuesta HTTP recibida")
            return response.json()
        except Exception as e:
            logger.exception("[FunctionExecutor] ❌ Error en ejecución HTTP")
            raise HTTPException(status_code=500, detail=f"Error HTTP: {str(e)}")

    def _render_template(self, template: str, variables: dict) -> str:
        try:
            return template.format(**variables)
        except Exception as e:
            logger.warning(f"[FunctionExecutor] ❌ Error renderizando template: {str(e)}")
            return template

    def _render_dict(self, template_dict: dict, variables: dict) -> dict:
        def _render(val):
            if isinstance(val, str):
                return self._render_template(val, variables)
            elif isinstance(val, dict):
                return self._render_dict(val, variables)
            elif isinstance(val, list):
                return [_render(v) for v in val]
            return val

        return {k: _render(v) for k, v in template_dict.items()}
