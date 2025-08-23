#!/usr/bin/env python3
"""
Менеджер воркеров с динамическим масштабированием для AudioScribeTranslate.

Использует MemoryMonitor для автоматического управления количеством Celery воркеров
на основе доступной памяти и конфигурации. Позволяет запускать мониторинг,
останавливать его, а также получать подробную статистику о состоянии системы.

Архитектурные принципы:
- Автоматическое масштабирование воркеров
- Поддержка ручного управления через аргументы командной строки
- Подробное логирование и мониторинг

Example:
    python worker_manager.py --status
    python worker_manager.py --stop

Pitfalls:
- Требует корректной настройки окружения и переменных
- Не обрабатывает ошибки подключения к Celery
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Добавляем путь к src для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from audioscribetranslate.core.config import get_settings
from audioscribetranslate.core.memory_monitor import memory_monitor


def setup_logging(level: str = "INFO") -> None:
    """
    Настройка логирования.

    Args:
        level (str): Уровень логирования (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    """
    Основная функция менеджера воркеров.

    Обрабатывает аргументы командной строки для управления мониторингом и
    получения статуса. Запускает MemoryMonitor и выводит статистику каждые 5 минут.

    Args:
        --log-level: Уровень логирования
        --status: Показать текущий статус
        --stop: Остановить мониторинг
    """
    parser = argparse.ArgumentParser(
        description="Менеджер Celery воркеров с автомасштабированием"
    )
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    parser.add_argument("--status", action="store_true", help="Показать текущий статус")
    parser.add_argument("--stop", action="store_true", help="Остановить мониторинг")

    args = parser.parse_args()

    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    settings = get_settings()

    if args.status:
        # Показать статус
        status = memory_monitor.get_status()
        print("\n=== Статус системы ===")
        print(
            f"Память: {status['memory']['used_gb']:.1f}/{status['memory']['total_gb']:.1f} GB "
            f"({status['memory']['percent_used']:.1f}% использовано)"
        )
        print(f"Доступно: {status['memory']['available_gb']:.1f} GB")
        print(f"Порог: {status['memory']['threshold_gb']} GB")
        print()
        print(f"Воркеров активно: {status['workers']['active_count']}")
        print(f"Оптимально: {status['workers']['optimal_count']}")
        print(
            f"Диапазон: {status['workers']['min_workers']}-{status['workers']['max_workers']}"
        )
        print()
        print(
            f"Автомасштабирование: {'включено' if status['config']['auto_scaling_enabled'] else 'отключено'}"
        )
        print(f"Интервал проверки: {status['config']['memory_check_interval']} сек")
        print(
            f"Лимит памяти на воркера: {status['config']['worker_memory_limit_gb']} GB"
        )
        print(
            f"Мониторинг запущен: {'да' if status['monitoring']['is_running'] else 'нет'}"
        )

        if status["workers"]["processes"]:
            print("\nАктивные процессы:")
            for proc in status["workers"]["processes"]:
                print(
                    f"  PID {proc['pid']}: {proc['memory_mb']:.1f} MB, CPU {proc['cpu_percent']:.1f}%"
                )

        return

    if args.stop:
        # Остановить мониторинг
        logger.info("Остановка менеджера воркеров...")
        memory_monitor.stop_monitoring()
        logger.info("Менеджер воркеров остановлен")
        return

    # Запуск основного режима
    logger.info("=== Менеджер Celery воркеров с автомасштабированием ===")
    # logger.info(f"Целевое окружение: {settings.environment}")
    logger.info(f"Текущий env файл: {getattr(settings, 'current_env_file', 'unknown')}")
    logger.info(
        f"Автомасштабирование: {'включено' if settings.enable_auto_scaling else 'отключено'}"
    )
    logger.info(f"Диапазон воркеров: {settings.min_workers}-{settings.max_workers}")
    logger.info(f"Порог памяти: {settings.memory_threshold_gb} GB")

    if not settings.enable_auto_scaling:
        logger.warning("Автомасштабирование отключено в настройках!")
        logger.info("Запуск в режиме фиксированного количества воркеров")

    try:
        # Запускаем мониторинг
        memory_monitor.start_monitoring()

        logger.info("Менеджер воркеров запущен. Нажмите Ctrl+C для остановки")

        # Основной цикл - показываем статистику каждые 5 минут
        last_status_time: float = 0.0

        while True:
            current_time = time.time()

            # Показываем расширенную статистику каждые 5 минут
            if current_time - last_status_time >= 300:  # 5 минут
                status = memory_monitor.get_status()
                logger.info("=== Периодическая статистика ===")
                logger.info(
                    f"Память: {status['memory']['available_gb']:.1f} GB доступно "
                    f"({status['memory']['percent_used']:.1f}% используется)"
                )
                logger.info(
                    f"Воркеров: {status['workers']['active_count']}/{status['workers']['optimal_count']} "
                    f"(диапазон {status['workers']['min_workers']}-{status['workers']['max_workers']})"
                )

                if status["workers"]["processes"]:
                    total_memory = sum(
                        p["memory_mb"] for p in status["workers"]["processes"]
                    )
                    avg_cpu = sum(
                        p["cpu_percent"] for p in status["workers"]["processes"]
                    ) / len(status["workers"]["processes"])
                    logger.info(
                        f"Воркеры используют {total_memory:.0f} MB памяти, средний CPU {avg_cpu:.1f}%"
                    )

                last_status_time = current_time

            time.sleep(60)  # Проверяем каждую минуту

    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
    finally:
        logger.info("Завершение работы менеджера воркеров...")
        memory_monitor.stop_monitoring()
        logger.info("Менеджер воркеров завершен")


if __name__ == "__main__":
    main()
