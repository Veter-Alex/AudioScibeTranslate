#!/usr/bin/env python3
"""
wait_for_postgres.py

Скрипт для ожидания готовности PostgreSQL перед запуском backend-сервиса.
Используется в Docker-контейнере для предотвращения ошибок подключения,
когда приложение стартует раньше, чем база данных готова принимать соединения.

- Использует переменные окружения POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD.
- Проверяет соединение каждую секунду, пока не получит успешный ответ.
"""
import os
import time

import psycopg2

host = os.environ.get("POSTGRES_HOST", "db")
port = int(os.environ.get("POSTGRES_PORT", 5432))
db = os.environ.get("POSTGRES_DB", "postgres")
user = os.environ.get("POSTGRES_USER", "postgres")
password = os.environ.get("POSTGRES_PASSWORD", "postgres")

while True:
    try:
        conn = psycopg2.connect(
            dbname=db, user=user, password=password, host=host, port=port
        )
        conn.close()
        print("Postgres is ready!")
        break
    except Exception as e:
        print(f"Waiting for Postgres... {e}")
        time.sleep(1)
        time.sleep(1)
