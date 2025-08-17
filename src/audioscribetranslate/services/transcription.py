"""Сервис транскрипции на основе FastWhisper.

Предоставляет чистый интерфейс для транскрипции аудио с автоматическим выбором устройства,
кэшированием моделей и возможностями извлечения длительности аудио.

Возможности:
- Автоматический выбор GPU/CPU устройства
- Кэширование моделей для избежания повторной загрузки
- Извлечение длительности аудио (WAV + резервный ffprobe)
- Комплексная обработка ошибок и логирование
- Управление конфигурацией
- Поддержка инъекции зависимостей
- Мониторинг производительности и статистика
- Гибкая архитектура с возможностью расширения

Архитектурные принципы:
- Service-oriented архитектура для лучшей тестируемости
- Protocol-based подход для стратегий извлечения длительности
- LRU кэширование с детальными метриками
- Graceful degradation при отсутствии зависимостей
- Полная обратная совместимость с legacy API
"""

# Импорты с поддержкой Python 3.8+
from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import time
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple, Union
from weakref import WeakValueDictionary

# Настраиваем логгер для модуля транскрипции
logger = logging.getLogger(__name__)

# Опциональные зависимости с graceful degradation
# Эти модули могут отсутствовать, и сервис должен корректно работать без них
torch: Optional[object] = None
WhisperModel: Optional[type] = None

try:
    import torch  # type: ignore

    logger.debug("PyTorch успешно загружен - доступно GPU ускорение")
except ImportError:
    logger.debug("PyTorch недоступен - GPU ускорение отключено")

try:
    from faster_whisper import WhisperModel  # type: ignore

    logger.debug("faster-whisper успешно загружен")
except ImportError as e:
    logger.warning("faster-whisper не установлен: %s", e)
    WhisperModel = None


@dataclass(frozen=True)
class TranscriptionConfig:
    """Конфигурация для сервиса транскрипции.

    Все параметры настройки сервиса собраны в одном месте для удобства управления.
    Использует frozen=True для неизменяемости и лучшей производительности.

    Атрибуты:
        default_model: Модель Whisper по умолчанию ('tiny', 'base', 'small', 'medium', 'large')
        beam_size: Размер луча для beam search (больше = точнее, но медленнее)
        cache_size: Максимальное количество моделей в кэше
        ffprobe_timeout: Таймаут для ffprobe в секундах
        enable_gpu: Разрешить использование GPU если доступно
        log_performance: Логировать метрики производительности
    """

    default_model: str = "base"  # Баланс между скоростью и качеством
    beam_size: int = 1  # Быстрый режим для real-time приложений
    cache_size: int = 8  # Достаточно для большинства сценариев
    ffprobe_timeout: float = 5.0  # Предотвращает зависание на поврежденных файлах
    enable_gpu: bool = True  # Автоматическое использование GPU
    log_performance: bool = True  # Включить мониторинг производительности


class DeviceType(str, Enum):
    """Поддерживаемые типы вычислительных устройств.

    Наследуется от str для удобства сериализации и логирования.
    """

    CUDA = "cuda"  # NVIDIA GPU с CUDA поддержкой
    CPU = "cpu"  # Центральный процессор


class ComputeType(str, Enum):
    """Поддерживаемые типы вычислений для оптимизации производительности.

    Различные типы данных обеспечивают компромисс между скоростью и точностью.
    """

    FLOAT16 = "float16"  # Половинная точность для GPU (быстрее, меньше памяти)
    INT8 = "int8"  # Квантизация для CPU (значительно быстрее)


