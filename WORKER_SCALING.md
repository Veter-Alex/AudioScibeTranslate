# Система динамического масштабирования воркеров

## Обзор

Система автоматического масштабирования Celery воркеров на основе доступной памяти, специально оптимизированная для серверов Dell R620 с 8 CPU и 64GB RAM.

## Основные компоненты

### 1. MemoryMonitor (`src/audioscribetranslate/core/memory_monitor.py`)

Основной класс для мониторинга памяти и управления воркерами:

- **Мониторинг памяти**: Отслеживает использование системной памяти каждые N секунд
- **Автомасштабирование**: Автоматически запускает/останавливает воркеров на основе доступной памяти
- **Управление ресурсами**: Контролирует лимиты памяти для каждого воркера
- **Graceful shutdown**: Корректно останавливает воркеров при завершении

### 2. Worker Manager (`src/audioscribetranslate/worker_manager.py`)

CLI менеджер для управления системой масштабирования:

```bash
# Запуск автомасштабирования
python src/audioscribetranslate/worker_manager.py

# Показать статус
python src/audioscribetranslate/worker_manager.py --status

# Остановить систему
python src/audioscribetranslate/worker_manager.py --stop
```

### 3. API мониторинга (`src/audioscribetranslate/routers/monitoring.py`)

REST API для мониторинга и управления системой:

- `GET /monitoring/status` - Общий статус системы
- `GET /monitoring/memory` - Информация о памяти
- `GET /monitoring/workers` - Статус воркеров
- `POST /monitoring/workers/scale` - Ручное масштабирование
- `POST /monitoring/monitoring/start` - Запуск мониторинга
- `POST /monitoring/monitoring/stop` - Остановка мониторинга

## Конфигурация

### Переменные окружения

#### Основные настройки (.env)

```env
# Настройки динамического масштабирования воркеров
MEMORY_THRESHOLD_GB=8           # Минимальный размер свободной памяти для дополнительных воркеров
MAX_WORKERS=6                   # Максимальное количество воркеров
MIN_WORKERS=1                   # Минимальное количество воркеров
MEMORY_CHECK_INTERVAL=30        # Интервал проверки памяти в секундах
WORKER_MEMORY_LIMIT_GB=4        # Ограничение памяти на один воркер
ENABLE_AUTO_SCALING=true        # Включить автомасштабирование
```

#### Продакшн настройки (.env.production)

```env
# Оптимизировано для Dell R620 (8 CPU, 64GB RAM)
MEMORY_THRESHOLD_GB=12          # Более консервативный порог для продакшна
MAX_WORKERS=8                   # Используем все 8 CPU
MIN_WORKERS=2                   # Минимум 2 воркера в продакшне
MEMORY_CHECK_INTERVAL=20        # Чаще проверяем в продакшне
WORKER_MEMORY_LIMIT_GB=6        # Больше памяти на воркера
ENABLE_AUTO_SCALING=true
```

### Логика масштабирования

Система рассчитывает оптимальное количество воркеров по формуле:

```
available_for_workers = available_memory - 4GB (системный запас)
optimal_workers = min(available_for_workers / WORKER_MEMORY_LIMIT_GB, MAX_WORKERS)
optimal_workers = max(optimal_workers, MIN_WORKERS)

# Дополнительная проверка
if available_memory < MEMORY_THRESHOLD_GB:
    optimal_workers = max(MIN_WORKERS, optimal_workers - 1)
```

## Использование

### Через manage.py (рекомендуется)

```bash
# Запуск автомасштабирования
python manage.py workers

# Статус воркеров
python manage.py worker-status

# Остановка воркеров
python manage.py stop-workers

# Для продакшна
ENV=production python manage.py workers
```

### Через Docker Compose

```bash
# Запуск всех сервисов включая автомасштабирование
docker-compose up

# Только сервис воркеров
docker-compose up celery
```

### Прямое использование

```bash
# Прямой запуск менеджера
poetry run python src/audioscribetranslate/worker_manager.py

# Статус системы
poetry run python src/audioscribetranslate/worker_manager.py --status
```

## Мониторинг

### Через API

```bash
# Статус системы
curl http://localhost:8000/monitoring/status

# Информация о памяти
curl http://localhost:8000/monitoring/memory

# Статус воркеров
curl http://localhost:8000/monitoring/workers

# Ручное масштабирование до 4 воркеров
curl -X POST http://localhost:8000/monitoring/workers/scale?target_workers=4
```

### Через логи

Система логирует ключевые события:

- Запуск/остановка воркеров
- Изменения в использовании памяти
- Решения о масштабировании
- Ошибки и предупреждения

Пример логов:

```
2024-12-08 15:30:00 - memory_monitor - INFO - Воркер worker_1@hostname запущен с PID 12345
2024-12-08 15:30:30 - memory_monitor - INFO - Состояние системы:
2024-12-08 15:30:30 - memory_monitor - INFO -   - Память: 24.5/64.0 GB (38.3% использовано)
2024-12-08 15:30:30 - memory_monitor - INFO -   - Доступно: 32.1 GB
2024-12-08 15:30:30 - memory_monitor - INFO -   - Воркеров: 3/5 (оптимально)
2024-12-08 15:31:00 - memory_monitor - INFO - Масштабирование: 3 -> 5 воркеров
```

## Особенности Dell R620

### Оптимизация под железо

- **8 CPU**: MAX_WORKERS=8 для полного использования ядер
- **64GB RAM**: Консервативный расчет с запасом 12GB для системы
- **Серверное железо**: Стабильная работа под высокими нагрузками

### Рекомендации по настройке

1. **Продакшн конфигурация**:

   ```env
   MAX_WORKERS=8
   MIN_WORKERS=2
   MEMORY_THRESHOLD_GB=12
   WORKER_MEMORY_LIMIT_GB=6
   ```

2. **Разработка/тестирование**:

   ```env
   MAX_WORKERS=4
   MIN_WORKERS=1
   MEMORY_THRESHOLD_GB=8
   WORKER_MEMORY_LIMIT_GB=4
   ```

### Мониторинг производительности

- CPU загрузка должна быть равномерной между ядрами
- Использование памяти не должно превышать 80% от общего объема
- Каждый воркер должен использовать не более 6GB RAM

## Безопасность и надежность

### Graceful Shutdown

Система корректно обрабатывает сигналы:

- `SIGTERM` - плавная остановка воркеров
- `SIGINT` - немедленная остановка при необходимости

### Защита от перегрузки

- Лимиты памяти на воркера предотвращают OOM
- Минимальный порог памяти защищает систему
- Максимальное количество воркеров ограничивает нагрузку на CPU

### Восстановление после сбоев

- Автоматическое обнаружение завершившихся воркеров
- Перезапуск воркеров при необходимости
- Логирование всех критических событий

## Интеграция с Celery

### Настройки оптимизации

```python
celery_app.conf.update(
    worker_prefetch_multiplier=1,       # Один таск на раз
    task_acks_late=True,               # Подтверждение после выполнения
    worker_max_tasks_per_child=15,      # Перезапуск для очистки памяти
    task_time_limit=3600,              # Лимит времени на задачу
    task_soft_time_limit=3300,         # Мягкий лимит
)
```

### Очереди задач

Система поддерживает разделение задач по очередям:

- `transcription` - обработка аудио (CPU-intensive)
- `translation` - перевод текста
- `summarization` - создание саммари

## Масштабирование

### Горизонтальное масштабирование

Система готова к запуску на нескольких серверах:

- Каждый сервер управляет своими воркерами
- Общая очередь Redis для всех серверов
- Централизованная база данных

### Вертикальное масштабирование

При увеличении ресурсов сервера:

1. Обновить MAX_WORKERS
2. Увеличить WORKER_MEMORY_LIMIT_GB
3. Настроить MEMORY_THRESHOLD_GB

## Troubleshooting

### Частые проблемы

1. **Воркеры не запускаются**
   - Проверить доступность Redis
   - Убедиться в корректности настроек базы данных
   - Проверить права доступа к файлам

2. **Высокое использование памяти**
   - Уменьшить WORKER_MEMORY_LIMIT_GB
   - Увеличить MEMORY_THRESHOLD_GB
   - Уменьшить MAX_WORKERS

3. **Медленная обработка задач**
   - Увеличить количество воркеров при наличии свободной памяти
   - Проверить нагрузку на CPU
   - Оптимизировать задачи Celery

### Команды диагностики

```bash
# Статус системы
python manage.py worker-status

# Логи воркеров
docker-compose logs celery

# Использование ресурсов
htop
free -h
```

## Заключение

Система динамического масштабирования предоставляет:

✅ **Автоматическую оптимизацию ресурсов** на основе доступной памяти
✅ **Максимальное использование** возможностей Dell R620
✅ **Надежность и стабильность** в продакшн среде
✅ **Простое управление** через CLI и API
✅ **Гибкую настройку** под различные нагрузки
✅ **Детальный мониторинг** для диагностики и оптимизации
