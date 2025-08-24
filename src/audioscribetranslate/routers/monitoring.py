"""
Маршруты для мониторинга системы обработки цепочек.
"""
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from audioscribetranslate.core.chain_manager import ProcessingChainManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

# Глобальная переменная для chain_manager будет инициализирована при старте приложения
from typing import Optional

chain_manager: Optional[ProcessingChainManager] = None


def set_chain_manager(manager: ProcessingChainManager) -> None:
    """Устанавливает менеджер цепочек для использования в роутах."""
    global chain_manager
    chain_manager = manager


@router.get("/status")
async def get_monitoring_status() -> Dict[str, Any]:
    """Возвращает общий статус системы мониторинга."""
    if not chain_manager:
        raise HTTPException(status_code=503, detail="Chain manager не инициализирован")
    
    try:
        # Базовая информация о системе
        status = {
            "service": "AudioScribeTranslate Monitoring",
            "status": "active",
            "chain_manager_active": chain_manager.is_running if hasattr(chain_manager, 'is_running') else True
        }
        
        # Добавляем информацию о памяти если psutil доступен
        if PSUTIL_AVAILABLE:
            memory = psutil.virtual_memory()
            status.update({
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "used_percent": memory.percent,
                    "free_gb": round((memory.total - memory.used) / (1024**3), 2)
                }
            })
        
        return status
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса мониторинга: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка мониторинга: {str(e)}")


@router.get("/workers")
async def get_worker_info() -> Dict[str, Any]:
    """Возвращает информацию о воркерах цепочек обработки."""
    if not chain_manager:
        raise HTTPException(status_code=503, detail="Chain manager не инициализирован")
    
    try:
        workers_info: Dict[str, Any] = {
            "active_workers": 0,
            "worker_processes": [],
            "queue_info": {
                "processing_chains": "unknown"
            }
        }

        # Получаем информацию о активных воркерах из chain_manager
        if hasattr(chain_manager, 'workers'):
            workers_info["active_workers"] = len(chain_manager.workers)
            # Детальная информация о каждом воркере
            for worker_id, worker in chain_manager.workers.items():
                worker_info = {
                    "id": worker_id,
                    "status": "running" if hasattr(worker, 'process') and worker.process and worker.process.poll() is None else "stopped",
                    "pid": worker.process.pid if hasattr(worker, 'process') and worker.process and worker.process.poll() is None else None
                }
                # Добавляем информацию об использовании ресурсов если доступно
                if PSUTIL_AVAILABLE and worker_info["pid"]:
                    try:
                        proc = psutil.Process(worker_info["pid"])
                        worker_info["memory_mb"] = round(proc.memory_info().rss / (1024**2), 2)
                        worker_info["cpu_percent"] = round(proc.cpu_percent(interval=None), 2)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                workers_info["worker_processes"].append(worker_info)
        
        return workers_info
        
    except Exception as e:
        logger.error(f"Ошибка получения информации о воркерах: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения информации о воркерах: {str(e)}")


@router.get("/memory")
async def get_memory_info() -> Dict[str, Any]:
    """Возвращает детальную информацию о памяти системы."""
    if not PSUTIL_AVAILABLE:
        raise HTTPException(status_code=503, detail="psutil не доступен для мониторинга памяти")
    
    try:
        # Виртуальная память
        memory = psutil.virtual_memory()
        
        # Swap память
        swap = psutil.swap_memory()
        
        memory_info = {
            "virtual_memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "free_gb": round(memory.free / (1024**3), 2),
                "percent_used": memory.percent,
                "buffers_gb": round(memory.buffers / (1024**3), 2) if hasattr(memory, 'buffers') else 0,
                "cached_gb": round(memory.cached / (1024**3), 2) if hasattr(memory, 'cached') else 0
            },
            "swap_memory": {
                "total_gb": round(swap.total / (1024**3), 2),
                "used_gb": round(swap.used / (1024**3), 2),
                "free_gb": round(swap.free / (1024**3), 2),
                "percent_used": swap.percent
            }
        }
        
        # CPU информация
        import os
        cpu_info = {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "cpu_count_logical": psutil.cpu_count(),
            "cpu_count_physical": psutil.cpu_count(logical=False),
            "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') and os.name != 'nt' else None
        }
        
        memory_info["cpu"] = cpu_info
        
        return memory_info
        
    except Exception as e:
        logger.error(f"Ошибка получения информации о памяти: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения информации о памяти: {str(e)}")


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Простая проверка работоспособности сервиса."""
    return {
        "status": "healthy",
        "service": "AudioScribeTranslate Monitoring",
        "psutil_available": str(PSUTIL_AVAILABLE)
    }