@dataclass(frozen=True)
class TranscriptionResult:
    """Результат транскрипции аудио с расширенными метриками.

    Содержит не только текст и язык, но и подробную информацию о процессе
    транскрипции для мониторинга и оптимизации производительности.

    Атрибуты:
        text: Транскрибированный текст
        language: Обнаруженный язык (ISO код)
        confidence: Уверенность модели в определении языка (0.0-1.0)
        processing_time: Время обработки в секундах
        model_used: Использованная модель Whisper
        device_used: Устройство для вычислений (cuda/cpu)
    """

    text: str
    language: str
    confidence: Optional[float] = None
    processing_time: Optional[float] = None  # Для анализа производительности
    model_used: Optional[str] = None  # Для отладки и мониторинга
    device_used: Optional[str] = None  # Для оптимизации распределения нагрузки


@dataclass(frozen=True)
class TranscriptionError:
    """Информация об ошибке транскрипции с контекстом для диагностики.

    Расширенная информация об ошибках помогает в отладке и мониторинге
    системы в production среде.

    Атрибуты:
        message: Описание ошибки
        error_type: Тип исключения Python
        file_path: Путь к проблемному файлу
        timestamp: Время возникновения ошибки (Unix timestamp)
    """

    message: str
    error_type: str
    file_path: Optional[str] = None
    timestamp: float = field(default_factory=time.time)  # Автоматическая метка времени


@dataclass(frozen=True)
class ModelCacheStats:
    """Статистика производительности кэша моделей.

    Предоставляет детальную информацию о работе кэша для оптимизации
    конфигурации и мониторинга эффективности.

    Атрибуты:
        cache_size: Текущее количество моделей в кэше
        cache_hits: Количество успешных обращений к кэшу
        cache_misses: Количество промахов кэша (требующих загрузки)
        loaded_models: Список ключей загруженных моделей
    """

    cache_size: int
    cache_hits: int
    cache_misses: int
    loaded_models: List[str]

    @property
    def hit_ratio(self) -> float:
        """Вычисляет коэффициент попаданий в кэш.

        Returns:
            Отношение попаданий к общему количеству обращений (0.0-1.0)
            Высокий коэффициент (>0.8) указывает на эффективное использование кэша
        """
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0


class AudioDurationExtractor(Protocol):
    """Протокол для стратегий извлечения длительности аудио.

    Использует паттерн Strategy для поддержки различных методов определения
    длительности аудиофайлов. Позволяет легко добавлять новые форматы и методы.

    Методы:
        extract_duration: Извлекает длительность в секундах или None при неудаче
    """

    def extract_duration(self, path: Path) -> Optional[float]:
        """Извлекает длительность аудио в секундах.

        Args:
            path: Путь к аудиофайлу

        Returns:
            Длительность в секундах или None если не удалось определить
        """
        ...


class WaveDurationExtractor:
    """Извлекает длительность из WAV файлов используя встроенный модуль wave.

    Быстрый и надежный метод для WAV файлов, не требует внешних зависимостей.
    Работает только с несжатыми WAV файлами.
    """

    def extract_duration(self, path: Path) -> Optional[float]:
        """Извлекает длительность из WAV файла через анализ заголовка.

        Args:
            path: Путь к WAV файлу

        Returns:
            Длительность в секундах или None для не-WAV файлов или при ошибке
        """
        # Проверяем расширение файла для быстрого исключения не-WAV файлов
        if path.suffix.lower() != ".wav":
            return None

        try:
            # Используем contextlib для автоматического закрытия файла
            with contextlib.closing(wave.open(str(path), "rb")) as wf:
                frames = wf.getnframes()  # Общее количество фреймов
                rate = wf.getframerate()  # Частота дискретизации

                # Избегаем деления на ноль
                return frames / float(rate) if rate > 0 else None

        except Exception as e:
            # Логируем на уровне debug, так как это ожидаемое поведение для некоторых файлов
            logger.debug("Не удалось извлечь длительность WAV для %s: %s", path, e)
            return None


