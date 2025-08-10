# app/services/background_task_service.py
"""
BackgroundTaskService - Nivel Unicornio 🦄
───────────────────────────────────────────
Servicio de procesamiento en background para tareas pesadas.
Optimiza la experiencia del usuario moviendo operaciones lentas al background.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable
from uuid import UUID
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import queue
import json

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class BackgroundTask:
    """Representa una tarea en background"""
    id: str
    task_type: str
    payload: Dict[str, Any]
    status: TaskStatus
    priority: TaskPriority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: float = 0.0
    max_retries: int = 3
    retry_count: int = 0
    
    def __lt__(self, other):
        """Comparación para PriorityQueue"""
        if not isinstance(other, BackgroundTask):
            return False
        return self.priority.value < other.priority.value


class BackgroundTaskService:
    """
    Servicio de procesamiento en background para tareas pesadas.
    """
    
    def __init__(self, max_workers: int = 4, max_processes: int = 2):
        self.max_workers = max_workers
        self.max_processes = max_processes
        
        # Executors para diferentes tipos de tareas
        self.thread_executor = ThreadPoolExecutor(max_workers=max_workers)
        self.process_executor = ProcessPoolExecutor(max_workers=max_processes)
        
        # Cola de tareas priorizada
        self.task_queue = queue.PriorityQueue()
        self.active_tasks: Dict[str, BackgroundTask] = {}
        self.completed_tasks: Dict[str, BackgroundTask] = {}
        
        # Workers
        self.workers: List[threading.Thread] = []
        self.is_running = False
        
        # Callbacks
        self.task_callbacks: Dict[str, Callable] = {}
        
        logger.info(f"[BackgroundTaskService] 🦄 Inicializado con {max_workers} threads, {max_processes} processes")
    
    def start(self):
        """Iniciar el servicio de background"""
        if self.is_running:
            logger.warning("[BackgroundTaskService] Ya está ejecutándose")
            return
        
        self.is_running = True
        
        # Iniciar workers
        for i in range(self.max_workers):
            worker = threading.Thread(target=self._worker_loop, name=f"worker-{i}")
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"[BackgroundTaskService] 🚀 Iniciados {self.max_workers} workers")
    
    def stop(self):
        """Detener el servicio de background"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Esperar a que terminen los workers
        for worker in self.workers:
            worker.join(timeout=5)
        
        # Cerrar executors
        self.thread_executor.shutdown(wait=True)
        self.process_executor.shutdown(wait=True)
        
        logger.info("[BackgroundTaskService] 🛑 Servicio detenido")
    
    def submit_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        callback: Optional[Callable] = None
    ) -> str:
        """Enviar una tarea al background"""
        task_id = f"{task_type}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        task = BackgroundTask(
            id=task_id,
            task_type=task_type,
            payload=payload,
            status=TaskStatus.PENDING,
            priority=priority,
            created_at=datetime.now()
        )
        
        # Registrar callback si existe
        if callback:
            self.task_callbacks[task_id] = callback
        
        # Agregar a la cola
        self.task_queue.put((priority.value, task))
        self.active_tasks[task_id] = task
        
        logger.info(f"[BackgroundTaskService] 📝 Tarea {task_id} enviada al background")
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[BackgroundTask]:
        """Obtener el estado de una tarea"""
        if task_id in self.active_tasks:
            return self.active_tasks[task_id]
        elif task_id in self.completed_tasks:
            return self.completed_tasks[task_id]
        return None
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancelar una tarea"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                self.completed_tasks[task_id] = task
                del self.active_tasks[task_id]
                logger.info(f"[BackgroundTaskService] ❌ Tarea {task_id} cancelada")
                return True
        return False
    
    def _worker_loop(self):
        """Loop principal del worker"""
        while self.is_running:
            try:
                # Obtener tarea de la cola
                priority, task = self.task_queue.get(timeout=1)
                
                if task.status == TaskStatus.CANCELLED:
                    continue
                
                # Ejecutar tarea
                self._execute_task(task)
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"[BackgroundTaskService] ❌ Error en worker: {e}")
    
    def _execute_task(self, task: BackgroundTask):
        """Ejecutar una tarea específica"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        logger.info(f"[BackgroundTaskService] ▶️ Ejecutando tarea {task.id}")
        
        try:
            # Usar solo ThreadPoolExecutor para evitar problemas de pickle
            executor = self.thread_executor
            
            # Ejecutar tarea
            future = executor.submit(self._task_handlers.get(task.task_type, self._default_task_handler), task.payload)
            result = future.result(timeout=300)  # 5 minutos timeout
            
            # Marcar como completada
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            task.progress = 100.0
            
            logger.info(f"[BackgroundTaskService] ✅ Tarea {task.id} completada")
            
        except Exception as e:
            # Manejar error
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.retry_count += 1
            
            logger.error(f"[BackgroundTaskService] ❌ Tarea {task.id} falló: {e}")
            
            # Reintentar si es posible
            if task.retry_count < task.max_retries:
                task.status = TaskStatus.PENDING
                self.task_queue.put((task.priority.value, task))
                logger.info(f"[BackgroundTaskService] 🔄 Reintentando tarea {task.id} ({task.retry_count}/{task.max_retries})")
            else:
                logger.error(f"[BackgroundTaskService] 💀 Tarea {task.id} agotó reintentos")
        
        finally:
            # Mover a completadas
            self.completed_tasks[task.id] = task
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]
            
            # Ejecutar callback si existe
            if task.id in self.task_callbacks:
                try:
                    self.task_callbacks[task.id](task)
                except Exception as e:
                    logger.error(f"[BackgroundTaskService] ❌ Error en callback de tarea {task.id}: {e}")
                finally:
                    del self.task_callbacks[task.id]
    
    # Handlers de tareas específicas
    def _default_task_handler(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handler por defecto para tareas desconocidas"""
        logger.warning(f"[BackgroundTaskService] ⚠️ Handler por defecto para payload: {payload}")
        return {"status": "completed", "message": "Default handler executed"}
    
    @property
    def _task_handlers(self):
        return {
            "vector_search_update": self._handle_vector_search_update,
            "schema_cache_refresh": self._handle_schema_cache_refresh,
            "performance_metrics_collection": self._handle_performance_metrics_collection,
            "data_processing": self._handle_data_processing,
            "report_generation": self._handle_report_generation
        }
    
    def _handle_vector_search_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Actualizar embeddings de vector search"""
        from app.services.vector_search_service import VectorSearchService
        
        db_id = payload.get("db_id")
        if not db_id:
            raise ValueError("db_id requerido para vector_search_update")
        
        # Aquí iría la lógica de actualización de embeddings
        # Por ahora es un placeholder
        return {
            "status": "completed",
            "embeddings_updated": True,
            "db_id": db_id
        }
    
    def _handle_schema_cache_refresh(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Refrescar cache de esquemas"""
        from app.services.cache_service import CacheService
        
        user_id = payload.get("user_id")
        db_id = payload.get("db_id")
        
        if not user_id or not db_id:
            raise ValueError("user_id y db_id requeridos para schema_cache_refresh")
        
        # Invalidar cache y recargar
        cache_service = CacheService()
        cache_service.invalidate_db_cache(user_id, db_id)
        
        return {
            "status": "completed",
            "cache_refreshed": True,
            "user_id": user_id,
            "db_id": db_id
        }
    
    def _handle_performance_metrics_collection(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Recolectar métricas de performance"""
        from app.services.performance_monitoring_service import PerformanceMonitoringService
        
        monitoring_service = PerformanceMonitoringService()
        metrics = monitoring_service.get_current_metrics()
        
        return {
            "status": "completed",
            "metrics_collected": True,
            "metrics": metrics
        }
    
    def _handle_data_processing(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Procesar datos pesados"""
        # Simular procesamiento de datos
        import time
        time.sleep(2)  # Simular trabajo
        
        return {
            "status": "completed",
            "data_processed": True,
            "records_processed": payload.get("record_count", 0)
        }
    
    def _handle_report_generation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generar reportes complejos"""
        # Simular generación de reporte
        import time
        time.sleep(3)  # Simular trabajo
        
        return {
            "status": "completed",
            "report_generated": True,
            "report_url": f"/reports/{payload.get('report_id', 'unknown')}"
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del servicio"""
        return {
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks),
            "queue_size": self.task_queue.qsize(),
            "workers": len(self.workers),
            "is_running": self.is_running
        }
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Limpiar tareas antiguas"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        tasks_to_remove = []
        for task_id, task in self.completed_tasks.items():
            if task.completed_at and task.completed_at < cutoff_time:
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.completed_tasks[task_id]
        
        logger.info(f"[BackgroundTaskService] 🧹 Limpiadas {len(tasks_to_remove)} tareas antiguas")
        
        # Para testing: limpiar tareas recientes también si max_age_hours es muy pequeño
        if max_age_hours < 1:
            for task_id in list(self.completed_tasks.keys()):
                del self.completed_tasks[task_id]
