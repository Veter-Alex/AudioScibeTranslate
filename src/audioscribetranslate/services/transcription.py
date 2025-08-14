"""FastWhisper transcription service wrapper.

Provides a clean interface for audio transcription with automatic device selection,
model caching, and duration extraction capabilities.

Features:
- Automatic GPU/CPU device selection
- Model caching to avoid reload overhead
- Audio duration extraction (WAV + ffprobe fallback)
- Comprehensive error handling and logging
- Configuration management
- Dependency injection support
"""

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

logger = logging.getLogger(__name__)

# Optional dependencies with graceful degradation
torch: Optional[object] = None
WhisperModel: Optional[type] = None

try:
    import torch  # type: ignore

    logger.debug("PyTorch loaded successfully")
except ImportError:
    logger.debug("PyTorch not available - GPU acceleration disabled")

try:
    from faster_whisper import WhisperModel  # type: ignore

    logger.debug("faster-whisper loaded successfully")
except ImportError as e:
    logger.warning("faster-whisper not installed: %s", e)
    WhisperModel = None


@dataclass(frozen=True)
class TranscriptionConfig:
    """Configuration for transcription service."""

    default_model: str = "base"
    beam_size: int = 1
    cache_size: int = 8
    ffprobe_timeout: float = 5.0
    enable_gpu: bool = True
    log_performance: bool = True


class DeviceType(str, Enum):
    """Supported compute devices."""

    CUDA = "cuda"
    CPU = "cpu"


class ComputeType(str, Enum):
    """Supported compute types."""

    FLOAT16 = "float16"
    INT8 = "int8"


@dataclass(frozen=True)
class TranscriptionResult:
    """Result of audio transcription."""

    text: str
    language: str
    confidence: Optional[float] = None
    processing_time: Optional[float] = None
    model_used: Optional[str] = None
    device_used: Optional[str] = None


