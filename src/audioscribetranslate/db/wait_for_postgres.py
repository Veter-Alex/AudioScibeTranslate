#!/usr/bin/env python3
"""
wait_for_postgres.py

Скрипт для ожидания готовности PostgreSQL перед запуском backend-сервиса.

Использование:
    Запускается в Docker-контейнере для предотвращения ошибок подключения,
    когда приложение стартует раньше, чем база данных готова принимать соединения.

Args:
    POSTGRES_HOST (str): Хост базы данных (env).
    POSTGRES_PORT (int): Порт базы данных (env).
    POSTGRES_DB (str): Имя базы данных (env).
    POSTGRES_USER (str): Имя пользователя (env).
    POSTGRES_PASSWORD (str): Пароль пользователя (env).

Returns:
    None

Example:
    $ python wait_for_postgres.py

Pitfalls:
    Скрипт может зациклиться, если база данных недоступна.
    Рекомендуется использовать в связке с Docker healthcheck.
"""
import os
import time

import psycopg2

host = os.environ.get("POSTGRES_HOST", "db")  # Хост базы данных
port = int(os.environ.get("POSTGRES_PORT", 5432))  # Порт базы данных
db = os.environ.get("POSTGRES_DB", "postgres")  # Имя базы данных
user = os.environ.get("POSTGRES_USER", "postgres")  # Имя пользователя
password = os.environ.get("POSTGRES_PASSWORD", "postgres")  # Пароль пользователя

while True:
    try:
        # Пробуем подключиться к базе данных
        conn = psycopg2.connect(
            dbname=db, user=user, password=password, host=host, port=port
        )
        conn.close()
        print("Postgres is ready!")
        break
    except Exception as e:
        print(f"Waiting for Postgres... {e}")
        time.sleep(1)
