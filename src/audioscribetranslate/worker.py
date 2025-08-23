"""
Точка входа для запуска Celery worker через docker-compose.

Назначение:
- Импортирует celery_app для корректного старта воркера
- Используется как entrypoint в Docker и при ручном запуске

Example:
	celery -A audioscribetranslate.worker worker --loglevel=info
"""

from audioscribetranslate.core.tasks import celery_app
