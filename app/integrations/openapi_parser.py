import json
from typing import Any, Dict, List

def parse_openapi_to_functions(openapi: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Transforma un OpenAPI dict en una lista de funciones compatibles con OpenAI function calling.
    """

    if not isinstance(openapi, dict):
        raise ValueError("Invalid OpenAPI input: expected dict")

    if "paths" not in openapi:
        raise ValueError("Invalid OpenAPI: missing 'paths' section")

    functions = []
    seen_names = set()

    paths = openapi.get("paths", {})

    for path, methods in paths.items():
        for method, details in methods.items():
            if not isinstance(details, dict):
                continue

            func_name = details.get("operationId") or f"{method}_{path.strip('/').replace('/', '_')}"
            func_name = func_name.replace("-", "_")

            if func_name in seen_names:
                func_name += f"_{method}"
            seen_names.add(func_name)

            # --- Extraer parámetros de path/query ---
            parameters = details.get("parameters", [])
            properties = {}
            required = []

            for param in parameters:
                name = param.get("name")
                schema = param.get("schema", {})
                if not name or not schema:
                    continue

                properties[name] = {
                    "type": schema.get("type", "string"),
                    "description": param.get("description", "")
                }

                if param.get("required", False):
                    required.append(name)

            # --- Extraer parámetros del body (application/json) ---
            request_body = details.get("requestBody", {})
            content = request_body.get("content", {})
            json_schema = content.get("application/json", {}).get("schema", {})

            if "properties" in json_schema:
                for key, val in json_schema["properties"].items():
                    properties[key] = {
                        "type": val.get("type", "string"),
                        "description": val.get("description", "")
                    }
                if "required" in json_schema:
                    required.extend(json_schema["required"])

            func_def = {
                "name": func_name,
                "description": details.get("summary", f"Call {method.upper()} {path}"),
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": list(set(required)),
                },
                # Para posibles ejecuciones futuras:
                "metadata": {
                    "path": path,
                    "method": method.upper()
                }
            }

            functions.append(func_def)

    return functions
