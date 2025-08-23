"""
Менеджер цепочек обработки аудиофайлов.

Отвечает за:
- Автоматический запуск воркеров при наличии файлов в очереди
- Контроль использования памяти
- Масштабирование количества воркеров
"""

import logging
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

import psutil
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from audioscribetranslate.core.config import get_settings
from audioscribetranslate.models.audio_file import AudioFile

logger = logging.getLogger(__name__)


class ChainWorkerProcess:
    """Представляет процесс воркера цепочек обработки."""
    
    def __init__(self, worker_id: str, process: subprocess.Popen[bytes]) -> None:
        self.worker_id = worker_id
        self.process = process
        self.start_time = time.time()
        self.is_active = True
    
    def get_memory_usage_mb(self) -> float:
        """Возвращает использование памяти процессом в МБ."""
        try:
            proc = psutil.Process(self.process.pid)
            return float(proc.memory_info().rss / (1024 * 1024))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0
    
    def is_running(self) -> bool:
        """Проверяет, запущен ли процесс."""
        return self.process.poll() is None
    
    def terminate(self) -> None:
        """Завершает процесс воркера."""
        try:
            self.process.terminate()
            self.process.wait(timeout=10)
            self.is_active = False
            logger.info(f"Воркер цепочек {self.worker_id} завершен")
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.is_active = False
            logger.warning(f"Воркер цепочек {self.worker_id} принудительно завершен")
        except Exception as e:
            logger.error(f"Ошибка завершения воркера {self.worker_id}: {e}")