class FFProbeDurationExtractor:
    """Извлекает длительность используя ffprobe (если доступен).

    Универсальный метод для большинства аудио/видео форматов.
    Требует установленного FFmpeg в системе.

    Атрибуты:
        timeout: Максимальное время ожидания выполнения ffprobe
    """

    def __init__(self, timeout: float = 5.0):
        """Инициализирует экстрактор с настраиваемым таймаутом.

        Args:
            timeout: Максимальное время ожидания в секундах
        """
        self.timeout = timeout

    def extract_duration(self, path: Path) -> Optional[float]:
        """Извлекает длительность используя ffprobe.

        Выполняет системный вызов ffprobe для получения метаданных файла.
        Обрабатывает различные типы ошибок и таймауты.

        Args:
            path: Путь к аудиофайлу

        Returns:
            Длительность в секундах или None при неудаче
        """
        try:
            # Формируем команду ffprobe для извлечения только длительности
            proc = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",  # Подавляем лишний вывод
                    "-show_entries",
                    "format=duration",  # Показываем только длительность
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",  # Формат вывода: только значение
                    str(path),
                ],
                stdout=subprocess.PIPE,  # Захватываем стандартный вывод
                stderr=subprocess.PIPE,  # Захватываем ошибки
                text=True,  # Декодируем как текст
                timeout=self.timeout,  # Применяем таймаут
            )

            # Проверяем успешность выполнения команды
            if proc.returncode == 0:
                val = proc.stdout.strip()
                return float(val) if val else None

        except (
            subprocess.TimeoutExpired,  # Превышен таймаут
            subprocess.SubprocessError,  # Ошибка выполнения
            ValueError,  # Не удалось преобразовать в float
            FileNotFoundError,  # ffprobe не найден в системе
        ) as e:
            # Логируем на уровне debug - отсутствие ffprobe это нормально
            logger.debug("ffprobe не смог извлечь длительность для %s: %s", path, e)

        return None


class AudioDurationService:
    """Сервис для извлечения длительности аудиофайлов с множественными стратегиями.

    Использует паттерн Chain of Responsibility для применения различных методов
    извлечения длительности в порядке приоритета. Обеспечивает максимальную
    совместимость с различными форматами файлов.

    Стратегии применяются в порядке:
    1. WaveDurationExtractor - быстро для WAV файлов
    2. FFProbeDurationExtractor - универсально для остальных форматов

    Атрибуты:
        extractors: Список экстракторов в порядке приоритета
    """

    def __init__(self) -> None:
        """Инициализирует сервис с предустановленными экстракторами.

        Порядок экстракторов важен - более быстрые и специализированные
        должны идти первыми.
        """
        self.extractors: list[AudioDurationExtractor] = [
            WaveDurationExtractor(),  # Быстрый метод для WAV
            FFProbeDurationExtractor(),  # Универсальный метод
        ]

    def get_duration_seconds(
        self, path: Union[str, os.PathLike[str]]
    ) -> Optional[float]:
        """Получает длительность аудио в секундах используя доступные экстракторы.

        Пробует каждый экстрактор по очереди до первого успешного результата.
        Это обеспечивает graceful fallback между различными методами.

        Args:
            path: Путь к аудиофайлу (str или PathLike объект)

        Returns:
            Длительность в секундах или None если не удалось определить
        """
        path_obj = Path(path)

        # Проверяем существование файла перед попытками извлечения
        if not path_obj.exists():
            logger.debug("Аудиофайл не найден: %s", path_obj)
            return None

        # Пробуем каждый экстрактор в порядке приоритета
        for extractor in self.extractors:
            duration = extractor.extract_duration(path_obj)
            if duration is not None:
                logger.debug(
                    "Длительность извлечена для %s: %.2f секунд", path_obj, duration
                )
                return duration

        # Если ни один экстрактор не сработал
        logger.debug("Не удалось извлечь длительность для %s", path_obj)
        return None


