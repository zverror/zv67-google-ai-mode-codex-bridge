"""Persist one row per request and aggregate honest local metrics."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from sqlalchemy import func, select

from zv67.persistence.db import Database
from zv67.persistence.models import RequestEvent, RequestRecord


class RequestRow(BaseModel):
    id: str
    session_id: str | None
    account_id: str | None
    model_id: str
    backend: str
    status: str
    http_status: int | None
    error_code: str | None
    latency_ms: int | None
    retry_count: int
    tool_call_count: int
    created_at: datetime
    completed_at: datetime | None


class Summary(BaseModel):
    period_hours: int
    requests: int
    successes: int
    errors: int
    active: int
    success_rate: float | None
    avg_latency_ms: int | None
    p50_latency_ms: int | None
    p95_latency_ms: int | None
    by_model: dict[str, int]
    by_account: dict[str, int]


class TimeBucket(BaseModel):
    bucket: str
    requests: int
    successes: int
    errors: int
    avg_latency_ms: int | None


def _percentile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction)))
    return ordered[index]


class RequestStatistics:
    def __init__(self, database: Database) -> None:
        self._database = database

    def start(
        self,
        *,
        model_id: str,
        backend: str,
        session_id: str | None = None,
        account_id: str | None = None,
        request_id: str | None = None,
    ) -> str:
        request_id = request_id or f"req_{uuid.uuid4().hex}"
        with self._database.session() as session:
            session.add(
                RequestRecord(
                    id=request_id,
                    session_id=session_id,
                    account_id=account_id,
                    model_id=model_id,
                    backend=backend,
                    status="STARTED",
                )
            )
        return request_id

    def finish(
        self,
        request_id: str,
        *,
        status: str,
        http_status: int | None = None,
        error_code: str | None = None,
        latency_ms: int | None = None,
        retry_count: int | None = None,
    ) -> None:
        with self._database.session() as session:
            record = session.get(RequestRecord, request_id)
            if record is None:
                raise KeyError(f"request '{request_id}' does not exist")
            record.status = status
            record.http_status = http_status
            record.error_code = error_code
            record.latency_ms = latency_ms
            if retry_count is not None:
                record.retry_count = retry_count
            record.completed_at = datetime.now(timezone.utc)

    def attach(
        self,
        request_id: str,
        *,
        session_id: str | None,
        account_id: str | None,
    ) -> None:
        with self._database.session() as session:
            record = session.get(RequestRecord, request_id)
            if record is None:
                return
            record.session_id = session_id
            record.account_id = account_id

    def mark_stale_started(self, *, error_code: str = "service_restarted") -> int:
        """Close requests left in STARTED after a process restart."""

        with self._database.session() as session:
            rows = session.scalars(
                select(RequestRecord).where(RequestRecord.status == "STARTED")
            ).all()
            now = datetime.now(timezone.utc)
            for row in rows:
                row.status = "ERROR"
                row.http_status = 499
                row.error_code = error_code
                row.completed_at = now
            return len(rows)

    def add_event(self, request_id: str, kind: str, detail: str | None = None) -> None:
        safe_detail = detail[:1000] if detail else None
        with self._database.session() as session:
            session.add(
                RequestEvent(request_id=request_id, kind=kind, detail=safe_detail)
            )

    def recent(self, limit: int = 100) -> list[RequestRow]:
        with self._database.session() as session:
            rows = session.scalars(
                select(RequestRecord)
                .order_by(RequestRecord.created_at.desc())
                .limit(min(max(limit, 1), 500))
            ).all()
            return [self._row(row) for row in rows]

    def summary(self, hours: int = 24) -> Summary:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        with self._database.session() as session:
            rows = session.scalars(
                select(RequestRecord).where(RequestRecord.created_at >= since)
            ).all()
            by_model = dict(
                session.execute(
                    select(RequestRecord.model_id, func.count())
                    .where(RequestRecord.created_at >= since)
                    .group_by(RequestRecord.model_id)
                ).all()
            )
            by_account = dict(
                session.execute(
                    select(RequestRecord.account_id, func.count())
                    .where(
                        RequestRecord.created_at >= since,
                        RequestRecord.account_id.is_not(None),
                    )
                    .group_by(RequestRecord.account_id)
                ).all()
            )
        latencies = [row.latency_ms for row in rows if row.latency_ms is not None]
        successes = sum(1 for row in rows if row.status == "SUCCESS")
        errors = sum(1 for row in rows if row.status == "ERROR")
        finished = successes + errors
        return Summary(
            period_hours=hours,
            requests=len(rows),
            successes=successes,
            errors=errors,
            active=sum(1 for row in rows if row.status == "STARTED"),
            success_rate=round(successes / finished, 4) if finished else None,
            avg_latency_ms=(
                round(sum(latencies) / len(latencies)) if latencies else None
            ),
            p50_latency_ms=_percentile(latencies, 0.5),
            p95_latency_ms=_percentile(latencies, 0.95),
            by_model={str(key): int(value) for key, value in by_model.items()},
            by_account={str(key): int(value) for key, value in by_account.items()},
        )

    def timeseries(self, hours: int = 24, bucket_minutes: int = 60) -> list[TimeBucket]:
        """Aggregate requests by UTC time bucket."""

        if bucket_minutes not in (5, 15, 30, 60, 360, 1440):
            raise ValueError("unsupported bucket size")
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        with self._database.session() as session:
            rows = session.scalars(
                select(RequestRecord).where(RequestRecord.created_at >= since)
            ).all()
        groups: dict[datetime, list[RequestRecord]] = {}
        for row in rows:
            moment = row.created_at
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            moment = moment.astimezone(timezone.utc)
            minute = (moment.minute // bucket_minutes) * bucket_minutes if bucket_minutes < 60 else 0
            if bucket_minutes <= 60:
                key = moment.replace(minute=minute if bucket_minutes < 60 else 0, second=0, microsecond=0)
            elif bucket_minutes == 360:
                key = moment.replace(hour=(moment.hour // 6) * 6, minute=0, second=0, microsecond=0)
            else:
                key = moment.replace(hour=0, minute=0, second=0, microsecond=0)
            groups.setdefault(key, []).append(row)
        result: list[TimeBucket] = []
        for key in sorted(groups):
            items = groups[key]
            latencies = [item.latency_ms for item in items if item.latency_ms is not None]
            result.append(
                TimeBucket(
                    bucket=key.isoformat(),
                    requests=len(items),
                    successes=sum(1 for item in items if item.status == "SUCCESS"),
                    errors=sum(1 for item in items if item.status == "ERROR"),
                    avg_latency_ms=(
                        round(sum(latencies) / len(latencies)) if latencies else None
                    ),
                )
            )
        return result

    @staticmethod
    def _row(record: RequestRecord) -> RequestRow:
        return RequestRow(
            id=record.id,
            session_id=record.session_id,
            account_id=record.account_id,
            model_id=record.model_id,
            backend=record.backend,
            status=record.status,
            http_status=record.http_status,
            error_code=record.error_code,
            latency_ms=record.latency_ms,
            retry_count=record.retry_count,
            tool_call_count=record.tool_call_count,
            created_at=record.created_at,
            completed_at=record.completed_at,
        )

