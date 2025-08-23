import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class ResourceProposalHelper:
    """Ayuda a generar propuestas de recursos para el modo Guided"""
    
    @staticmethod
    def should_propose_resources(user_message: str) -> bool:
        """
        Determina si se debe proponer recursos basándose en el mensaje del usuario.
        
        Args:
            user_message: Mensaje del usuario
            
        Returns:
            True si se debe proponer recursos, False en caso contrario
        """
        message_lower = user_message.lower()
        
        # Palabras clave que sugieren una tarea específica
        task_keywords = [
            "buscar", "encontrar", "obtener", "extraer", "consultar", "analizar",
            "crear", "insertar", "actualizar", "modificar", "eliminar", "borrar",
            "generar", "calcular", "resumir", "comparar", "filtrar", "ordenar",
            "agrupar", "contar", "sumar", "promedio", "máximo", "mínimo",
            "reporte", "dashboard", "exportar", "importar", "sincronizar"
        ]
        
        # Palabras clave que sugieren exploración general
        exploration_keywords = [
            "qué hay", "qué contiene", "muéstrame", "explora", "investiga",
            "descubre", "revisa", "examina", "explora", "navega"
        ]
        
        # Si el mensaje contiene palabras de tarea específica, proponer recursos
        if any(keyword in message_lower for keyword in task_keywords):
            return True
        
        # Si el mensaje es muy general o solo exploratorio, no proponer
        if any(keyword in message_lower for keyword in exploration_keywords):
            return False
        
        # Si el mensaje es corto o muy general, no proponer
        if len(user_message.split()) <= 3:
            return False
        
        # Por defecto, proponer si el mensaje parece ser una pregunta o solicitud
        return "?" in user_message or any(word in message_lower for word in ["puedes", "ayúdame", "necesito", "quiero"])
    
    @staticmethod
    def prepare_database_info(db_ids: List[str]) -> List[Dict[str, Any]]:
        """Prepara información de las bases de datos para el selector de recursos"""
        all_dbs = []
        for db_id in db_ids:
            db_info = {
                'id': str(db_id),
                'name': f"Database {db_id[:8]}",
                'description': f"Database connection {db_id[:8]}",
                'table_count': 0,  # Se puede mejorar obteniendo metadata real
                'size_mb': 0,
                'last_updated': None,
                'is_readonly': True,
                'has_comments': False,
                'has_constraints': False,
                'has_indexes': False
            }
            all_dbs.append(db_info)
        return all_dbs
    
    @staticmethod
    def prepare_application_info(apps: List[Any]) -> List[Dict[str, Any]]:
        """Prepara información de las aplicaciones para el selector de recursos"""
        all_apps = []
        for app in apps:
            app_info = {
                'id': str(app.id),
                'name': app.name,
                'description': app.description or f"Application {app.name}",
                'api_count': len(app.functions) if hasattr(app, 'functions') else 0,
                'last_updated': app.updated_at.isoformat() if hasattr(app, 'updated_at') else None,
                'requires_auth': True,
                'has_rate_limiting': True,
                'has_openapi_spec': True,
                'has_examples': False,
                'has_descriptions': True
            }
            all_apps.append(app_info)
        return all_apps
    
    @staticmethod
    def format_proposal_options(proposals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Formatea las opciones de propuesta para la UI"""
        formatted_options = []
        for i, proposal in enumerate(proposals, 1):
            option = {
                "id": f"guided_option_{i}",
                "label": f"Opción {i}: {proposal['database']['name']} + {proposal['application']['name']}",
                "description": f"Score: {proposal['combined_score']:.2f} - {', '.join(proposal['selection_reasons'][:3])}",
                "action": f"guided_option_{i}",
                "data": {
                    "database_id": proposal['database']['id'],
                    "application_id": proposal['application']['id'],
                    "combined_score": proposal['combined_score'],
                    "reasons": proposal['selection_reasons']
                }
            }
            formatted_options.append(option)
        
        # Añadir opciones adicionales
        formatted_options.extend([
            {
                "id": "see_more",
                "label": "Ver más opciones",
                "description": "Explorar más combinaciones de recursos",
                "action": "see_more"
            },
            {
                "id": "explore_only",
                "label": "Solo explorar",
                "description": "Continuar en modo Explorer sin cambiar a Guided",
                "action": "explore_only"
            }
        ])
        
        return formatted_options