class DeviceSelector:
    """Управляет автоматическим выбором устройства и типа вычислений.

    Определяет оптимальное устройство (GPU/CPU) и тип данных для максимальной
    производительности на конкретной системе. Учитывает конфигурацию пользователя
    и доступность аппаратного обеспечения.

    Атрибуты:
        config: Конфигурация транскрипции с настройками устройства
    """

    def __init__(self, config: TranscriptionConfig):
        """Инициализирует селектор с конфигурацией.

        Args:
            config: Конфигурация с настройками использования GPU
        """
        self.config = config

    def select_optimal_device(self) -> Tuple[DeviceType, ComputeType]:
        """Выбирает оптимальное устройство и тип вычислений.

        Логика выбора:
        1. Если GPU разрешен в конфигурации И PyTorch доступен И CUDA доступна
           -> Используем CUDA с float16 (быстро + экономия памяти)
        2. Иначе -> Используем CPU с int8 (квантизация для ускорения)

        Returns:
            Кортеж (тип_устройства, тип_вычислений)
        """
        if (
            self.config.enable_gpu  # GPU разрешен в настройках
            and torch  # PyTorch доступен
            and hasattr(torch, "cuda")  # CUDA модуль присутствует
            and torch.cuda.is_available()  # CUDA устройство доступно
        ):
            logger.debug("CUDA доступна - используем GPU ускорение")
            return DeviceType.CUDA, ComputeType.FLOAT16

        logger.debug("Используем CPU (GPU отключен или недоступен)")
        return DeviceType.CPU, ComputeType.INT8

    def get_device_info(self) -> Dict[str, Any]:
        """Получает детальную информацию о доступных устройствах.

        Собирает информацию о системе для диагностики и мониторинга.
        Полезно для отладки проблем с производительностью.

        Returns:
            Словарь с информацией об устройствах:
            - available_devices: Список доступных устройств
            - cuda_available: Доступность CUDA (если PyTorch установлен)
            - cuda_device_count: Количество CUDA устройств
            - cuda_device_name: Название первого GPU
        """
        info = {"available_devices": ["cpu"]}  # CPU всегда доступен

        # Добавляем информацию о CUDA если PyTorch доступен
        if torch and hasattr(torch, "cuda"):
            info["cuda_available"] = torch.cuda.is_available()

            if torch.cuda.is_available():
                info["available_devices"].append("cuda")
                info["cuda_device_count"] = torch.cuda.device_count()
                info["cuda_device_name"] = torch.cuda.get_device_name(0)

        return info


