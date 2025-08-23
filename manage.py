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

    # Определяем путь к Poetry
    poetry_path = os.path.join(os.getenv("APPDATA", ""), "Python", "Scripts", "poetry.exe")
    if not Path(poetry_path).exists():
        poetry_path = "poetry"  # Fallback на системную команду

    try:
        # Запуск через Poetry
        subprocess.run(
            [
                poetry_path,
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


def run_processing_chains() -> None:
    """Запуск менеджера цепочек обработки"""
    print("⛓️ Запуск менеджера цепочек обработки...")

    # Проверяем настройки
    current_env = os.getenv("ENV", "local")
    print(f"   Окружение: {current_env}")

    # Определяем путь к Poetry
    poetry_path = os.path.join(os.getenv("APPDATA", ""), "Python", "Scripts", "poetry.exe")
    if not Path(poetry_path).exists():
        poetry_path = "poetry"  # Fallback на системную команду

    try:
        # Устанавливаем зависимости если нужно
        subprocess.run([poetry_path, "install"], check=True, capture_output=True)

        # Запускаем менеджер цепочек
        subprocess.run(
            [poetry_path, "run", "python", "-c", 
             "from src.audioscribetranslate.core.chain_manager import start_chain_manager; start_chain_manager(); import time; time.sleep(1000)"],
            check=True,
        )

    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка запуска менеджера цепочек: {e}")
    except KeyboardInterrupt:
        print("\n⏹️ Остановка менеджера цепочек...")


def show_chains_status() -> None:
    """Показать статус цепочек обработки"""
    print("⛓️ Статус цепочек обработки:")

    # Определяем путь к Poetry
    poetry_path = os.path.join(os.getenv("APPDATA", ""), "Python", "Scripts", "poetry.exe")
    if not Path(poetry_path).exists():
        poetry_path = "poetry"  # Fallback на системную команду

    try:
        # Запускаем команду статуса цепочек
        result = subprocess.run(
            [
                poetry_path,
                "run",
                "python",
                "-c",
                """
from src.audioscribetranslate.core.chain_manager import get_chain_manager
from src.audioscribetranslate.core.config import get_settings
import psutil

manager = get_chain_manager()
settings = get_settings()

print(f"Доступно памяти: {psutil.virtual_memory().available / (1024**3):.1f} GB")
print(f"Минимум для запуска: {settings.min_free_memory_gb} GB")
print(f"Максимум воркеров: {settings.max_workers}")
print(f"Включены цепочки: {'Да' if settings.enable_processing_chains else 'Нет'}")

# Статус очереди
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from src.audioscribetranslate.models.audio_file import AudioFile

engine = create_engine(settings.sync_database_url)
SessionLocal = sessionmaker(bind=engine)
with SessionLocal() as session:
    queued = session.execute(select(AudioFile).where(AudioFile.status == 'queued')).scalars().all()
    processing = session.execute(select(AudioFile).where(AudioFile.status == 'processing')).scalars().all()
    print(f"Файлов в очереди: {len(queued)}")
    print(f"Файлов в обработке: {len(processing)}")
                """
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        print(result.stdout)

    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка получения статуса цепочек: {e}")
        if e.stderr:
            print(f"   Детали: {e.stderr}")


def stop_chains() -> None:
    """Остановить цепочки обработки"""
    print("⏹️ Остановка цепочек обработки...")

    # Определяем путь к Poetry
    poetry_path = os.path.join(os.getenv("APPDATA", ""), "Python", "Scripts", "poetry.exe")
    if not Path(poetry_path).exists():
        poetry_path = "poetry"  # Fallback на системную команду

    try:
        result = subprocess.run(
            [
                poetry_path,
                "run",
                "python",
                "-c",
                "from src.audioscribetranslate.core.chain_manager import stop_chain_manager; stop_chain_manager(); print('Цепочки остановлены')",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        print(result.stdout)
        print("✅ Цепочки обработки остановлены")

    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка остановки цепочек: {e}")
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
        print("\nУправление цепочками обработки:")
        print("  python manage.py chains        - Запуск менеджера цепочек обработки")
        print("  python manage.py chains-status - Показать статус цепочек")
        print("  python manage.py stop-chains   - Остановить цепочки")
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
    elif command == "chains":
        run_processing_chains()
    elif command == "chains-status":
        show_chains_status()
    elif command == "stop-chains":
        stop_chains()
    else:
        print(f"❌ Неизвестная команда: {command}")
        print(
            "Используйте: local, services, docker, stop, status, chains, chains-status, stop-chains"
        )


if __name__ == "__main__":
    main()
