import logging
import time
import threading
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PersistentServiceCache:
    """Cache persistente para servicios que mantiene instancias vivas entre requests"""
    
    def __init__(self, max_services: int = 50, ttl_hours: int = 24):
        self.max_services = max_services
        self.ttl_hours = ttl_hours
        
        # Cache de servicios
        self._services: Dict[str, Any] = {}
        self._service_factories: Dict[str, Callable] = {}
        self._timestamps: Dict[str, float] = {}
        self._access_count: Dict[str, int] = {}
        self._last_accessed: Dict[str, float] = {}
        self._service_stats: Dict[str, Dict] = {}
        
        # Lock para thread safety
        self._lock = threading.RLock()
        
        # Inicializar thread de limpieza
        self._cleanup_thread = None
        self._stop_cleanup = False
        self._start_cleanup_thread()
    
    def register_service(self, service_name: str, factory_func: Callable):
        """Registra una función factory para un servicio"""
        with self._lock:
            self._service_factories[service_name] = factory_func
            logger.debug(f"[PersistentServiceCache] 📝 Servicio registrado: {service_name}")
    
    def get_service(self, service_name: str) -> Optional[Any]:
        """Obtiene un servicio del cache, creándolo si es necesario"""
        with self._lock:
            # Verificar si ya tenemos el servicio en cache
            if service_name in self._services:
                service = self._services[service_name]
                
                # Verificar si ha expirado
                if self._is_expired(service_name):
                    logger.info(f"[PersistentServiceCache] ⏰ Servicio expirado: {service_name}")
                    self._remove_service(service_name)
                else:
                    # Actualizar estadísticas
                    self._update_access_stats(service_name, "cache_hit")
                    self._last_accessed[service_name] = time.time()
                    logger.debug(f"[PersistentServiceCache] 🔥 Cache HIT para servicio: {service_name}")
                    return service
            
            # Cache MISS - crear nuevo servicio
            logger.info(f"[PersistentServiceCache] 🆕 Cache MISS para servicio: {service_name}")
            
            if service_name not in self._service_factories:
                logger.warning(f"[PersistentServiceCache] ⚠️ No hay factory registrada para: {service_name}")
                return None
            
            try:
                start_time = time.time()
                
                # Crear servicio usando la factory
                service = self._service_factories[service_name]()
                
                if service:
                    creation_time = time.time() - start_time
                    
                    # Guardar en cache
                    self._add_service_to_cache(service_name, service, creation_time)
                    self._update_access_stats(service_name, "created")
                    
                    logger.info(f"[PersistentServiceCache] ✅ Servicio creado: {service_name} en {creation_time:.3f}s")
                    return service
                else:
                    logger.error(f"[PersistentServiceCache] ❌ Factory no pudo crear servicio: {service_name}")
                    return None
                    
            except Exception as e:
                logger.error(f"[PersistentServiceCache] ❌ Error creando servicio {service_name}: {e}")
                return None
    
    def get_db_instance(self, user_id: str, db_id: str) -> Optional[Any]:
        """Obtiene una instancia de base de datos del cache"""
        try:
            cache_key = f"db_instance_{user_id}_{db_id}"
            if cache_key in self._services:
                service = self._services[cache_key]
                
                # Verificar si ha expirado
                if self._is_expired(cache_key):
                    logger.info(f"[PersistentServiceCache] ⏰ Instancia DB expirada: {db_id}")
                    self._remove_service(cache_key)
                else:
                    # Actualizar estadísticas
                    self._update_access_stats(cache_key, "cache_hit")
                    self._last_accessed[cache_key] = time.time()
                    logger.debug(f"[PersistentServiceCache] 🔥 Cache HIT para instancia DB: {db_id}")
                    return service
            
            return None
            
        except Exception as e:
            logger.error(f"[PersistentServiceCache] ❌ Error obteniendo instancia DB {db_id}: {e}")
            return None
    
    def set_db_instance(self, user_id: str, db_id: str, instance: Any) -> bool:
        """Guarda una instancia de base de datos en el cache"""
        try:
            cache_key = f"db_instance_{user_id}_{db_id}"
            
            # Verificar si hay espacio
            if len(self._services) >= self.max_services:
                self._evict_least_used()
            
            # Agregar al cache
            self._services[cache_key] = instance
            self._timestamps[cache_key] = time.time()
            self._last_accessed[cache_key] = time.time()
            self._access_count[cache_key] = 0
            
            # Inicializar estadísticas
            self._service_stats[cache_key] = {
                'creation_time': 0.1,  # Tiempo aproximado
                'total_requests': 0,
                'cache_hits': 0,
                'cache_misses': 0,
                'last_created': datetime.utcnow().isoformat()
            }
            
            logger.info(f"[PersistentServiceCache] ✅ Instancia DB {db_id} cacheada para usuario {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"[PersistentServiceCache] ❌ Error cacheando instancia DB {db_id}: {e}")
            return False
    
    def _add_service_to_cache(self, service_name: str, service: Any, creation_time: float):
        """Agrega un servicio al cache"""
        # Verificar si hay espacio
        if len(self._services) >= self.max_services:
            self._evict_least_used()
        
        # Agregar al cache
        self._services[service_name] = service
        self._timestamps[service_name] = time.time()
        self._last_accessed[service_name] = time.time()
        self._access_count[service_name] = 0
        
        # Inicializar estadísticas
        self._service_stats[service_name] = {
            'creation_time': creation_time,
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'last_created': datetime.utcnow().isoformat()
        }
    
    def _update_access_stats(self, service_name: str, action: str):
        """Actualiza estadísticas de acceso del servicio"""
        if service_name not in self._service_stats:
            return
        
        stats = self._service_stats[service_name]
        stats['total_requests'] += 1
        
        if action == 'cache_hit':
            stats['cache_hits'] += 1
        elif action == 'created':
            stats['cache_misses'] += 1
        
        # Calcular hit ratio
        if stats['total_requests'] > 0:
            stats['hit_ratio'] = (stats['cache_hits'] / stats['total_requests']) * 100
    
    def _is_expired(self, service_name: str) -> bool:
        """Verifica si un servicio ha expirado"""
        if service_name not in self._timestamps:
            return True
        
        timestamp = self._timestamps[service_name]
        expiration_time = timestamp + (self.ttl_hours * 3600)
        
        return time.time() > expiration_time
    
    def _evict_least_used(self):
        """Elimina el servicio menos usado del cache"""
        if not self._access_count:
            return
        
        # Encontrar servicio con menos accesos
        least_used = min(self._access_count.items(), key=lambda x: x[1])
        service_name = least_used[0]
        
        logger.info(f"[PersistentServiceCache] 🗑️ Evicting least used service: {service_name}")
        self._remove_service(service_name)
    
    def _remove_service(self, service_name: str):
        """Remueve un servicio del cache"""
        if service_name in self._services:
            # Intentar limpiar el servicio si tiene método dispose
            service = self._services[service_name]
            try:
                if hasattr(service, 'dispose'):
                    service.dispose()
                    logger.debug(f"[PersistentServiceCache] 🔌 Servicio disposed: {service_name}")
            except Exception as e:
                logger.warning(f"[PersistentServiceCache] ⚠️ Error disposing servicio {service_name}: {e}")
            
            # Remover del cache
            del self._services[service_name]
            del self._timestamps[service_name]
            del self._access_count[service_name]
            del self._last_accessed[service_name]
            if service_name in self._service_stats:
                del self._service_stats[service_name]
    
    def _start_cleanup_thread(self):
        """Inicia el thread de limpieza automática"""
        def cleanup_worker():
            while not self._stop_cleanup:
                try:
                    time.sleep(300)  # Limpiar cada 5 minutos
                    self._cleanup_expired_services()
                except Exception as e:
                    logger.error(f"[PersistentServiceCache] ❌ Error en cleanup thread: {e}")
        
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        logger.info("[PersistentServiceCache] 🧹 Thread de limpieza iniciado")
    
    def _cleanup_expired_services(self):
        """Limpia servicios expirados"""
        with self._lock:
            expired_services = [
                service_name for service_name in self._services.keys()
                if self._is_expired(service_name)
            ]
            
            for service_name in expired_services:
                logger.info(f"[PersistentServiceCache] 🧹 Limpiando servicio expirado: {service_name}")
                self._remove_service(service_name)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache"""
        with self._lock:
            total_services = len(self._services)
            total_requests = sum(stats['total_requests'] for stats in self._service_stats.values())
            total_cache_hits = sum(stats['cache_hits'] for stats in self._service_stats.values())
            total_cache_misses = sum(stats['cache_misses'] for stats in self._service_stats.values())
            
            overall_hit_ratio = 0
            if total_requests > 0:
                overall_hit_ratio = (total_cache_hits / total_requests) * 100
            
            # Calcular tiempo promedio de creación
            creation_times = [stats['creation_time'] for stats in self._service_stats.values()]
            avg_creation_time = sum(creation_times) / len(creation_times) if creation_times else 0
            
            return {
                'total_services': total_services,
                'max_services': self.max_services,
                'total_requests': total_requests,
                'total_cache_hits': total_cache_hits,
                'total_cache_misses': total_cache_misses,
                'overall_hit_ratio': overall_hit_ratio,
                'avg_creation_time': avg_creation_time,
                'ttl_hours': self.ttl_hours,
                'services_details': {
                    service_name: {
                        'age_seconds': time.time() - self._timestamps.get(service_name, 0),
                        'last_accessed_seconds': time.time() - self._last_accessed.get(service_name, 0),
                        'access_count': self._access_count.get(service_name, 0),
                        'hit_ratio': stats.get('hit_ratio', 0),
                        'creation_time': stats.get('creation_time', 0)
                    }
                    for service_name, stats in self._service_stats.items()
                }
            }
    
    def clear_cache(self, service_name: Optional[str] = None):
        """Limpia el cache"""
        with self._lock:
            if service_name:
                if service_name in self._services:
                    self._remove_service(service_name)
                    logger.info(f"[PersistentServiceCache] 🧹 Cache limpiado para servicio: {service_name}")
            else:
                # Limpiar todo el cache
                for service_name in list(self._services.keys()):
                    self._remove_service(service_name)
                logger.info("[PersistentServiceCache] 🧹 Cache completamente limpiado")
    
    def warm_up_cache(self, service_names: list) -> Dict[str, bool]:
        """Pre-calienta el cache para servicios específicos"""
        results = {}
        
        for service_name in service_names:
            try:
                service = self.get_service(service_name)
                results[service_name] = service is not None
                
                if results[service_name]:
                    logger.info(f"[PersistentServiceCache] 🔥 Cache caliente para: {service_name}")
                else:
                    logger.warning(f"[PersistentServiceCache] ❄️ Cache frío para: {service_name}")
                    
            except Exception as e:
                logger.error(f"[PersistentServiceCache] ❌ Error warming up {service_name}: {e}")
                results[service_name] = False
        
        return results
    
    def shutdown(self):
        """Apaga el cache y limpia recursos"""
        with self._lock:
            self._stop_cleanup = True
            
            # Limpiar todo el cache
            self.clear_cache()
            
            # Esperar a que termine el thread de limpieza
            if self._cleanup_thread and self._cleanup_thread.is_alive():
                self._cleanup_thread.join(timeout=5)
            
            logger.info("[PersistentServiceCache] 🔌 Cache apagado")
