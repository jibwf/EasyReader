import pytest
from backend.services.search import (
    _SOURCE_HEALTH,
    _record_source_success,
    _record_source_failure,
    MAX_SOURCE_HEALTH_ENTRIES,
)


@pytest.fixture(autouse=True)
def clean_health():
    _SOURCE_HEALTH.clear()
    yield
    _SOURCE_HEALTH.clear()


def test_source_health_does_not_exceed_cap():
    for i in range(MAX_SOURCE_HEALTH_ENTRIES + 100):
        _record_source_success(f"http://source-{i}.com", latency_ms=100.0)
    assert len(_SOURCE_HEALTH) == MAX_SOURCE_HEALTH_ENTRIES


def test_eviction_removes_oldest():
    for i in range(MAX_SOURCE_HEALTH_ENTRIES + 10):
        _record_source_success(f"http://source-{i}.com", latency_ms=100.0)
    assert "http://source-0.com" not in _SOURCE_HEALTH
    assert "http://source-9.com" not in _SOURCE_HEALTH
    assert f"http://source-{MAX_SOURCE_HEALTH_ENTRIES + 9}.com" in _SOURCE_HEALTH


def test_recently_accessed_entry_not_evicted():
    for i in range(MAX_SOURCE_HEALTH_ENTRIES):
        _record_source_success(f"http://source-{i}.com", latency_ms=100.0)
    _record_source_success("http://source-0.com", latency_ms=100.0)
    _record_source_success("http://source-new.com", latency_ms=100.0)
    assert "http://source-0.com" in _SOURCE_HEALTH
    assert len(_SOURCE_HEALTH) == MAX_SOURCE_HEALTH_ENTRIES


def test_failure_records_also_trigger_eviction():
    for i in range(MAX_SOURCE_HEALTH_ENTRIES + 5):
        _record_source_failure(f"http://source-{i}.com", latency_ms=500.0, error="timeout", timed_out=True)
    assert len(_SOURCE_HEALTH) == MAX_SOURCE_HEALTH_ENTRIES
