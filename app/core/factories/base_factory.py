"""
🏭 Base Service Factory: Factory base para todas las sub-factories

Proporciona funcionalidades comunes como lazy loading, cache local
y gestión de servicios para todas las factories especializadas.
"""

import logging
from typing import Any, Dict, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

# Type variable para servicios
ServiceType = TypeVar('ServiceType')


class BaseServiceFactory:
    """
    🏭 Factory base con funcionalidades comunes
    
    Funcionalidades:
    - Lazy loading con cache local
    - Gestión de errores robusta
    - Logging de inicialización
    - Cache de servicios por nombre
    """
    
    def __init__(self, main_factory):
        """
        Inicializa la factory base
        
        Args:
            main_factory: Referencia al ServiceFactory principal
        """
        self.main_factory = main_factory
        self._services: Dict[str, Any] = {}
        self._initialization_errors: Dict[str, str] = {}
        
        logger.debug(f"[{self.__class__.__name__}] 🚀 Inicializada")
    
    def _get_or_create_service(
        self, 
        service_class: Type[ServiceType], 
        service_name: str,
        *args, 
        **kwargs
    ) -> Optional[ServiceType]:
        """
        Obtiene o crea un servicio con lazy loading y cache local
        
        Args:
            service_class: Clase del servicio a instanciar
            service_name: Nombre del servicio para cache
            *args: Argumentos posicionales para el servicio
            **kwargs: Argumentos de palabra clave para el servicio
            
        Returns:
            Instancia del servicio o None si falla
        """
        try:
            # Verificar si ya está en cache
            if service_name in self._services:
                logger.debug(f"[{self.__class__.__name__}] 📦 Servicio '{service_name}' obtenido desde cache")
                return self._services[service_name]
            
            # Verificar si hubo error previo
            if service_name in self._initialization_errors:
                logger.warning(f"[{self.__class__.__name__}] ⚠️ Servicio '{service_name}' falló previamente: {self._initialization_errors[service_name]}")
                return None
            
            # Crear nueva instancia
            logger.info(f"[{self.__class__.__name__}] 🔨 Creando servicio '{service_name}'")
            
            # 🔧 FIX: Verificar si el servicio necesita el factory
            use_factory = kwargs.pop('use_factory', True)
            
            if use_factory and (args or kwargs):
                service_instance = service_class(self.main_factory, *args, **kwargs)
            elif use_factory:
                service_instance = service_class(self.main_factory)
            else:
                # 🔧 FIX: Servicios que no necesitan factory (como RedisSchemaCache)
                service_instance = service_class(*args, **kwargs)
            
            # Almacenar en cache
            self._services[service_name] = service_instance
            
            logger.info(f"[{self.__class__.__name__}] ✅ Servicio '{service_name}' creado exitosamente")
            return service_instance
            
        except Exception as e:
            error_msg = f"Error creando servicio '{service_name}': {str(e)}"
            logger.error(f"[{self.__class__.__name__}] ❌ {error_msg}")
            
            # Almacenar error para evitar reintentos
            self._initialization_errors[service_name] = str(e)
            
            return None
    
    def _clear_service_cache(self, service_name: Optional[str] = None):
        """
        Limpia el cache de servicios
        
        Args:
            service_name: Nombre específico del servicio a limpiar, o None para limpiar todo
        """
        try:
            if service_name:
                if service_name in self._services:
                    del self._services[service_name]
                    logger.debug(f"[{self.__class__.__name__}] 🧹 Cache limpiado para servicio '{service_name}'")
            else:
                self._services.clear()
                self._initialization_errors.clear()
                logger.info(f"[{self.__class__.__name__}] 🧹 Cache completo limpiado")
                
        except Exception as e:
            logger.warning(f"[{self.__class__.__name__}] ⚠️ Error limpiando cache: {e}")
    
    def _get_service_info(self) -> Dict[str, Any]:
        """
        Obtiene información sobre los servicios en cache
        
        Returns:
            Diccionario con información de servicios
        """
        try:
            return {
                "factory_class": self.__class__.__name__,
                "cached_services": list(self._services.keys()),
                "service_count": len(self._services),
                "initialization_errors": self._initialization_errors.copy(),
                "error_count": len(self._initialization_errors)
            }
        except Exception as e:
            logger.warning(f"[{self.__class__.__name__}] ⚠️ Error obteniendo info: {e}")
            return {"error": str(e)}
    
    def _reset_factory(self):
        """
        Resetea la factory a su estado inicial
        """
        try:
            self._services.clear()
            self._initialization_errors.clear()
            logger.info(f"[{self.__class__.__name__}] 🔄 Factory reseteada")
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] ❌ Error reseteando factory: {e}")
    
    def __repr__(self):
        """Representación string de la factory"""
        return f"<{self.__class__.__name__}(services={len(self._services)}, errors={len(self._initialization_errors)})>"