class WhisperModelCache:
    """Продвинутый менеджер кэширования моделей Whisper с LRU вытеснением и метриками.

    Реализует intelligent кэширование для минимизации времени загрузки моделей.
    Использует LRU (Least Recently Used) алгоритм для оптимального использования памяти.
    Собирает детальную статистику для мониторинга производительности.

    Особенности:
    - LRU вытеснение для оптимального использования памяти
    - Детальные метрики производительности (hits/misses/evictions)
    - Thread-safe операции (если не используется из разных потоков одновременно)
    - Graceful handling ошибок загрузки

    Атрибуты:
        config: Конфигурация кэша
        max_size: Максимальное количество моделей в кэше
        _cache: Основное хранилище моделей
        _access_order: Порядок доступа для LRU алгоритма
        _stats: Статистика производительности кэша
    """

    def __init__(self, config: TranscriptionConfig):
        """Инициализирует кэш с конфигурацией.

        Args:
            config: Конфигурация с размером кэша и другими настройками
        """
        self.config = config
        self.max_size = config.cache_size
        self._cache: Dict[str, Any] = {}  # Хранилище моделей
        self._access_order: List[str] = []  # LRU порядок доступа
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}  # Метрики

    def get_model(
        self, model_name: str, device: DeviceType, compute_type: ComputeType
    ) -> Any:
        """Получает или загружает модель Whisper с продвинутым кэшированием и метриками.

        Реализует следующую логику:
        1. Проверка наличия в кэше (cache hit)
        2. При попадании - обновление LRU порядка
        3. При промахе - освобождение места и загрузка новой модели
        4. Обновление статистики на каждом этапе

        Args:
            model_name: Название модели Whisper ('tiny', 'base', 'small', etc.)
            device: Тип устройства (CUDA/CPU)
            compute_type: Тип вычислений (float16/int8)

        Returns:
            Загруженная модель Whisper

        Raises:
            RuntimeError: Если faster-whisper не установлен
            Exception: Любые ошибки загрузки модели (проброшены выше)
        """
        # Проверяем доступность faster-whisper
        if WhisperModel is None:
            raise RuntimeError(
                "faster-whisper недоступен - установите командой: pip install faster-whisper"
            )

        # Создаем уникальный ключ для кэша на основе всех параметров
        cache_key = f"{model_name}_{device.value}_{compute_type.value}"

        # Проверяем попадание в кэш
        if cache_key in self._cache:
            self._stats["hits"] += 1
            self._update_access_order(cache_key)  # Обновляем LRU порядок
            logger.debug("Попадание в кэш модели: %s", cache_key)
            return self._cache[cache_key]

        # Промах кэша - нужно загружать модель
        self._stats["misses"] += 1
        logger.debug("Промах кэша модели: %s", cache_key)

        # Освобождаем место если кэш заполнен
        self._evict_if_needed()

        # Загружаем новую модель с замером времени
        start_time = time.time()
        logger.info(
            "Загружаем модель Whisper '%s' на %s (%s)",
            model_name,
            device.value,
            compute_type.value,
        )

        # Создаем экземпляр модели
        model = WhisperModel(
            model_name, device=device.value, compute_type=compute_type.value
        )

        load_time = time.time() - start_time
        logger.info("Модель загружена за %.2f секунд", load_time)

        # Сохраняем в кэш и обновляем порядок доступа
        self._cache[cache_key] = model
        self._access_order.append(cache_key)

        return model

    def _update_access_order(self, cache_key: str) -> None:
        """Обновляет порядок доступа для LRU алгоритма.

        Перемещает ключ в конец списка, отмечая его как недавно использованный.
        Это ключевая часть LRU реализации.

        Args:
            cache_key: Ключ для перемещения в конец списка
        """
        # Удаляем ключ из текущей позиции (если есть)
        if cache_key in self._access_order:
            self._access_order.remove(cache_key)

        # Добавляем в конец как наиболее недавно использованный
        self._access_order.append(cache_key)

    def _evict_if_needed(self) -> None:
        """Вытесняет наименее недавно использованные модели при заполнении кэша.

        Реализует LRU eviction policy:
        - Удаляет модели с начала списка _access_order
        - Продолжает до освобождения достаточного места
        - Обновляет статистику вытеснений
        """
        while len(self._cache) >= self.max_size:
            # Проверяем наличие элементов для вытеснения
            if not self._access_order:
                break

            # Берем наименее недавно использованную модель (начало списка)
            oldest_key = self._access_order.pop(0)

            # Удаляем из кэша если ключ все еще присутствует
            if oldest_key in self._cache:
                del self._cache[oldest_key]
                self._stats["evictions"] += 1
                logger.debug("Вытеснена модель из кэша: %s", oldest_key)

    def get_stats(self) -> ModelCacheStats:
        """Получает статистику производительности кэша.

        Returns:
            Объект со статистикой включая hit ratio и список загруженных моделей
        """
        return ModelCacheStats(
            cache_size=len(self._cache),
            cache_hits=self._stats["hits"],
            cache_misses=self._stats["misses"],
            loaded_models=list(self._cache.keys()),
        )

    def clear_cache(self) -> None:
        """Очищает все кэшированные модели.

        Полезно для освобождения памяти или сброса состояния кэша.
        Сбрасывает статистику доступа, но сохраняет общие метрики.
        """
        cleared_count = len(self._cache)
        self._cache.clear()
        self._access_order.clear()
        logger.info("Очищено %d моделей из кэша", cleared_count)


