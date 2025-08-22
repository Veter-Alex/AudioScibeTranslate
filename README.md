# AudioScribeTranslate

Fullstack приложение для транскрибирования аудиофайлов на базе FastAPI, PostgreSQL, Celery и Docker.

## Описание

Бэкенд реализован на Python с использованием FastAPI, асинхронной работы с PostgreSQL, очередей задач через Celery и Redis. Управление зависимостями — poetry.

## 🚀 Быстрый запуск

### Вариант 1: Локальная разработка (без Docker)

```bash
# Установка зависимостей
poetry install

# Запуск в локальном режиме
python manage.py local
```

### Вариант 2: Docker Compose (рекомендуется)

```bash
# Запуск всех сервисов
python manage.py docker

# Остановка сервисов
python manage.py stop
```

### Проверка статуса

```bash
python manage.py status
```

## 🔧 Конфигурация окружений

Приложение поддерживает несколько окружений:

| Окружение | ENV файл | Описание |
|-----------|----------|----------|
| `local` | `.env.local` | Локальная разработка без Docker |
| `docker` | `.env` | Разработка с Docker Compose |
| `production` | `.env.production` | Продакшн окружение |

### Переключение окружений

```bash
# Установка переменной окружения
export ENV=local     # Для Linux/macOS
set ENV=local        # Для Windows CMD
$env:ENV="local"     # Для Windows PowerShell

# Или использовать менеджер окружений
python manage.py local    # Автоматически устанавливает ENV=local
python manage.py docker   # Автоматически устанавливает ENV=docker
```

## 📊 Доступные сервисы

После запуска через Docker:

- **Backend API**: <http://localhost:8000>
- **API Docs**: <http://localhost:8000/docs>
- **pgAdmin**: <http://localhost:5050> (<admin@admin.com> / admin)
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

## 🛠 Разработка
