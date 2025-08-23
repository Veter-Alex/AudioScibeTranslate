
"""
:module: src/audioscribetranslate/core/memory_monitor.py
Тесты мониторинга памяти и автомасштабирования воркеров.
Требования: MEM-101, MEM-102, MEM-103
# Проверка сценариев из JIRA MEM-228
"""
import pytest

from src.audioscribetranslate.core.memory_monitor import MemoryInfo, MemoryMonitor


# MOCK: Подменяем psutil для edge-case тестов
class DummyMemory:
    def __init__(self, total: float, available: float, used: float, percent: float, free: float) -> None:
        self.total = total
        self.available = available
        self.used = used
        self.percent = percent
        self.free = free

def test_get_memory_info_returns_valid_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: get_memory_info возвращает MemoryInfo с корректными типами (MEM-101)"""
    monitor = MemoryMonitor()
    info = monitor.get_memory_info()
    assert isinstance(info, MemoryInfo)
    assert info.total_gb > 0
    assert info.available_gb > 0
    assert 0 <= info.percent_used <= 100


def test_calculate_optimal_workers_basic() -> None:
    """Happy path: расчет оптимального числа воркеров при достаточной памяти (MEM-102)"""
    monitor = MemoryMonitor()
    mem = MemoryInfo(total_gb=64, available_gb=32, used_gb=32, percent_used=50, free_gb=32)
    optimal = monitor.calculate_optimal_workers(mem)
    assert monitor.min_workers <= optimal <= monitor.max_workers


def test_calculate_optimal_workers_low_memory() -> None:
    """Edge case: доступная память ниже порога — воркеров меньше (MEM-102, баг #33)"""
    monitor = MemoryMonitor()
    mem = MemoryInfo(total_gb=64, available_gb=2, used_gb=62, percent_used=97, free_gb=2)
    optimal = monitor.calculate_optimal_workers(mem)
    assert optimal == monitor.min_workers


def test_calculate_optimal_workers_auto_scaling_disabled() -> None:
    """Негативный тест: автомасштабирование отключено — всегда min_workers (MEM-102)"""
    monitor = MemoryMonitor()
    monitor.auto_scaling_enabled = False
    mem = MemoryInfo(total_gb=64, available_gb=32, used_gb=32, percent_used=50, free_gb=32)
    optimal = monitor.calculate_optimal_workers(mem)
    assert optimal == monitor.min_workers

# MOCK: Проверка get_status структуры
def test_get_status_structure() -> None:
    """Edge case: get_status возвращает все ключи (MEM-103)"""
    monitor = MemoryMonitor()
    status = monitor.get_status()
    assert "memory" in status
    assert "workers" in status
    assert "config" in status
    assert "monitoring" in status
    assert "config" in status
    assert "monitoring" in status
    assert "monitoring" in status