class ProcessingChainManager:
    """Менеджер для управления воркерами цепочек обработки."""
    
    def __init__(self) -> None:
        self.settings = get_settings()
        self.workers: Dict[str, ChainWorkerProcess] = {}
        self.is_running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.engine = create_engine(self.settings.sync_database_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)
    
    def get_available_memory_gb(self) -> float:
        """Возвращает доступную память в ГБ."""
        memory = psutil.virtual_memory()
        return float(memory.available / (1024**3))
    
    def get_queued_files_count(self) -> int:
        """Возвращает количество файлов в очереди."""
        try:
            with self.SessionLocal() as session:
                result = session.execute(
                    select(AudioFile).where(AudioFile.status == "queued")
                )
                return len(result.scalars().all())
        except Exception as e:
            logger.error(f"Ошибка получения количества файлов в очереди: {e}")
            return 0
    
    def should_start_new_worker(self) -> bool:
        """
        Определяет, нужно ли запускать новый воркер.
        
        Returns:
            bool: True если нужно запускать новый воркер
        """
        # Проверяем память
        available_memory = self.get_available_memory_gb()
        if available_memory < self.settings.min_free_memory_gb:
            logger.debug(f"Недостаточно памяти: {available_memory:.1f}GB < {self.settings.min_free_memory_gb}GB")
            return False
        
        # Проверяем очередь
        queued_files = self.get_queued_files_count()
        if queued_files == 0:
            logger.debug("Нет файлов в очереди")
            return False
        
        # Проверяем максимальное количество воркеров
        active_workers = len([w for w in self.workers.values() if w.is_running()])
        if active_workers >= self.settings.max_workers:
            logger.debug(f"Достигнут максимум воркеров: {active_workers}/{self.settings.max_workers}")
            return False
        
        logger.info(f"Можно запустить новый воркер: память={available_memory:.1f}GB, очередь={queued_files}, воркеров={active_workers}")
        return True
    
    def start_chain_worker(self) -> Optional[str]:
        """
        Запускает новый воркер для обработки цепочек.
        
        Returns:
            Optional[str]: ID воркера если запуск успешен, иначе None
        """
        try:
            worker_id = f"chain_worker_{len(self.workers) + 1}"
            
            # Команда для запуска воркера цепочек
            cmd = [
                "python", "-m", "celery",
                "-A", "src.audioscribetranslate.worker",
                "worker",
                "--loglevel=info",
                "--pool=solo",
                "--queues=processing_chains",
                f"--hostname={worker_id}@%h",
                "--concurrency=1",
                f"--max-memory-per-child={self.settings.worker_memory_limit_gb * 1024 * 1024}"
            ]
            
            logger.info(f"Запуск воркера цепочек: {worker_id}")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            
            worker = ChainWorkerProcess(worker_id, process)
            self.workers[worker_id] = worker
            
            logger.info(f"Воркер цепочек {worker_id} запущен с PID {process.pid}")
            return worker_id
            
        except Exception as e:
            logger.error(f"Ошибка запуска воркера цепочек: {e}")
            return None
    
    def cleanup_inactive_workers(self) -> None:
        """Удаляет неактивные воркеры из списка."""
        inactive_workers = []
        for worker_id, worker in self.workers.items():
            if not worker.is_running():
                inactive_workers.append(worker_id)
        
        for worker_id in inactive_workers:
            logger.info(f"Удаляем неактивный воркер: {worker_id}")
            del self.workers[worker_id]
    
    def get_workers_status(self) -> Dict[str, Dict[str, Any]]:
        """Возвращает статус всех воркеров."""
        status = {}
        for worker_id, worker in self.workers.items():
            status[worker_id] = {
                "pid": worker.process.pid,
                "running": worker.is_running(),
                "memory_mb": worker.get_memory_usage_mb(),
                "uptime_seconds": time.time() - worker.start_time,
                "start_time": worker.start_time
            }
        return status
    
    def monitor_and_scale(self) -> None:
        """Основной цикл мониторинга и масштабирования."""
        logger.info("Запуск мониторинга цепочек обработки")
        
        while self.is_running:
            try:
                # Очистка неактивных воркеров
                self.cleanup_inactive_workers()
                
                # Проверка необходимости запуска новых воркеров
                if self.should_start_new_worker():
                    self.start_chain_worker()
                
                # Логирование статуса каждые 60 секунд
                if int(time.time()) % 60 == 0:
                    self.log_status()
                
                time.sleep(self.settings.chain_queue_check_interval)
                
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга цепочек: {e}")
                time.sleep(30)  # Больше времени при ошибках
    
    def log_status(self) -> None:
        """Логирует текущий статус системы."""
        active_workers = len([w for w in self.workers.values() if w.is_running()])
        queued_files = self.get_queued_files_count()
        available_memory = self.get_available_memory_gb()
        
        logger.info("=== СТАТУС ЦЕПОЧЕК ОБРАБОТКИ ===")
        logger.info(f"Активных воркеров: {active_workers}/{self.settings.max_workers}")
        logger.info(f"Файлов в очереди: {queued_files}")
        logger.info(f"Доступно памяти: {available_memory:.1f} GB")
        
        if active_workers > 0:
            total_memory = sum(w.get_memory_usage_mb() for w in self.workers.values() if w.is_running())
            logger.info(f"Использование памяти воркерами: {total_memory:.1f} MB")
    
    def start(self) -> None:
        """Запускает менеджер цепочек."""
        if self.is_running:
            logger.warning("Менеджер цепочек уже запущен")
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self.monitor_and_scale, daemon=True)
        self.monitor_thread.start()
        logger.info("Менеджер цепочек обработки запущен")
    
    def stop(self) -> None:
        """Останавливает менеджер и все воркеры."""
        logger.info("Остановка менеджера цепочек обработки...")
        self.is_running = False
        
        # Останавливаем все воркеры
        for worker in self.workers.values():
            worker.terminate()
        
        # Ждем завершения потока мониторинга
        if self.monitor_thread:
            self.monitor_thread.join(timeout=30)
        
        self.workers.clear()
        logger.info("Менеджер цепочек обработки остановлен")


# Глобальный экземпляр менеджера
_chain_manager: Optional[ProcessingChainManager] = None


def get_chain_manager() -> ProcessingChainManager:
    """Возвращает экземпляр менеджера цепочек (singleton)."""
    global _chain_manager
    if _chain_manager is None:
        _chain_manager = ProcessingChainManager()
    return _chain_manager


def start_chain_manager() -> None:
    """Запускает менеджер цепочек."""
    manager = get_chain_manager()
    manager.start()


def stop_chain_manager() -> None:
    """Останавливает менеджер цепочек."""
    global _chain_manager
    if _chain_manager:
        _chain_manager.stop()
        _chain_manager = None
        _chain_manager = None
