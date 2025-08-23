"""
Сервис мониторинга памяти и динамического масштабирования Celery воркеров.

Этот модуль предоставляет функциональность для:
- Мониторинга использования системной памяти
- Автоматического масштабирования количества Celery воркеров
- Управления ресурсами на основе доступной памяти

Особенно полезен для серверов Dell R620 с 64GB RAM и 8 CPU.
"""

import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from threading import Event, Thread
from typing import Dict, List, Optional

import psutil

from audioscribetranslate.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class MemoryInfo:
    """Информация о состоянии памяти системы"""

    total_gb: float
    available_gb: float
    used_gb: float
    percent_used: float
    free_gb: float


@dataclass
class WorkerInfo:
    """Информация о воркере Celery"""

    pid: int
    name: str
    memory_mb: float
    cpu_percent: float
    status: str


class MemoryMonitor:
    """
    Мониторинг памяти и управление Celery воркерами

    Этот класс отслеживает использование памяти и автоматически
    масштабирует количество Celery воркеров на основе доступных ресурсов.
    """

    def __init__(self):
        self.settings = get_settings()
        self._stop_event = Event()
        self._monitoring_thread: Optional[Thread] = None
        self._active_workers: List[subprocess.Popen] = []

        # Настройки из конфига
        self.memory_threshold_gb = self.settings.memory_threshold_gb
        self.max_workers = self.settings.max_workers
        self.min_workers = self.settings.min_workers
        self.memory_check_interval = self.settings.memory_check_interval
        self.worker_memory_limit_gb = self.settings.worker_memory_limit_gb
        self.auto_scaling_enabled = self.settings.enable_auto_scaling

        logger.info(f"Memory Monitor инициализирован:")
        logger.info(f"  - Порог памяти: {self.memory_threshold_gb} GB")
        logger.info(f"  - Максимум воркеров: {self.max_workers}")
        logger.info(f"  - Минимум воркеров: {self.min_workers}")
        logger.info(
            f"  - Автомасштабирование: {'включено' if self.auto_scaling_enabled else 'отключено'}"
        )

    def get_memory_info(self) -> MemoryInfo:
        """Получить информацию о памяти системы"""
        memory = psutil.virtual_memory()

        return MemoryInfo(
            total_gb=memory.total / (1024**3),
            available_gb=memory.available / (1024**3),
            used_gb=memory.used / (1024**3),
            percent_used=memory.percent,
            free_gb=memory.free / (1024**3),
        )

    def get_celery_workers(self) -> List[WorkerInfo]:
        """Получить список активных Celery воркеров"""
        workers = []

        for process in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                info = process.info
                cmdline = info.get("cmdline", [])

                # Ищем процессы celery worker
                if (
                    cmdline
                    and len(cmdline) > 1
                    and "celery" in cmdline
                    and "worker" in cmdline
                ):

                    memory_mb = process.memory_info().rss / (1024 * 1024)
                    cpu_percent = process.cpu_percent(interval=0.1)

                    workers.append(
                        WorkerInfo(
                            pid=info["pid"],
                            name=info["name"],
                            memory_mb=memory_mb,
                            cpu_percent=cpu_percent,
                            status="running",
                        )
                    )

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        return workers

    def calculate_optimal_workers(self, memory_info: MemoryInfo) -> int:
        """
        Рассчитать оптимальное количество воркеров на основе доступной памяти

        Args:
            memory_info: Информация о памяти системы

        Returns:
            Оптимальное количество воркеров
        """
        if not self.auto_scaling_enabled:
            return self.min_workers

        # Доступная память для воркеров (оставляем запас для системы)
        available_for_workers = memory_info.available_gb - 4  # 4GB запас для системы

        # Сколько воркеров можем запустить исходя из памяти
        workers_by_memory = int(available_for_workers / self.worker_memory_limit_gb)

        # Ограничиваем по настройкам
        optimal_workers = max(
            self.min_workers, min(workers_by_memory, self.max_workers)
        )

        # Дополнительная проверка: если свободной памяти меньше порога, уменьшаем воркеров
        if memory_info.available_gb < self.memory_threshold_gb:
            optimal_workers = max(self.min_workers, optimal_workers - 1)

        logger.debug(f"Расчет оптимального количества воркеров:")
        logger.debug(f"  - Доступная память: {memory_info.available_gb:.2f} GB")
        logger.debug(f"  - Память для воркеров: {available_for_workers:.2f} GB")
        logger.debug(f"  - Воркеров по памяти: {workers_by_memory}")
        logger.debug(f"  - Оптимальное количество: {optimal_workers}")

        return optimal_workers

    def start_worker(self, worker_id: int) -> Optional[subprocess.Popen]:
        """
        Запустить нового Celery воркера

        Args:
            worker_id: ID воркера

        Returns:
            Процесс воркера или None в случае ошибки
        """
        try:
            worker_name = f"worker_{worker_id}@%h"
            cmd = [
                "celery",
                "-A",
                "src.audioscribetranslate.worker",
                "worker",
                "--loglevel=info",
                f"--hostname={worker_name}",
                "--concurrency=1",  # Один процесс на воркера для контроля памяти
                f"--max-memory-per-child={self.worker_memory_limit_gb * 1024 * 1024}",  # В KB
            ]

            logger.info(f"Запускаем воркера {worker_name}: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy(),
            )

            self._active_workers.append(process)
            logger.info(f"Воркер {worker_name} запущен с PID {process.pid}")

            return process

        except Exception as e:
            logger.error(f"Ошибка при запуске воркера {worker_id}: {e}")
            return None

    def stop_worker(self, process: subprocess.Popen) -> bool:
        """
        Остановить воркера

        Args:
            process: Процесс воркера

        Returns:
            True если воркер успешно остановлен
        """
        try:
            logger.info(f"Останавливаем воркера с PID {process.pid}")

            # Отправляем SIGTERM для graceful shutdown
            process.terminate()

            # Ждем завершения до 10 секунд
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Если не остановился, принудительно убиваем
                logger.warning(
                    f"Воркер {process.pid} не остановился, принудительное завершение"
                )
                process.kill()
                process.wait(timeout=5)

            if process in self._active_workers:
                self._active_workers.remove(process)

            logger.info(f"Воркер с PID {process.pid} остановлен")
            return True

        except Exception as e:
            logger.error(f"Ошибка при остановке воркера {process.pid}: {e}")
            return False

    def scale_workers(self, target_workers: int) -> None:
        """
        Масштабировать количество воркеров до целевого значения

        Args:
            target_workers: Целевое количество воркеров
        """
        current_workers = len(self._active_workers)

        if current_workers == target_workers:
            return

        logger.info(f"Масштабирование: {current_workers} -> {target_workers} воркеров")

        if current_workers < target_workers:
            # Добавляем воркеров
            for i in range(current_workers, target_workers):
                self.start_worker(i + 1)
                time.sleep(2)  # Небольшая задержка между запусками

        elif current_workers > target_workers:
            # Убираем воркеров
            workers_to_stop = current_workers - target_workers
            for _ in range(workers_to_stop):
                if self._active_workers:
                    worker = self._active_workers[-1]  # Останавливаем последнего
                    self.stop_worker(worker)
                    time.sleep(1)

    def cleanup_dead_workers(self) -> None:
        """Удалить из списка завершившиеся воркеры"""
        alive_workers = []

        for worker in self._active_workers:
            if worker.poll() is None:  # Процесс еще работает
                alive_workers.append(worker)
            else:
                logger.info(f"Воркер с PID {worker.pid} завершился")

        self._active_workers = alive_workers

    def monitoring_loop(self) -> None:
        """Основной цикл мониторинга"""
        logger.info("Запуск цикла мониторинга памяти")

        while not self._stop_event.is_set():
            try:
                # Получаем информацию о памяти
                memory_info = self.get_memory_info()

                # Очищаем завершившихся воркеров
                self.cleanup_dead_workers()

                # Рассчитываем оптимальное количество воркеров
                optimal_workers = self.calculate_optimal_workers(memory_info)
                current_workers = len(self._active_workers)

                # Логируем статистику каждые 5 циклов (чтобы не засорять лог)
                if (
                    int(time.time()) % (self.memory_check_interval * 5)
                    < self.memory_check_interval
                ):
                    logger.info(f"Состояние системы:")
                    logger.info(
                        f"  - Память: {memory_info.used_gb:.1f}/{memory_info.total_gb:.1f} GB "
                        f"({memory_info.percent_used:.1f}% использовано)"
                    )
                    logger.info(f"  - Доступно: {memory_info.available_gb:.1f} GB")
                    logger.info(
                        f"  - Воркеров: {current_workers}/{optimal_workers} (оптимально)"
                    )

                # Масштабируем воркеров при необходимости
                if current_workers != optimal_workers:
                    self.scale_workers(optimal_workers)

                # Ждем до следующей проверки
                self._stop_event.wait(self.memory_check_interval)

            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
                self._stop_event.wait(5)  # Короткая пауза перед повтором

    def start_monitoring(self) -> None:
        """Запустить мониторинг в отдельном потоке"""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            logger.warning("Мониторинг уже запущен")
            return

        logger.info("Запуск мониторинга памяти и автомасштабирования")

        # Запускаем минимальное количество воркеров
        for i in range(self.min_workers):
            self.start_worker(i + 1)

        # Запускаем поток мониторинга
        self._monitoring_thread = Thread(target=self.monitoring_loop, daemon=True)
        self._monitoring_thread.start()

    def stop_monitoring(self) -> None:
        """Остановить мониторинг"""
        logger.info("Остановка мониторинга памяти")

        # Сигнал остановки
        self._stop_event.set()

        # Ждем завершения потока
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=10)

        # Останавливаем всех воркеров
        for worker in self._active_workers[:]:
            self.stop_worker(worker)

        logger.info("Мониторинг памяти остановлен")

    def get_status(self) -> Dict:
        """Получить текущий статус системы"""
        memory_info = self.get_memory_info()
        workers = self.get_celery_workers()

        return {
            "memory": {
                "total_gb": round(memory_info.total_gb, 2),
                "available_gb": round(memory_info.available_gb, 2),
                "used_gb": round(memory_info.used_gb, 2),
                "percent_used": round(memory_info.percent_used, 1),
                "threshold_gb": self.memory_threshold_gb,
            },
            "workers": {
                "active_count": len(self._active_workers),
                "optimal_count": self.calculate_optimal_workers(memory_info),
                "max_workers": self.max_workers,
                "min_workers": self.min_workers,
                "processes": [
                    {
                        "pid": w.pid,
                        "memory_mb": round(w.memory_mb, 1),
                        "cpu_percent": round(w.cpu_percent, 1),
                    }
                    for w in workers
                ],
            },
            "config": {
                "auto_scaling_enabled": self.auto_scaling_enabled,
                "memory_check_interval": self.memory_check_interval,
                "worker_memory_limit_gb": self.worker_memory_limit_gb,
            },
            "monitoring": {
                "is_running": self._monitoring_thread is not None
                and self._monitoring_thread.is_alive()
            },
        }


# Глобальный экземпляр монитора
memory_monitor = MemoryMonitor()


def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    try:
        logger.info(f"Получен сигнал {signum}, завершаем работу...")
        memory_monitor.stop_monitoring()
    except Exception as e:
        logger.error(f"Ошибка при завершении работы: {e}")
    finally:
        sys.exit(0)


# Регистрируем обработчики сигналов только в Windows-совместимом режиме
try:
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
except (OSError, ValueError) as e:
    logger.warning(f"Не удалось зарегистрировать обработчики сигналов: {e}")


if __name__ == "__main__":
    # Запуск как отдельный сервис
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        memory_monitor.start_monitoring()

        # Держим основной поток живым
        while True:
            time.sleep(60)
            status = memory_monitor.get_status()
            logger.info(
                f"Статус: {status['workers']['active_count']} воркеров, "
                f"{status['memory']['available_gb']:.1f} GB доступно"
            )

    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания")
    finally:
        memory_monitor.stop_monitoring()
