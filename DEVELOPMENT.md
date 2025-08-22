# 🚀 Руководство по локальной разработке AudioScribeTranslate

## 📋 Быстрый старт

### 1️⃣ **Подготовка окружения**
```bash
# Клонируем репозиторий
git clone https://github.com/Veter-Alex/AudioScibeTranslate.git
cd AudioScibeTranslate

# Настраиваем Poetry для in-project виртуального окружения
poetry config virtualenvs.in-project true

# Устанавливаем зависимости
poetry install
```

### 2️⃣ **Запуск Docker сервисов**
```bash
# Запуск БД, Redis, Celery Worker и pgAdmin
python manage.py services

# Проверка статуса сервисов
python manage.py status
```

### 3️⃣ **Применение миграций БД** (однократно)
```bash
# Устанавливаем окружение и применяем миграции
$env:ENV="local"
poetry run alembic upgrade head
```

### 4️⃣ **Запуск API локально**
```bash
# Запуск FastAPI сервера для разработки
python manage.py local

# Или вручную:
$env:ENV="local"
poetry run uvicorn src.audioscribetranslate.main:app --host 0.0.0.0 --port 8000 --reload
```

## 🔧 **Команды управления**

### **Управление сервисами:**
- `python manage.py services` - Запуск Docker сервисов
- `python manage.py local` - Запуск API локально  
- `python manage.py stop` - Остановка всех Docker сервисов
- `python manage.py status` - Проверка статуса сервисов

### **Окружения:**
- **local** - Разработка без Docker (API локально, сервисы в Docker)
- **docker** - Полностью через Docker Compose
- **production** - Продакшн настройки

## 📊 **Доступные сервисы при разработке:**

### **🔍 Веб-интерфейсы:**
- **API документация**: http://localhost:8000/docs
- **pgAdmin**: http://localhost:5050
  - Логин: `admin@admin.com`
  - Пароль: `admin`

### **🔧 Прямые подключения:**
- **PostgreSQL**: `localhost:5432`
  - БД: `audioscribetranslate`
  - Пользователь: `postgres`
  - Пароль: `postgres`
- **Redis**: `localhost:6379`

## 🛠️ **Структура конфигураций:**

```
.env.local      # Локальная разработка (localhost подключения)
.env           # Docker окружение (service names)
.env.production # Продакшн (template)
```

Система автоматически выберет правильный файл на основе переменной `ENV`:
- `ENV=local` → использует `.env.local`
- `ENV=docker` → использует `.env`  
- `ENV=production` → использует `.env.production`

## 🏗️ **Рабочий процесс разработки:**

1. **Запуск сервисов**: `python manage.py services`
2. **Запуск API**: `python manage.py local`
3. **Разработка** в IDE с горячей перезагрузкой
4. **Тестирование** через http://localhost:8000/docs
5. **Работа с БД** через pgAdmin (http://localhost:5050)

## 🔄 **Обработка аудио:**

После запуска Celery worker автоматически обрабатывает:
- Транскрипцию аудиофайлов (Whisper models: base, small, medium, large)
- Переводы текстов
- Генерацию саммари

## 🚀 **Готово к разработке!**

Все сервисы настроены для эффективной локальной разработки с поддержкой горячей перезагрузки, автоматических миграций и полной интеграции с Docker сервисами.