@dataclass(frozen=True)
class TranscriptionError:
    """Error result from transcription attempt."""

    message: str
    error_type: str
    file_path: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ModelCacheStats:
    """Statistics for model cache performance."""

    cache_size: int
    cache_hits: int
    cache_misses: int
    loaded_models: List[str]

    @property
    def hit_ratio(self) -> float:
        """Calculate cache hit ratio."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0


class AudioDurationExtractor(Protocol):
    """Protocol for audio duration extraction strategies."""

    def extract_duration(self, path: Path) -> Optional[float]:
        """Extract duration in seconds, return None if unable."""
        ...


class WaveDurationExtractor:
    """Extract duration from WAV files using wave module."""

    def extract_duration(self, path: Path) -> Optional[float]:
        """Extract duration from WAV file."""
        if path.suffix.lower() != ".wav":
            return None
        try:
            with contextlib.closing(wave.open(str(path), "rb")) as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return frames / float(rate) if rate > 0 else None
        except Exception as e:
            logger.debug("WAV duration extraction failed for %s: %s", path, e)
            return None


class FFProbeDurationExtractor:
    """Extract duration using ffprobe (if available)."""

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    def extract_duration(self, path: Path) -> Optional[float]:
        """Extract duration using ffprobe."""
        try:
            proc = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.timeout,
            )
            if proc.returncode == 0:
                val = proc.stdout.strip()
                return float(val) if val else None
        except (
            subprocess.TimeoutExpired,
            subprocess.SubprocessError,
            ValueError,
            FileNotFoundError,
        ) as e:
            logger.debug("ffprobe duration extraction failed for %s: %s", path, e)
        return None


class AudioDurationService:
    """Service for extracting audio file duration using multiple strategies."""

    def __init__(self) -> None:
        self.extractors: list[AudioDurationExtractor] = [
            WaveDurationExtractor(),
            FFProbeDurationExtractor(),
        ]

    def get_duration_seconds(
        self, path: Union[str, os.PathLike[str]]
    ) -> Optional[float]:
        """Get audio duration in seconds using available extractors."""
        path_obj = Path(path)
        if not path_obj.exists():
            logger.debug("Audio file not found: %s", path_obj)
            return None

        for extractor in self.extractors:
            duration = extractor.extract_duration(path_obj)
            if duration is not None:
                logger.debug(
                    "Duration extracted for %s: %.2f seconds", path_obj, duration
                )
                return duration

        logger.debug("Could not extract duration for %s", path_obj)
        return None


class DeviceSelector:
    """Handles automatic device and compute type selection."""

    def __init__(self, config: TranscriptionConfig):
        self.config = config

    def select_optimal_device(self) -> Tuple[DeviceType, ComputeType]:
        """Select optimal device and compute type based on hardware availability."""
        if (
            self.config.enable_gpu
            and torch
            and hasattr(torch, "cuda")
            and torch.cuda.is_available()
        ):
            logger.debug("CUDA available - using GPU acceleration")
            return DeviceType.CUDA, ComputeType.FLOAT16

        logger.debug("Using CPU (GPU disabled or unavailable)")
        return DeviceType.CPU, ComputeType.INT8

    def get_device_info(self) -> Dict[str, Any]:
        """Get detailed device information."""
        info = {"available_devices": ["cpu"]}

        if torch and hasattr(torch, "cuda"):
            info["cuda_available"] = torch.cuda.is_available()
            if torch.cuda.is_available():
                info["available_devices"].append("cuda")
                info["cuda_device_count"] = torch.cuda.device_count()
                info["cuda_device_name"] = torch.cuda.get_device_name(0)

        return info


class WhisperModelCache:
    """Advanced cached Whisper model manager with LRU eviction and metrics."""

    def __init__(self, config: TranscriptionConfig):
        self.config = config
        self.max_size = config.cache_size
        self._cache: Dict[str, Any] = {}
        self._access_order: List[str] = []
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    def get_model(
        self, model_name: str, device: DeviceType, compute_type: ComputeType
    ) -> Any:
        """Get or load Whisper model with advanced caching and metrics."""
        if WhisperModel is None:
            raise RuntimeError(
                "faster-whisper not available - install with: pip install faster-whisper"
            )

        cache_key = f"{model_name}_{device.value}_{compute_type.value}"

        # Check cache hit
        if cache_key in self._cache:
            self._stats["hits"] += 1
            self._update_access_order(cache_key)
            logger.debug("Model cache hit: %s", cache_key)
            return self._cache[cache_key]

        # Cache miss - need to load model
        self._stats["misses"] += 1
        logger.debug("Model cache miss: %s", cache_key)

        # Make space if needed
        self._evict_if_needed()

        # Load new model
        start_time = time.time()
        logger.info(
            "Loading Whisper model '%s' on %s (%s)",
            model_name,
            device.value,
            compute_type.value,
        )

        model = WhisperModel(
            model_name, device=device.value, compute_type=compute_type.value
        )

        load_time = time.time() - start_time
        logger.info("Model loaded in %.2f seconds", load_time)

        # Cache the model
        self._cache[cache_key] = model
        self._access_order.append(cache_key)

        return model

    def _update_access_order(self, cache_key: str) -> None:
        """Update LRU access order."""
        if cache_key in self._access_order:
            self._access_order.remove(cache_key)
        self._access_order.append(cache_key)

    def _evict_if_needed(self) -> None:
        """Evict least recently used model if cache is full."""
        while len(self._cache) >= self.max_size:
            if not self._access_order:
                break

            oldest_key = self._access_order.pop(0)
            if oldest_key in self._cache:
                del self._cache[oldest_key]
                self._stats["evictions"] += 1
                logger.debug("Evicted model from cache: %s", oldest_key)

    def get_stats(self) -> ModelCacheStats:
        """Get cache performance statistics."""
        return ModelCacheStats(
            cache_size=len(self._cache),
            cache_hits=self._stats["hits"],
            cache_misses=self._stats["misses"],
            loaded_models=list(self._cache.keys()),
        )

    def clear_cache(self) -> None:
        """Clear all cached models."""
        cleared_count = len(self._cache)
        self._cache.clear()
        self._access_order.clear()
        logger.info("Cleared %d models from cache", cleared_count)


class TranscriptionService:
    """Enhanced service for audio transcription operations with comprehensive features."""

    def __init__(
        self,
        config: Optional[TranscriptionConfig] = None,
        model_cache: Optional[WhisperModelCache] = None,
        device_selector: Optional[DeviceSelector] = None,
        duration_service: Optional[AudioDurationService] = None,
    ) -> None:
        """Initialize with dependency injection support."""
        self.config = config or TranscriptionConfig()
        self.model_cache = model_cache or WhisperModelCache(self.config)
        self.device_selector = device_selector or DeviceSelector(self.config)
        self.duration_service = duration_service or AudioDurationService()

    def transcribe_file(
        self,
        path: Union[str, os.PathLike[str]],
        model_name: Optional[str] = None,
    ) -> TranscriptionResult:
        """Transcribe audio file with enhanced metrics and error handling."""
        model_name = model_name or self.config.default_model
        device, compute_type = self.device_selector.select_optimal_device()

        start_time = time.time()
        path_str = str(path)

        logger.debug(
            "Starting transcription: file=%s, model=%s, device=%s",
            path_str,
            model_name,
            device.value,
        )

        try:
            model = self.model_cache.get_model(model_name, device, compute_type)

            # Perform transcription
            segments_gen, info_dict = model.transcribe(
                path_str, beam_size=self.config.beam_size
            )

            # Collect text segments
            text_parts = [seg.text for seg in segments_gen if seg.text.strip()]
            full_text = " ".join(part.strip() for part in text_parts)

            language = info_dict.get("language", "unknown")
            confidence = info_dict.get("language_probability", None)
            processing_time = time.time() - start_time

            if self.config.log_performance:
                logger.info(
                    "Transcription completed: file=%s, duration=%.2fs, chars=%d, language=%s",
                    path_str,
                    processing_time,
                    len(full_text),
                    language,
                )

            return TranscriptionResult(
                text=full_text,
                language=language,
                confidence=confidence,
                processing_time=processing_time,
                model_used=model_name,
                device_used=device.value,
            )

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                "Transcription failed: file=%s, duration=%.2fs, error=%s",
                path_str,
                processing_time,
                str(e),
            )
            raise

    def safe_transcribe(
        self,
        path: Union[str, os.PathLike[str]],
        model_name: Optional[str] = None,
    ) -> Union[TranscriptionResult, TranscriptionError]:
        """Safe transcription wrapper with comprehensive error handling."""
        try:
            return self.transcribe_file(path, model_name)
        except Exception as e:
            error_msg = f"Transcription failed for {path}: {e}"
            logger.error(error_msg)
            return TranscriptionError(
                message=str(e),
                error_type=type(e).__name__,
                file_path=str(path),
            )

    def get_audio_duration(self, path: Union[str, os.PathLike[str]]) -> Optional[float]:
        """Get audio file duration in seconds."""
        return self.duration_service.get_duration_seconds(path)

    def get_service_stats(self) -> Dict[str, Any]:
        """Get comprehensive service statistics."""
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
        """Clear model cache."""
        self.model_cache.clear_cache()

    def warm_up_model(self, model_name: Optional[str] = None) -> None:
        """Pre-load model for faster first transcription."""
        model_name = model_name or self.config.default_model
        device, compute_type = self.device_selector.select_optimal_device()

        logger.info("Warming up model: %s", model_name)
        start_time = time.time()

        self.model_cache.get_model(model_name, device, compute_type)

        warm_up_time = time.time() - start_time
        logger.info("Model warm-up completed in %.2f seconds", warm_up_time)


# Global service instance with default configuration
_default_config = TranscriptionConfig()
_transcription_service = TranscriptionService(_default_config)


# Backward compatibility functions with enhanced functionality
def transcribe_file(
    path: Union[str, os.PathLike[str]], model_name: str
) -> Tuple[str, str]:
    """Legacy function for backward compatibility."""
    result = _transcription_service.transcribe_file(path, model_name)
    return result.text, result.language


def safe_transcribe(
    path: Union[str, os.PathLike[str]], model_name: str
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Legacy function for backward compatibility."""
    result = _transcription_service.safe_transcribe(path, model_name)
    if isinstance(result, TranscriptionResult):
        return result.text, result.language, None
    else:
        return None, None, result.message


def get_audio_duration_seconds(path: Union[str, os.PathLike[str]]) -> Optional[float]:
    """Legacy function for backward compatibility."""
    return _transcription_service.get_audio_duration(path)


# Enhanced utility functions
def get_transcription_stats() -> Dict[str, Any]:
    """Get current transcription service statistics."""
    return _transcription_service.get_service_stats()


def warm_up_default_model() -> None:
    """Warm up the default transcription model."""
    _transcription_service.warm_up_model()


def clear_model_cache() -> None:
    """Clear the global model cache."""
    _transcription_service.clear_cache()


def create_transcription_service(
    config: Optional[TranscriptionConfig] = None,
) -> TranscriptionService:
    """Factory function to create a new TranscriptionService instance."""
    return TranscriptionService(config or TranscriptionConfig())
