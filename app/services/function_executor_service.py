import json
import requests
import logging
from typing import Any
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.function_model import Function
from app.services.proxy_service import ProxyService
from app.models.strategy_model import Strategy

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class FunctionExecutor:
    def __init__(self, factory: "ServiceFactory"):
        self.factory = factory
        self.db: Session = factory.db
        self.user_id: int = factory.user.id
        self.proxy_service: ProxyService = factory.get_proxy_service()

        logger.info("[FunctionExecutor] Inicializado para user_id=%s", self.user_id)

    def execute_by_id(self, fn_id: int, arguments: dict | str) -> Any:
        logger.info("[FunctionExecutor] 🔍 Buscando función con id=%s", fn_id)
        fn: Function = (
            self.db.query(Function)
            .filter(Function.user_id == self.user_id, Function.id == fn_id, Function.active == True)
            .first()
        )
        if not fn:
            logger.warning("[FunctionExecutor] ❌ Función no encontrada con id=%s", fn_id)
            raise HTTPException(status_code=404, detail=f"Function id={fn_id} no encontrada.")

        # 📦 Asegurarse de tener argumentos como dict
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
        except Exception as e:
            logger.error("[FunctionExecutor] ❌ Argumentos inválidos: %s", str(e))
            raise HTTPException(status_code=400, detail="Argumentos inválidos.")

        logger.info("[FunctionExecutor] 🚀 Ejecutando función '%s' con tipo %s", fn.name, fn.execution_type)

        if fn.execution_type == "python":
            return self._exec_python(fn, args)
        elif fn.execution_type == "http":
            return self._exec_http(fn, args)
        else:
            logger.error("[FunctionExecutor] ❌ Tipo de ejecución no soportado: %s", fn.execution_type)
            raise HTTPException(status_code=400, detail="Tipo de ejecución no soportado.")

    def _exec_python(self, fn: Function, args: dict) -> Any:
        local_scope = {}
        try:
            exec(fn.code, {}, local_scope)
            if fn.name not in local_scope or not callable(local_scope[fn.name]):
                logger.error("[FunctionExecutor] ❌ Función Python '%s' no definida correctamente", fn.name)
                raise HTTPException(status_code=500, detail="Función mal definida.")
            logger.debug("[FunctionExecutor] ▶ Ejecutando código Python")
            result = local_scope[fn.name](**args)
            logger.info("[FunctionExecutor] ✅ Función Python ejecutada correctamente")
            return result
        except Exception as e:
            logger.exception("[FunctionExecutor] ❌ Error al ejecutar función Python")
            raise HTTPException(status_code=500, detail=f"Error en ejecución Python: {str(e)}")

    def _exec_http(self, fn: Function, args: dict) -> Any:
        try:
            url = self._render_template(fn.url, args)
            headers = {k: self._render_template(v, args) for k, v in (fn.headers or {}).items()}
            body = self._render_dict(fn.body or {}, args)

            proxies = None
            if fn.proxy_id:
                proxy = self.proxy_service.get_by_id(fn.proxy_id)
                if proxy:
                    proxies = {
                        "http": proxy.base_url,
                        "https": proxy.base_url
                    }
                    logger.info("[FunctionExecutor] 🌐 Usando proxy: %s", proxy.base_url)
                else:
                    logger.warning("[FunctionExecutor] ⚠️ Proxy ID %s no válido para función %s", fn.proxy_id, fn.name)

            logger.info("[FunctionExecutor] 🌍 Haciendo request %s a %s", fn.method or "POST", url)
            response = requests.request(
                method=fn.method or "POST",
                url=url,
                headers=headers,
                json=body,
                proxies=proxies,
                timeout=20
            )

            logger.info("[FunctionExecutor] ✅ Respuesta HTTP status=%s", response.status_code)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.exception("[FunctionExecutor] ❌ Error HTTP en función '%s'", fn.name)
            raise HTTPException(status_code=500, detail=f"Error HTTP: {str(e)}")

    def _render_template(self, template: str, variables: dict) -> str:
        try:
            return template.format(**variables)
        except Exception as e:
            logger.warning("[FunctionExecutor] ⚠️ Error renderizando template: %s", str(e))
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

    def run_strategy(self, strategy: Strategy) -> list[dict]:
        """
        Ejecuta todos los pasos definidos en una estrategia.
        Cada paso llama a una función con sus argumentos.
        Retorna una lista con el resultado de cada paso.
        """
        logger.info("[FunctionExecutor] 🧠 Ejecutando estrategia: %s (%s)", strategy.name, strategy.id)

        results = []
        for index, step in enumerate(strategy.steps):
            function_id = step.get("function_id")
            inputs = step.get("inputs", {})
            logger.info("[FunctionExecutor] ▶ Paso %d: Ejecutando función ID=%s con inputs=%s", index + 1, function_id, inputs)

            try:
                result = self.execute_by_id(function_id, inputs)
                results.append({
                    "step": index + 1,
                    "function_id": str(function_id),
                    "status": "success",
                    "result": result
                })
                logger.info("[FunctionExecutor] ✅ Paso %d completado", index + 1)

            except HTTPException as http_exc:
                logger.warning("[FunctionExecutor] ⚠️ Paso %d falló: %s", index + 1, http_exc.detail)
                results.append({
                    "step": index + 1,
                    "function_id": str(function_id),
                    "status": "error",
                    "error": http_exc.detail
                })
                break  # 🔁 Parar la ejecución si un paso falla

            except Exception as e:
                logger.exception("[FunctionExecutor] ❌ Error inesperado en el paso %d", index + 1)
                results.append({
                    "step": index + 1,
                    "function_id": str(function_id),
                    "status": "error",
                    "error": str(e)
                })
                break

        logger.info("[FunctionExecutor] 🧩 Estrategia finalizada con %d pasos ejecutados", len(results))
        return results