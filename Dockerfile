# syntax=docker/dockerfile:1
FROM python:3.10-slim

# Установка зависимостей системы
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Установка poetry
RUN pip install --upgrade pip && pip install poetry

# Установка рабочей директории
WORKDIR /app

# Копирование зависимостей poetry, README.md и исходного кода
COPY pyproject.toml poetry.lock* README.md ./
COPY src ./src
COPY src/audioscribetranslate/db/wait_for_postgres.py ./wait_for_postgres.py

# Копирование файлов миграций Alembic
COPY alembic.ini ./
COPY alembic ./alembic

# Установка зависимостей через poetry и psycopg2 для wait_for_postgres
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main \
    && pip install psycopg2-binary

# Копирование .env
COPY .env .env

# Открытие порта
EXPOSE 8000

# Команда запуска
CMD ["uvicorn", "src.audioscribetranslate.main:app", "--host", "0.0.0.0", "--port", "8000"]
