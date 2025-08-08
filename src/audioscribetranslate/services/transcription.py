"""FastWhisper transcription service wrapper.

Provides a simple function transcribe(audio_path, model_name) -> (text, language).
Uses GPU if available (CUDA), else CPU.
Caches loaded models by (model_name, device_key) to avoid reload overhead.
"""

from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import wave
from functools import lru_cache
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

try:
    import torch  # type: ignore
except Exception:  # noqa: BLE001
    torch = None  # type: ignore

try:
    from faster_whisper import WhisperModel  # type: ignore
except Exception as e:  # noqa: BLE001
    WhisperModel = None  # type: ignore
    logger.warning("faster-whisper not installed or failed to import: %s", e)


def _select_device() -> tuple[str, str]:
    """Return (device, compute_type). Prefer cuda float16, fallback to cpu int8."""
    if torch and torch.cuda.is_available():  # type: ignore[attr-defined]
        return "cuda", "float16"
    return "cpu", "int8"


@lru_cache(maxsize=8)
def _load_model(model_name: str, device: str, compute_type: str):
    if WhisperModel is None:
        raise RuntimeError("faster-whisper not available")
    logger.info(
        "Loading Whisper model '%s' on %s (%s)", model_name, device, compute_type
    )
    return WhisperModel(model_name, device=device, compute_type=compute_type)


def transcribe_file(path: str | os.PathLike[str], model_name: str) -> tuple[str, str]:
    """Transcribe audio file and return (text, language).

    If model not available, raises RuntimeError.
    """
    device, compute_type = _select_device()
    model = _load_model(model_name, device, compute_type)
    segments, info = model.transcribe(str(path), beam_size=1)
    text_parts = []
    for seg in segments:
        text_parts.append(seg.text)
    full_text = " ".join(t.strip() for t in text_parts if t.strip())
    language = info.language or "unknown"
    return full_text, language


def safe_transcribe(
    path: str | os.PathLike[str], model_name: str
) -> tuple[str | None, str | None, str | None]:
    """Wrapper that catches exceptions. Returns (text, language, error)."""
    try:
        text, lang = transcribe_file(path, model_name)
        return text, lang, None
    except Exception as e:  # noqa: BLE001
        logger.error("Transcription failed for %s: %s", path, e)
        return None, None, str(e)


def get_audio_duration_seconds(path: str | os.PathLike[str]) -> float | None:
    """Try to obtain duration (seconds) via lightweight methods.

    Order:
      1. wave (if .wav)
      2. ffprobe (if available in PATH)
    Returns None if cannot determine.
    """
    p = Path(path)
    if not p.exists():
        return None
    # WAV fast path
    if p.suffix.lower() == ".wav":
        try:
            with contextlib.closing(wave.open(str(p), "rb")) as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0:
                    return frames / float(rate)
        except Exception:  # noqa: BLE001
            pass
    # ffprobe fallback
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
                str(p),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0:
            val = proc.stdout.strip()
            return float(val)
    except Exception:  # noqa: BLE001
        return None
    return None
