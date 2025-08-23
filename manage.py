#!/usr/bin/env python3
"""
Скрипт для запуска AudioScribeTranslate в разных окружениях
"""
import os
import subprocess
import sys
from pathlib import Path


def run_local() -> bool:
    """Запуск в локальном режиме (без Docker)"""
    print("🚀 Запуск в локальном режиме...")
    os.environ["ENV"] = "local"

    # Проверяем наличие .env.local
    if not Path(".env.local").exists():
        print("❌ Файл .env.local не найден!")
        return False

    try:
        # Запуск через Poetry
        subprocess.run(
            [
                "poetry",
                "run",
                "uvicorn",
                "src.audioscribetranslate.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--reload",
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка запуска: {e}")
        return False

    return True


def run_services() -> bool:
    """Запуск Docker сервисов (БД, Redis, Celery, pgAdmin)"""
    print("🐳 Запуск Docker сервисов (БД, Redis, Celery, pgAdmin)...")
    os.environ["ENV"] = "docker"

    # Проверяем наличие .env
    if not Path(".env").exists():
        print("❌ Файл .env не найден!")
        return False

    try:
        # Запуск Docker сервисов (БД, Redis, Celery, pgAdmin)
        subprocess.run(
            ["docker-compose", "up", "-d", "db", "redis", "celery", "pgadmin"],
            check=True,
        )
        print("✅ Docker сервисы запущены!")
        print("📊 Доступные сервисы:")
        print("   - PostgreSQL: localhost:5432")
        print("   - Redis: localhost:6379")
        print("   - Celery Worker: работает")
        print("   - pgAdmin: http://localhost:5050")
        print("💡 Для запуска API локально используйте: python manage.py local")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка запуска Docker: {e}")
        return False

    return True


def stop_docker() -> bool:
    """Остановка Docker сервисов"""
    print("🛑 Остановка Docker сервисов...")
    try:
        subprocess.run(["docker-compose", "down"], check=True)
        print("✅ Docker сервисы остановлены!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка остановки: {e}")
        return False

    return True


def run_worker_manager() -> None:
    """Запуск менеджера воркеров с автомасштабированием"""
    print("🚀 Запуск менеджера воркеров с автомасштабированием...")

    # Проверяем настройки
    current_env = os.getenv("ENV", "local")
    print(f"   Окружение: {current_env}")

    try:
        # Устанавливаем зависимости если нужно
        subprocess.run(["poetry", "install"], check=True, capture_output=True)

        # Запускаем менеджер воркеров
        subprocess.run(
            ["poetry", "run", "python", "src/audioscribetranslate/worker_manager.py"],
            check=True,
        )

    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка запуска менеджера воркеров: {e}")
    except KeyboardInterrupt:
        print("\n⏹️ Остановка менеджера воркеров...")


def show_worker_status() -> None:
    """Показать статус воркеров"""
    print("📊 Статус воркеров:")

    try:
        # Запускаем команду статуса
        result = subprocess.run(
            [
                "poetry",
                "run",
                "python",
                "src/audioscribetranslate/worker_manager.py",
                "--status",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        print(result.stdout)

    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка получения статуса: {e}")
        if e.stderr:
            print(f"   Детали: {e.stderr}")


def stop_workers() -> None:
    """Остановить воркеры"""
    print("⏹️ Остановка воркеров...")

    try:
        result = subprocess.run(
            [
                "poetry",
                "run",
                "python",
                "src/audioscribetranslate/worker_manager.py",
                "--stop",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        print(result.stdout)
        print("✅ Воркеры остановлены")

    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка остановки воркеров: {e}")
        if e.stderr:
            print(f"   Детали: {e.stderr}")


def show_status() -> None:
    """Показать статус сервисов"""
    print("📋 Статус окружения:")
    current_env = os.getenv("ENV", "local")
    print(f"   Текущее окружение: {current_env}")

    # Показать какой .env файл будет использован
    env_files = {
        "local": ".env.local",
        "docker": ".env",
        "production": ".env.production",
    }
    env_file = env_files.get(current_env, ".env.local")
    exists = "✅" if Path(env_file).exists() else "❌"
    print(f"   Файл конфигурации: {env_file} {exists}")

    # Проверить статус Docker сервисов
    try:
        result = subprocess.run(
            ["docker-compose", "ps", "--services", "--filter", "status=running"],
            capture_output=True,
            text=True,
            check=True,
        )
        running_services = (
            result.stdout.strip().split("\n") if result.stdout.strip() else []
        )
        if running_services and running_services != [""]:
            print(f"   Docker сервисы запущены: {', '.join(running_services)}")
        else:
            print("   Docker сервисы не запущены")
    except subprocess.CalledProcessError:
        print("   Docker недоступен или сервисы не запущены")


def main() -> None:
    if len(sys.argv) < 2:
        print("🔧 Менеджер окружений AudioScribeTranslate")
        print("\nИспользование:")
        print("  python manage.py local     - Запуск API локально")
        print(
            "  python manage.py services  - Запуск Docker сервисов (БД, Redis, Celery, pgAdmin)"
        )
        print("  python manage.py docker    - Запуск всех сервисов через Docker")
        print("  python manage.py stop      - Остановка Docker сервисов")
        print("  python manage.py status    - Показать статус")
        print("\nУправление воркерами:")
        print(
            "  python manage.py workers   - Запуск менеджера воркеров с автомасштабированием"
        )
        print("  python manage.py worker-status - Показать статус воркеров")
        print("  python manage.py stop-workers  - Остановить воркеры")
        print("\nОкружения:")
        print("  local      - Разработка без Docker (.env.local)")
        print("  docker     - Разработка с Docker (.env)")
        print("  production - Продакшн (.env.production)")
        print("\nПримеры:")
        print("  ENV=production python manage.py workers  - Запуск в продакшне")
        print("  ENV=docker python manage.py services     - Запуск Docker сервисов")
        return

    command = sys.argv[1].lower()

    if command == "local":
        run_local()
    elif command == "services":
        run_services()
    elif command == "docker":
        run_services()  # Для обратной совместимости
    elif command == "stop":
        stop_docker()
    elif command == "status":
        show_status()
    elif command == "workers":
        run_worker_manager()
    elif command == "worker-status":
        show_worker_status()
    elif command == "stop-workers":
        stop_workers()
    else:
        print(f"❌ Неизвестная команда: {command}")
        print(
            "Используйте: local, services, docker, stop, status, workers, worker-status, stop-workers"
        )


if __name__ == "__main__":
    main()
