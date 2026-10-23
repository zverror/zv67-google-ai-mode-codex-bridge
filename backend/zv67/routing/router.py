"""Atomic account selection with concurrency and cooldown limits."""

from __future__ import annotations

import asyncio
import time
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class RoutingStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_BUSY = "least_busy"
    MANUAL = "manual"


class NoAccountAvailable(RuntimeError):
    """No candidate satisfies enabled, concurrency and cooldown rules."""


@dataclass(frozen=True)
class RoutingCandidate:
    account_id: str
    weight: int = 100
    concurrency_limit: int = 1
    enabled: bool = True
    status: str = "UNKNOWN"


@dataclass(frozen=True)
class AccountLease:
    account_id: str
    acquired_at: float


@dataclass
class _RouterState:
    cursor: int = 0
    weights: dict[str, int] = field(default_factory=dict)
    active: Counter[str] = field(default_factory=Counter)
    cooldown_until: dict[str, float] = field(default_factory=dict)


class AccountRouter:
    """In-process router. One lease equals one allowed in-flight request."""

    def __init__(self) -> None:
        self._state = _RouterState()
        self._lock = asyncio.Lock()

    def active_requests(self, account_id: str) -> int:
        return self._state.active[account_id]

    def in_cooldown(self, account_id: str, now: float | None = None) -> bool:
        until = self._state.cooldown_until.get(account_id, 0.0)
        return until > (time.monotonic() if now is None else now)

    async def acquire(
        self,
        candidates: Iterable[RoutingCandidate],
        *,
        strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN,
        sticky_account_id: str | None = None,
        manual_account_id: str | None = None,
    ) -> AccountLease:
        async with self._lock:
            now = time.monotonic()
            usable = [
                candidate
                for candidate in sorted(candidates, key=lambda item: item.account_id)
                if self._usable(candidate, now)
            ]
            if not usable:
                raise NoAccountAvailable("no enabled account is currently available")
            by_id = {candidate.account_id: candidate for candidate in usable}

            if manual_account_id is not None:
                if manual_account_id not in by_id:
                    raise NoAccountAvailable(
                        f"requested account '{manual_account_id}' is unavailable"
                    )
                chosen = by_id[manual_account_id]
            elif sticky_account_id is not None and sticky_account_id in by_id:
                chosen = by_id[sticky_account_id]
            elif strategy is RoutingStrategy.MANUAL:
                raise NoAccountAvailable("manual strategy requires an account id")
            elif strategy is RoutingStrategy.LEAST_BUSY:
                chosen = min(
                    usable,
                    key=lambda item: (
                        self._state.active[item.account_id] / item.concurrency_limit,
                        -item.weight,
                        item.account_id,
                    ),
                )
            elif strategy is RoutingStrategy.WEIGHTED_ROUND_ROBIN:
                chosen = self._weighted_choice(usable)
            else:
                chosen = usable[self._state.cursor % len(usable)]
                self._state.cursor += 1

            self._state.active[chosen.account_id] += 1
            return AccountLease(account_id=chosen.account_id, acquired_at=now)

    def _usable(self, candidate: RoutingCandidate, now: float) -> bool:
        if not candidate.enabled:
            return False
        if candidate.status in ("DISABLED", "UNAUTHORIZED"):
            return False
        if self.in_cooldown(candidate.account_id, now):
            return False
        if self._state.active[candidate.account_id] >= candidate.concurrency_limit:
            return False
        return True

    def _weighted_choice(self, usable: list[RoutingCandidate]) -> RoutingCandidate:
        total = 0
        best: RoutingCandidate | None = None
        best_current = 0
        for candidate in usable:
            current = self._state.weights.get(candidate.account_id, 0) + candidate.weight
            self._state.weights[candidate.account_id] = current
            total += candidate.weight
            if best is None or current > best_current:
                best = candidate
                best_current = current
        assert best is not None
        self._state.weights[best.account_id] -= total
        return best

    async def release(
        self,
        lease: AccountLease,
        *,
        cooldown_seconds: float | None = None,
    ) -> None:
        async with self._lock:
            current = self._state.active[lease.account_id]
            if current <= 0:
                raise ValueError("lease released more times than acquired")
            self._state.active[lease.account_id] = current - 1
            if cooldown_seconds and cooldown_seconds > 0:
                self._state.cooldown_until[lease.account_id] = (
                    time.monotonic() + cooldown_seconds
                )

    async def clear_cooldown(self, account_id: str) -> None:
        async with self._lock:
            self._state.cooldown_until.pop(account_id, None)

