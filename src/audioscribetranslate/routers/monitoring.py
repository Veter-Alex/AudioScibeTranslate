"""
API эндпоинты для мониторинга системы и управления воркерами
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from audioscribetranslate.core.config import get_settings
from audioscribetranslate.core.memory_monitor import memory_monitor
from audioscribetranslate.db.session import get_db

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/status", response_model=Dict[str, Any])
def get_system_status():
    """
    Получить статус системы мониторинга и воркеров

    Возвращает информацию о:
    - Использовании памяти
    - Количестве активных воркеров
    - Конфигурации автомасштабирования
    - Активных процессах
    """
    try:
        status = memory_monitor.get_status()
        return {
            "status": "success",
            "data": status,
            "message": "Статус системы получен успешно",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения статуса системы: {str(e)}"
        )


@router.get("/memory", response_model=Dict[str, Any])
def get_memory_info():
    """
    Получить детальную информацию о памяти
    """
    try:
        memory_info = memory_monitor.get_memory_info()
        return {
            "status": "success",
            "data": {
                "total_gb": round(memory_info.total_gb, 2),
                "available_gb": round(memory_info.available_gb, 2),
                "used_gb": round(memory_info.used_gb, 2),
                "free_gb": round(memory_info.free_gb, 2),
                "percent_used": round(memory_info.percent_used, 1),
                "threshold_gb": memory_monitor.memory_threshold_gb,
                "optimal_workers": memory_monitor.calculate_optimal_workers(
                    memory_info
                ),
            },
            "message": "Информация о памяти получена успешно",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения информации о памяти: {str(e)}"
        )


@router.get("/workers", response_model=Dict[str, Any])
def get_workers_info():
    """
    Получить информацию о Celery воркерах
    """
    try:
        workers = memory_monitor.get_celery_workers()
        return {
            "status": "success",
            "data": {
                "active_count": len(memory_monitor._active_workers),
                "system_processes": [
                    {
                        "pid": w.pid,
                        "name": w.name,
                        "memory_mb": round(w.memory_mb, 1),
                        "cpu_percent": round(w.cpu_percent, 1),
                        "status": w.status,
                    }
                    for w in workers
                ],
                "managed_workers": len(memory_monitor._active_workers),
                "config": {
                    "max_workers": memory_monitor.max_workers,
                    "min_workers": memory_monitor.min_workers,
                    "memory_limit_gb": memory_monitor.worker_memory_limit_gb,
                    "auto_scaling": memory_monitor.auto_scaling_enabled,
                },
            },
            "message": "Информация о воркерах получена успешно",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения информации о воркерах: {str(e)}"
        )


@router.post("/workers/scale", response_model=Dict[str, Any])
def scale_workers(target_workers: int):
    """
    Ручное масштабирование количества воркеров

    Args:
        target_workers: Целевое количество воркеров
    """
    if not (memory_monitor.min_workers <= target_workers <= memory_monitor.max_workers):
        raise HTTPException(
            status_code=400,
            detail=f"Количество воркеров должно быть между {memory_monitor.min_workers} и {memory_monitor.max_workers}",
        )

    try:
        current_count = len(memory_monitor._active_workers)
        memory_monitor.scale_workers(target_workers)

        return {
            "status": "success",
            "data": {
                "previous_count": current_count,
                "target_count": target_workers,
                "current_count": len(memory_monitor._active_workers),
            },
            "message": f"Воркеры масштабированы с {current_count} до {target_workers}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка масштабирования воркеров: {str(e)}"
        )


@router.post("/monitoring/start", response_model=Dict[str, Any])
def start_monitoring():
    """
    Запустить мониторинг памяти и автомасштабирование
    """
    try:
        if (
            memory_monitor._monitoring_thread
            and memory_monitor._monitoring_thread.is_alive()
        ):
            return {"status": "info", "message": "Мониторинг уже запущен"}

        memory_monitor.start_monitoring()

        return {"status": "success", "message": "Мониторинг памяти запущен"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка запуска мониторинга: {str(e)}"
        )


@router.post("/monitoring/stop", response_model=Dict[str, Any])
def stop_monitoring():
    """
    Остановить мониторинг памяти и автомасштабирование
    """
    try:
        memory_monitor.stop_monitoring()

        return {"status": "success", "message": "Мониторинг памяти остановлен"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка остановки мониторинга: {str(e)}"
        )


@router.get("/config", response_model=Dict[str, Any])
def get_monitoring_config():
    """
    Получить текущую конфигурацию мониторинга
    """
    settings = get_settings()

    return {
        "status": "success",
        "data": {
            "memory_threshold_gb": settings.memory_threshold_gb,
            "max_workers": settings.max_workers,
            "min_workers": settings.min_workers,
            "memory_check_interval": settings.memory_check_interval,
            "worker_memory_limit_gb": settings.worker_memory_limit_gb,
            "enable_auto_scaling": settings.enable_auto_scaling,
            "environment": settings.environment,
        },
        "message": "Конфигурация мониторинга получена успешно",
    }