class TranscriptionService:
    """Расширенный сервис для операций транскрипции аудио с комплексными возможностями.

    Главный сервисный класс, объединяющий все компоненты транскрипции в единую систему.
    Использует паттерн Dependency Injection для лучшей тестируемости и гибкости.

    Архитектурные принципы:
    - Single Responsibility: каждый компонент отвечает за свою область
    - Dependency Injection: все зависимости инжектируются через конструктор
    - Comprehensive Monitoring: детальное логирование и метрики
    - Graceful Error Handling: корректная обработка всех типов ошибок

    Атрибуты:
        config: Конфигурация сервиса
        model_cache: Менеджер кэширования моделей
        device_selector: Селектор устройств вычислений
        duration_service: Сервис определения длительности аудио
    """

    def __init__(
        self,
        config: Optional[TranscriptionConfig] = None,
        model_cache: Optional[WhisperModelCache] = None,
        device_selector: Optional[DeviceSelector] = None,
        duration_service: Optional[AudioDurationService] = None,
    ) -> None:
        """Инициализирует сервис с поддержкой инъекции зависимостей.

        Позволяет заменить любой компонент для тестирования или кастомизации.
        Создает компоненты по умолчанию если не предоставлены.

        Args:
            config: Конфигурация сервиса (по умолчанию создается стандартная)
            model_cache: Кэш моделей (по умолчанию создается с конфигурацией)
            device_selector: Селектор устройств (по умолчанию создается с конфигурацией)
            duration_service: Сервис длительности (по умолчанию создается стандартный)
        """
        self.config = config or TranscriptionConfig()
        self.model_cache = model_cache or WhisperModelCache(self.config)
        self.device_selector = device_selector or DeviceSelector(self.config)
        self.duration_service = duration_service or AudioDurationService()

    def transcribe_file(
        self,
        path: Union[str, os.PathLike[str]],
        model_name: Optional[str] = None,
    ) -> TranscriptionResult:
        """Транскрибирует аудиофайл с расширенными метриками и обработкой ошибок.

        Основной метод транскрипции с полным циклом обработки:
        1. Определение оптимального устройства и модели
        2. Загрузка/получение модели из кэша
        3. Выполнение транскрипции с замером времени
        4. Сборка результата с метриками
        5. Логирование производительности

        Args:
            path: Путь к аудиофайлу для транскрипции
            model_name: Название модели (используется default_model из конфигурации если не указано)

        Returns:
            TranscriptionResult с текстом, языком и метриками производительности

        Raises:
            RuntimeError: Если faster-whisper недоступен
            Exception: Любые ошибки загрузки модели или транскрипции
        """
        # Используем модель по умолчанию если не указана
        model_name = model_name or self.config.default_model

        # Определяем оптимальное устройство для данной системы
        device, compute_type = self.device_selector.select_optimal_device()

        # Начинаем замер времени обработки
        start_time = time.time()
        path_str = str(path)

        logger.debug(
            "Начинаем транскрипцию: файл=%s, модель=%s, устройство=%s",
            path_str,
            model_name,
            device.value,
        )

        try:
            # Получаем модель (из кэша или загружаем новую)
            model = self.model_cache.get_model(model_name, device, compute_type)

            # Выполняем транскрипцию
            # transcribe возвращает генератор сегментов и словарь с информацией
            segments_gen, info_dict = model.transcribe(
                path_str, beam_size=self.config.beam_size
            )

            # Собираем текст из всех сегментов
            # Фильтруем пустые сегменты для качественного результата
            text_parts = [seg.text for seg in segments_gen if seg.text.strip()]
            full_text = " ".join(part.strip() for part in text_parts)

            # Извлекаем метаданные из результата Whisper
            language = info_dict.get("language", "unknown")
            confidence = info_dict.get("language_probability", None)
            processing_time = time.time() - start_time

            # Логируем результаты если включен мониторинг производительности
            if self.config.log_performance:
                logger.info(
                    "Транскрипция завершена: файл=%s, время=%.2fс, символов=%d, язык=%s",
                    path_str,
                    processing_time,
                    len(full_text),
                    language,
                )

            # Создаем результат с полными метриками
            return TranscriptionResult(
                text=full_text,
                language=language,
                confidence=confidence,
                processing_time=processing_time,
                model_used=model_name,
                device_used=device.value,
            )

        except Exception as e:
            # Логируем ошибку с контекстом для диагностики
            processing_time = time.time() - start_time
            logger.error(
                "Ошибка транскрипции: файл=%s, время=%.2fс, ошибка=%s",
                path_str,
                processing_time,
                str(e),
            )
            # Проброс исключения для обработки выше по стеку
            raise

    def safe_transcribe(
        self,
        path: Union[str, os.PathLike[str]],
        model_name: Optional[str] = None,
    ) -> Union[TranscriptionResult, TranscriptionError]:
        """Безопасная обертка транскрипции с комплексной обработкой ошибок.

        Не выбрасывает исключения, а возвращает объект ошибки с детальной информацией.
        Полезно для batch обработки, где одна ошибка не должна останавливать весь процесс.

        Args:
            path: Путь к аудиофайлу для транскрипции
            model_name: Название модели (опционально)

        Returns:
            TranscriptionResult при успехе или TranscriptionError при ошибке
        """
        try:
            return self.transcribe_file(path, model_name)
        except Exception as e:
            error_msg = f"Ошибка транскрипции для {path}: {e}"
            logger.error(error_msg)

            # Создаем детальный объект ошибки для анализа
            return TranscriptionError(
                message=str(e),
                error_type=type(e).__name__,
                file_path=str(path),
            )

    def get_audio_duration(self, path: Union[str, os.PathLike[str]]) -> Optional[float]:
        """Получает длительность аудиофайла в секундах.

        Делегирует вызов специализированному сервису длительности.

        Args:
            path: Путь к аудиофайлу

        Returns:
            Длительность в секундах или None если не удалось определить
        """
        return self.duration_service.get_duration_seconds(path)

    def get_service_stats(self) -> Dict[str, Any]:
        """Получает комплексную статистику работы сервиса.

        Собирает метрики со всех компонентов для мониторинга и оптимизации.
        Полезно для dashboard мониторинга и профилирования производительности.

        Returns:
            Словарь со статистикой:
            - cache_stats: Метрики кэша моделей (попадания, промахи, коэффициент)
            - device_info: Информация о доступных устройствах
            - config: Текущая конфигурация сервиса
        """
        cache_stats = self.model_cache.get_stats()
        device_info = self.device_selector.get_device_info()

        return {
            "cache_stats": {
                "size": cache_stats.cache_size,
                "hits": cache_stats.cache_hits,
                "misses": cache_stats.cache_misses,
                "hit_ratio": cache_stats.hit_ratio,
                "loaded_models": cache_stats.loaded_models,
            },
            "device_info": device_info,
            "config": {
                "default_model": self.config.default_model,
                "beam_size": self.config.beam_size,
                "cache_size": self.config.cache_size,
                "gpu_enabled": self.config.enable_gpu,
            },
        }

    def clear_cache(self) -> None:
        """Очищает кэш моделей.

        Полезно для освобождения памяти или принудительной перезагрузки моделей.
        """
        self.model_cache.clear_cache()

    def warm_up_model(self, model_name: Optional[str] = None) -> None:
        """Предварительно загружает модель для ускорения первой транскрипции.

        Устраняет задержку "холодного старта" путем предзагрузки модели в кэш.
        Особенно полезно в production среде для обеспечения стабильного времени отклика.

        Args:
            model_name: Название модели для предзагрузки (используется default_model если не указано)
        """
        model_name = model_name or self.config.default_model
        device, compute_type = self.device_selector.select_optimal_device()

        logger.info("Предзагрузка модели: %s", model_name)
        start_time = time.time()

        # Загружаем модель в кэш
        self.model_cache.get_model(model_name, device, compute_type)

        warm_up_time = time.time() - start_time
        logger.info("Предзагрузка завершена за %.2f секунд", warm_up_time)


