#!/usr/bin/env python3
"""
Скрипт для полной очистки всех таблиц базы данных (удаляет все данные, но сохраняет структуру).
"""
import asyncio

from sqlalchemy import text

from src.audioscribetranslate.core.config import get_settings
from src.audioscribetranslate.db.session import AsyncSessionLocal

TABLES = [
    "audio_files",
    "transcripts",
    "translations",
    "summaries",
    "users"
    # Добавьте сюда остальные таблицы, если есть
]

def print_db_config():
    settings = get_settings()
    import os
    print("--- Диагностика переменных окружения ---")
    print(f"os.environ['POSTGRES_HOST']: {os.environ.get('POSTGRES_HOST')}")
    print(f"os.environ['ENV']: {os.environ.get('ENV')}")
    print(f"Файл .env.local существует: {os.path.exists('.env.local')}")
    print(f"Текущий рабочий каталог: {os.getcwd()}")
    print("------------------------------------------")
    print("--- Параметры подключения к базе данных ---")
    print(f"host: {settings.postgres_host}")
    print(f"port: {settings.postgres_port}")
    print(f"user: {settings.postgres_user}")
    print(f"db:   {settings.postgres_db}")
    print(f"url:  {settings.database_url}")
    print(f"env:  {settings.current_env_file}")
    print("------------------------------------------")

async def truncate_all_tables():
    async with AsyncSessionLocal() as db:
        try:
            for table in TABLES:
                await db.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
            await db.commit()
            print("✅ Все таблицы очищены!")
        except Exception as e:
            print(f"❌ Ошибка при очистке: {e}")
            await db.rollback()
    print("🎉 Очистка завершена!")

if __name__ == "__main__":
    print_db_config()
    asyncio.run(truncate_all_tables())
