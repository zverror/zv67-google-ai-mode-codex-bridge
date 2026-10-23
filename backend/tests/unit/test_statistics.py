"""Statistics aggregation tests."""

from __future__ import annotations

import pytest

from zv67.statistics.collector import RequestStatistics


@pytest.fixture
def stats(client, app):
    return RequestStatistics(app.state.database)


def test_summary_counts_errors_and_latency_percentiles(client, stats):
    fast = stats.start(model_id="zv67-mock", backend="mock")
    stats.finish(fast, status="SUCCESS", http_status=200, latency_ms=10)

    slow = stats.start(model_id="zv67-mock", backend="mock")
    stats.finish(slow, status="SUCCESS", http_status=200, latency_ms=100)

    failed = stats.start(model_id="zv67-mock", backend="mock")
    stats.finish(
        failed,
        status="ERROR",
        http_status=400,
        error_code="invalid_request",
        latency_ms=30,
    )

    summary = stats.summary(hours=24)

    assert summary.requests == 3
    assert summary.successes == 2
    assert summary.errors == 1
    assert summary.active == 0
    assert summary.success_rate == pytest.approx(0.6667)
    assert summary.avg_latency_ms == 47
    assert summary.p50_latency_ms == 30
    assert summary.p95_latency_ms == 100
    assert summary.by_model == {"zv67-mock": 3}


def test_active_requests_are_reported(client, stats):
    stats.start(model_id="zv67-mock", backend="mock", account_id="acc_1")

    summary = stats.summary(hours=24)

    assert summary.active == 1
    assert summary.success_rate is None
    assert summary.by_account == {"acc_1": 1}


def test_recent_returns_newest_first(client, stats):
    first = stats.start(model_id="zv67-mock", backend="mock")
    stats.finish(first, status="SUCCESS", http_status=200, latency_ms=5)
    second = stats.start(model_id="zv67-mock", backend="mock")
    stats.finish(second, status="SUCCESS", http_status=200, latency_ms=6)

    rows = stats.recent(limit=10)

    assert [row.id for row in rows] == [second, first]