# ============================================================================
# ГЛОБАЛЬНЫЕ ОБЪЕКТЫ И LEGACY API
# ============================================================================

# Глобальный экземпляр сервиса с конфигурацией по умолчанию
# Используется legacy функциями для обратной совместимости
_default_config = TranscriptionConfig()
_transcription_service = TranscriptionService(_default_config)


# ============================================================================
# LEGACY ФУНКЦИИ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ
# ============================================================================
# Эти функции сохраняют существующий API для совместимости с текущим кодом
# Внутренне используют новую архитектуру сервисов


def transcribe_file(
    path: Union[str, os.PathLike[str]], model_name: str
) -> Tuple[str, str]:
    """Legacy функция для обратной совместимости.

    Обертка над новым TranscriptionService.transcribe_file()
    с упрощенным возвращаемым значением.

    Args:
        path: Путь к аудиофайлу
        model_name: Название модели Whisper

    Returns:
        Кортеж (текст, язык) как в оригинальном API
    """
    result = _transcription_service.transcribe_file(path, model_name)
    return result.text, result.language


def safe_transcribe(
    path: Union[str, os.PathLike[str]], model_name: str
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Legacy функция для обратной совместимости.

    Обертка над новым TranscriptionService.safe_transcribe()
    с упрощенным возвращаемым значением.

    Args:
        path: Путь к аудиофайлу
        model_name: Название модели Whisper

    Returns:
        Кортеж (текст, язык, ошибка) как в оригинальном API
        При успехе: (текст, язык, None)
        При ошибке: (None, None, сообщение_об_ошибке)
    """
    result = _transcription_service.safe_transcribe(path, model_name)
    if isinstance(result, TranscriptionResult):
        return result.text, result.language, None
    else:
        return None, None, result.message


def get_audio_duration_seconds(path: Union[str, os.PathLike[str]]) -> Optional[float]:
    """Legacy функция для обратной совместимости.

    Обертка над новым TranscriptionService.get_audio_duration()

    Args:
        path: Путь к аудиофайлу

    Returns:
        Длительность в секундах или None
    """
    return _transcription_service.get_audio_duration(path)


# ============================================================================
# РАСШИРЕННЫЕ UTILITY ФУНКЦИИ
# ============================================================================
# Новые функции для работы с расширенными возможностями сервиса


def get_transcription_stats() -> Dict[str, Any]:
    """Получает текущую статистику сервиса транскрипции.

    Удобная функция для мониторинга производительности глобального сервиса.

    Returns:
        Словарь со статистикой кэша, устройств и конфигурации
    """
    return _transcription_service.get_service_stats()


def warm_up_default_model() -> None:
    """Предзагружает модель транскрипции по умолчанию.

    Устраняет задержку первого вызова путем предварительной загрузки модели в кэш.
    Рекомендуется вызывать при старте приложения в production среде.
    """
    _transcription_service.warm_up_model()


def clear_model_cache() -> None:
    """Очищает глобальный кэш моделей.

    Освобождает память, занятую кэшированными моделями.
    Полезно для управления памятью в долгоживущих приложениях.
    """
    _transcription_service.clear_cache()


def create_transcription_service(
    config: Optional[TranscriptionConfig] = None,
) -> TranscriptionService:
    """Фабричная функция для создания нового экземпляра TranscriptionService.

    Позволяет создавать сервисы с кастомными конфигурациями для специфических задач.
    Каждый сервис имеет собственный кэш и настройки.

    Args:
        config: Кастомная конфигурация (создается стандартная если не указана)

    Returns:
        Новый экземпляр TranscriptionService

    Example:
        # Создание сервиса с большим кэшем для batch обработки
        config = TranscriptionConfig(cache_size=16, beam_size=5)
        service = create_transcription_service(config)

        # Создание сервиса только для CPU
        cpu_config = TranscriptionConfig(enable_gpu=False)
        cpu_service = create_transcription_service(cpu_config)
    """
    return TranscriptionService(config or TranscriptionConfig())
