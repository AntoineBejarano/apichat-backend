import logging
from typing import Dict, Any, List
from uuid import uuid4

logger = logging.getLogger(__name__)


class StrategyExportService:
    """
    Servicio para exportar/importar estrategias (workflows) entre el formato interno de APIchat
    y formatos externos como n8n o Make.
    """

    @staticmethod
    def to_n8n(graph_internal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convierte nuestro formato interno de grafo a un workflow de n8n.
        """
        logger.info("[StrategyExportService] 🔄 Convirtiendo grafo interno a formato n8n")

        # Estructura base de un workflow en n8n
        n8n_workflow = {
            "name": "Exported from APIchat",
            "nodes": [],
            "connections": {}
        }

        for node in graph_internal.get("nodes", []):
            node_id = str(uuid4())
            n8n_node = {
                "id": node_id,
                "name": node["data"].get("name", node["id"]),
                "type": f"custom.{node['type']}",
                "parameters": node["data"].get("params", {}),
                "position": [0, 0]  # El usuario ajustará en el editor visual
            }
            n8n_workflow["nodes"].append(n8n_node)

        for edge in graph_internal.get("edges", []):
            source_id = StrategyExportService._find_node_id_by_name(n8n_workflow, edge["from"])
            target_id = StrategyExportService._find_node_id_by_name(n8n_workflow, edge["to"])
            if source_id and target_id:
                n8n_workflow["connections"].setdefault(source_id, {}).setdefault("main", []).append([{"node": target_id}])

        return n8n_workflow

    @staticmethod
    def from_n8n(n8n_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convierte un workflow de n8n a nuestro formato interno.
        """
        logger.info("[StrategyExportService] 🔄 Importando desde formato n8n")

        nodes = []
        for node in n8n_json.get("nodes", []):
            nodes.append({
                "id": node["name"],
                "type": node.get("type", "").replace("custom.", ""),
                "data": {
                    "params": node.get("parameters", {})
                }
            })

        edges = []
        for source, conn_data in n8n_json.get("connections", {}).items():
            for conn in conn_data.get("main", []):
                if conn:
                    edges.append({
                        "from": source,
                        "to": conn[0].get("node")
                    })

        return {"nodes": nodes, "edges": edges}

    @staticmethod
    def to_make(graph_internal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convierte nuestro formato interno de grafo a un escenario de Make.
        """
        logger.info("[StrategyExportService] 🔄 Convirtiendo grafo interno a formato Make")

        make_scenario = {
            "name": "Exported from APIchat",
            "modules": [],
            "links": []
        }

        for node in graph_internal.get("nodes", []):
            module_id = str(uuid4())
            make_module = {
                "id": module_id,
                "name": node["data"].get("name", node["id"]),
                "type": node["type"],
                "parameters": node["data"].get("params", {})
            }
            make_scenario["modules"].append(make_module)

        for edge in graph_internal.get("edges", []):
            from_id = StrategyExportService._find_module_id_by_name(make_scenario, edge["from"])
            to_id = StrategyExportService._find_module_id_by_name(make_scenario, edge["to"])
            if from_id and to_id:
                make_scenario["links"].append({"from_module": from_id, "to_module": to_id})

        return make_scenario

    @staticmethod
    def from_make(make_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convierte un escenario de Make a nuestro formato interno.
        """
        logger.info("[StrategyExportService] 🔄 Importando desde formato Make")

        nodes = []
        for module in make_json.get("modules", []):
            nodes.append({
                "id": module["name"],
                "type": module.get("type", ""),
                "data": {
                    "params": module.get("parameters", {})
                }
            })

        edges = []
        for link in make_json.get("links", []):
            edges.append({
                "from": link.get("from_module"),
                "to": link.get("to_module")
            })

        return {"nodes": nodes, "edges": edges}

    # --- Métodos auxiliares ---
    @staticmethod
    def _find_node_id_by_name(workflow: Dict[str, Any], name: str) -> str:
        for node in workflow["nodes"]:
            if node["name"] == name:
                return node["id"]
        return None

    @staticmethod
    def _find_module_id_by_name(scenario: Dict[str, Any], name: str) -> str:
        for module in scenario["modules"]:
            if module["name"] == name:
                return module["id"]
        return None
