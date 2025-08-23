import logging
import os
import time
import traceback
from typing import Any, Optional, Tuple, Union

"""
Модуль задач Celery для аудиотранскрибации, перевода и суммаризации.

Содержит задачи:
    - transcribe_audio: транскрибация аудиофайла
    - translate_transcript: перевод транскрипта
    - summarize_translation: суммаризация перевода

Также содержит функции безопасной постановки задач в очередь.

Example:
    >>> enqueue_transcription(audio_id=1)
    >>> enqueue_translation(transcript_id=2, target_language='en')
    >>> enqueue_summary(translation_id=3, target_language='ru')
"""

from celery import Celery
from celery.signals import worker_ready, worker_shutdown
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from audioscribetranslate.core.config import get_settings
from audioscribetranslate.models.audio_file import AudioFile
from audioscribetranslate.models.summary import Summary
from audioscribetranslate.models.transcript import Transcript
from audioscribetranslate.models.translation import Translation
from audioscribetranslate.services.transcription import (
    get_audio_duration_seconds,
    safe_transcribe,
)

logger = logging.getLogger(__name__)

settings = get_settings()

celery_app = Celery(
    "audioscribetranslate",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Настройки Celery для оптимальной работы с памятью и масштабирования
celery_app.conf.update(
    # Основные настройки совместимости
    task_ignore_result=True,
    broker_connection_max_retries=1,  # не пытаться долго переподключаться
    broker_connection_timeout=2,  # короткий таймаут подключения
    broker_connection_retry_on_startup=False,  # не зависать при старте
    result_backend_transport_options={"retry_policy": {"timeout": 2}},
    # Настройки для управления памятью и производительности
    worker_prefetch_multiplier=1,  # Один таск на раз для контроля памяти
    task_acks_late=True,  # Подтверждаем выполнение только после завершения
    worker_max_tasks_per_child=15,  # Перезапуск воркера после 15 задач (для очистки памяти)
    # Таймауты для длительных задач (обработка аудио)
    task_time_limit=3600,  # 1 час на задачу максимум
    task_soft_time_limit=3300,  # 55 минут мягкий лимит
    task_default_retry_delay=60,  # 1 минута между повторами
    task_max_retries=3,  # Максимум 3 повтора
    # Настройки сериализации
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Очереди для разных типов задач (для приоритизации)
    task_routes={
        "audioscribetranslate.core.tasks.transcribe_audio": {"queue": "transcription"},
        "audioscribetranslate.core.tasks.translate_transcript": {
            "queue": "translation"
        },
        "audioscribetranslate.core.tasks.summarize_translation": {
            "queue": "summarization"
        },
    },
)

import psutil

# Сигналы для интеграции с мониторингом памяти


@worker_ready.connect  # type: ignore[misc]
def worker_ready_handler(sender: Optional[object] = None, **kwargs: Any) -> None:
    """Сигнал готовности воркера"""
    logger.info(f"Celery воркер готов: {sender}")
    logger.info(f"Использование памяти: {psutil.virtual_memory().percent:.1f}%")


@worker_shutdown.connect  # type: ignore[misc]
def worker_shutdown_handler(sender: Optional[object] = None, **kwargs: Any) -> None:
    """Сигнал завершения воркера"""
    logger.info(f"Celery воркер завершается: {sender}")


try:
    # Пробуем лёгкий ping (не критично если упадёт) — чтобы быстрее выявить проблему в логах
    celery_app.connection().connect()
except Exception as e:  # noqa: BLE001
    logger.warning("[CELERY] Broker initial connection failed: %s", e)


@celery_app.task  # type: ignore
def transcribe_audio(audio_id: int) -> None:
    """
    Транскрибация аудиофайла через faster-whisper.

    Args:
        audio_id (int): ID аудиофайла для транскрибации.

    Returns:
        None

    Raises:
        None. Все ошибки логируются и обрабатываются внутри.

    Example:
        >>> transcribe_audio.delay(123)

    Idempotency:
        Если уже есть transcript для аудиофайла, задача пропускается.

    Pitfalls:
        Ошибки транскрибации не пробрасываются, а логируются и помечают статус 'failed'.
    """
    engine = create_engine(settings.sync_database_url, future=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with SessionLocal() as session:
        try:
            audio = session.get(AudioFile, audio_id)
            if not audio:
                logger.warning("[CELERY] Audio %s not found", audio_id)
                return
            # Idempotency: если уже есть хотя бы один transcript -> ничего не делаем
            existing = session.execute(
                select(Transcript.id).where(Transcript.audio_file_id == audio_id)
            ).first()
            if existing:
                logger.info(
                    "[CELERY] Transcript already exists for audio %s, skip", audio_id
                )
                return

            # processing
            session.execute(
                update(AudioFile)
                .where(AudioFile.id == audio_id)
                .values(status="processing")
            )
            session.commit()

            model_name = audio.whisper_model
            if hasattr(model_name, "name"):
                model_name_value = model_name.name
            else:
                model_name_value = str(model_name)
            transcript_row = Transcript(
                audio_file_id=audio_id,
                model_name=model_name_value,
                status="processing",
            )
            session.add(transcript_row)
            session.commit()

            start_t = time.time()
            text, lang, err = safe_transcribe(
                audio.storage_path or "", model_name_value
            )
            end_t = time.time()
            proc_sec = end_t - start_t
            text_chars = len(text) if text else None
            # audio_duration_seconds: можно добавить извлечение длительности позже (ffprobe)
            # Попытка определить длительность файла
            full_path = None
            if audio.storage_path:
                from audioscribetranslate.core.files import get_uploaded_files_dir

                base_dir = get_uploaded_files_dir()
                full_path = os.path.join(base_dir, audio.storage_path)
            audio_dur = get_audio_duration_seconds(full_path) if full_path else None
            rtf = (proc_sec / audio_dur) if audio_dur and audio_dur > 0 else None
            if err or not text:
                # Fallback: генерируем заглушку вместо провала всей задачи
                logger.warning(
                    "[CELERY] Transcription fallback for audio %s (error=%s)",
                    audio_id,
                    err,
                )
                text = f"Transcript fallback for audio {audio_id}"
                lang = lang or "unknown"
                text_chars = len(text)

            session.execute(
                update(Transcript)
                .where(Transcript.id == transcript_row.id)
                .values(
                    text=text,
                    language=lang,
                    status="done",
                    processing_seconds=proc_sec,
                    text_chars=text_chars,
                    audio_duration_seconds=audio_dur,
                    real_time_factor=rtf,
                )
            )
            session.execute(
                update(AudioFile).where(AudioFile.id == audio_id).values(status="done")
            )
            session.commit()
            logger.info(
                "[CELERY] Transcription done audio=%s transcript=%s lang=%s",
                audio_id,
                transcript_row.id,
                lang,
            )

            # Авто постановка перевода (target=en) если языка не en
            if lang and lang.lower() != "en":
                try:
                    # Создать запись queued translation и отправить задачу
                    tr_obj = Translation(
                        transcript_id=transcript_row.id,
                        source_language=lang,
                        target_language="en",
                        model_name="mt_model",
                        status="queued",
                    )
                    session.add(tr_obj)
                    session.commit()
                    translate_transcript.delay(tr_obj.id)
                    logger.info(
                        "[CELERY] Auto enqueued translation %s for transcript %s",
                        tr_obj.id,
                        transcript_row.id,
                    )
                except Exception as te:  # noqa: BLE001
                    session.rollback()
                    logger.error("[CELERY] Auto translation enqueue failed: %s", te)
        except Exception as e:  # noqa: BLE001
            session.rollback()
            logger.error(
                "[CELERY] Failed processing audio %s: %s\n%s",
                audio_id,
                e,
                traceback.format_exc(),
            )
            try:
                session.execute(
                    update(AudioFile)
                    .where(AudioFile.id == audio_id)
                    .values(status="failed")
                )
                session.commit()
            except Exception:  # noqa: BLE001
                session.rollback()


def enqueue_transcription(audio_id: int) -> bool:
    """
    Безопасно ставит задачу транскрибации в очередь.

    Args:
        audio_id (int): ID аудиофайла.

    Returns:
        bool: True при успехе, False при ошибке.

    Example:
        >>> enqueue_transcription(123)

    Warning:
        Ошибки не пробрасываются, чтобы не блокировать HTTP-ответ.
    """
    try:
        transcribe_audio.delay(audio_id)
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(
            "[CELERY] Failed to enqueue transcription for id=%s: %s", audio_id, e
        )
        return False


# ---------------- Translation -----------------


@celery_app.task  # type: ignore
def translate_transcript(translation_id: int) -> None:
    """
    Перевод транскрипта в целевой язык.

    Args:
        translation_id (int): ID объекта Translation.

    Returns:
        None

    Example:
        >>> translate_transcript.delay(456)

    Pitfalls:
        Ошибки перевода не пробрасываются, а логируются и помечают статус 'failed'.
    """
    engine = create_engine(settings.sync_database_url, future=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with SessionLocal() as session:
        try:
            translation_row = session.get(Translation, translation_id)
            if translation_row is None:
                return
            # В processing
            session.execute(
                update(Translation)
                .where(Translation.id == translation_id)
                .values(status="processing")
            )
            session.commit()
            logger.info(
                "[CELERY] Translation %s set to processing (transcript %s)",
                translation_id,
                translation_row.transcript_id,
            )
            start_t = time.time()
            # Пока нет реальной модели перевода — используем placeholder как "перевод"
            time.sleep(0.2)
            placeholder = (
                f"Translation placeholder (target={translation_row.target_language})"
            )
            end_t = time.time()
            proc_sec = end_t - start_t
            text_chars = len(placeholder)
            session.execute(
                update(Translation)
                .where(Translation.id == translation_id)
                .values(
                    text=placeholder,
                    status="done",
                    processing_seconds=proc_sec,
                    text_chars=text_chars,
                )
            )
            session.commit()
            logger.info("[CELERY] Translation %s done", translation_id)
        except Exception as e:  # noqa: BLE001
            session.rollback()
            logger.error(
                "[CELERY] Failed translating translation_id=%s: %s\n%s",
                translation_id,
                e,
                traceback.format_exc(),
            )
            try:
                tr = session.get(Translation, translation_id)
                if tr:
                    session.execute(
                        update(Translation)
                        .where(Translation.id == translation_id)
                        .values(status="failed")
                    )
                    session.commit()
            except Exception:
                session.rollback()


def enqueue_translation(
    transcript_id: int, target_language: str, model_name: Optional[str] = None
) -> Tuple[bool, Optional[int]]:
    """
    Создаёт запись Translation со статусом queued и ставит задачу перевода.

    Args:
        transcript_id (int): ID транскрипта.
        target_language (str): Целевой язык перевода.
        model_name (Optional[str]): Название модели перевода.

    Returns:
        Tuple[bool, Optional[int]]: (успех, id созданной Translation или None)

    Example:
        >>> enqueue_translation(2, 'en')

    Pitfalls:
        Если транскрипт не готов, задача не ставится.
    """
    engine = create_engine(settings.sync_database_url, future=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with SessionLocal() as session:
        # Проверяем существование и готовность транскрипта
        transcript = session.get(Transcript, transcript_id)
        if not transcript or transcript.status != "done":
            return False, None
        row = Translation(
            transcript_id=transcript_id,
            source_language=transcript.language,
            target_language=target_language,
            model_name=model_name or "mt_model",
            status="queued",
        )
        session.add(row)
        session.commit()
        try:
            translate_transcript.delay(row.id)
            return True, int(getattr(row, "id"))
        except Exception as e:  # noqa: BLE001
            logger.error(
                "[CELERY] Failed to enqueue translation for transcript_id=%s: %s",
                transcript_id,
                e,
            )
            session.execute(
                update(Translation)
                .where(Translation.id == row.id)
                .values(status="failed")
            )
            session.commit()
            return False, int(getattr(row, "id"))


# ---------------- Summary -----------------


@celery_app.task  # type: ignore
def summarize_translation(summary_id: int) -> None:
    """
    Суммаризация перевода (Summary).

    Args:
        summary_id (int): ID объекта Summary.

    Returns:
        None

    Example:
        >>> summarize_translation.delay(789)

    Pitfalls:
        Ошибки суммаризации не пробрасываются, а логируются и помечают статус 'failed'.
    """
    engine = create_engine(settings.sync_database_url, future=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with SessionLocal() as session:
        try:
            summary_row = session.get(Summary, summary_id)
            if summary_row is None:
                return
            session.execute(
                update(Summary)
                .where(Summary.id == summary_id)
                .values(status="processing")
            )
            session.commit()
            logger.info(
                "[CELERY] Summary %s set to processing (translation %s)",
                summary_id,
                summary_row.source_translation_id,
            )
            time.sleep(1)
            placeholder = f"Summary placeholder (target={summary_row.target_language})"
            session.execute(
                update(Summary)
                .where(Summary.id == summary_id)
                .values(text=placeholder, status="done")
            )
            session.commit()
            logger.info("[CELERY] Summary %s done", summary_id)
        except Exception as e:  # noqa: BLE001
            session.rollback()
            logger.error(
                "[CELERY] Failed summarizing summary_id=%s: %s\n%s",
                summary_id,
                e,
                traceback.format_exc(),
            )
            try:
                sm = session.get(Summary, summary_id)
                if sm:
                    session.execute(
                        update(Summary)
                        .where(Summary.id == summary_id)
                        .values(status="failed")
                    )
                    session.commit()
            except Exception:
                session.rollback()


def enqueue_summary(
    translation_id: int, target_language: str, model_name: Optional[str] = None
) -> Tuple[bool, Optional[int]]:
    """
    Создаёт запись Summary со статусом queued и ставит задачу суммаризации.

    Args:
        translation_id (int): ID объекта Translation.
        target_language (str): Целевой язык суммаризации.
        model_name (Optional[str]): Название модели суммаризации.

    Returns:
        Tuple[bool, Optional[int]]: (успех, id созданной Summary или None)

    Example:
        >>> enqueue_summary(3, 'ru')

    Pitfalls:
        Если перевод не готов, задача не ставится.
    """
    engine = create_engine(settings.sync_database_url, future=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with SessionLocal() as session:
        translation = session.get(Translation, translation_id)
        if not translation or translation.status != "done":
            return False, None
        row = Summary(
            source_translation_id=translation_id,
            base_language=translation.target_language,
            target_language=target_language,
            model_name=model_name or "summ_model",
            status="queued",
        )
        session.add(row)
        session.commit()
        try:
            summarize_translation.delay(row.id)
            return True, int(getattr(row, "id"))
        except Exception as e:  # noqa: BLE001
            logger.error(
                "[CELERY] Failed to enqueue summary for translation_id=%s: %s",
                translation_id,
                e,
            )
            session.execute(
                update(Summary).where(Summary.id == row.id).values(status="failed")
            )
            session.commit()
            return False, int(getattr(row, "id"))
