"""Routing strategy and concurrency tests."""

from __future__ import annotations

import pytest

from zv67.routing.router import (
    AccountRouter,
    NoAccountAvailable,
    RoutingCandidate,
    RoutingStrategy,
)

pytestmark = pytest.mark.anyio


def candidates():
    return [
        RoutingCandidate(account_id="acc_a", weight=1, concurrency_limit=2),
        RoutingCandidate(account_id="acc_b", weight=3, concurrency_limit=2),
    ]


async def test_round_robin_is_deterministic_and_skips_disabled():
    router = AccountRouter()
    pool = candidates()
    pool[1] = RoutingCandidate(account_id="acc_b", enabled=False)

    first = await router.acquire(pool, strategy=RoutingStrategy.ROUND_ROBIN)
    second = await router.acquire(pool, strategy=RoutingStrategy.ROUND_ROBIN)

    assert first.account_id == "acc_a"
    assert second.account_id == "acc_a"


async def test_weighted_round_robin_respects_weights():
    router = AccountRouter()
    pool = [
        RoutingCandidate(account_id="acc_a", weight=1, concurrency_limit=10),
        RoutingCandidate(account_id="acc_b", weight=3, concurrency_limit=10),
    ]

    picks = [
        (await router.acquire(pool, strategy=RoutingStrategy.WEIGHTED_ROUND_ROBIN)).account_id
        for _ in range(4)
    ]

    assert picks.count("acc_b") == 3
    assert picks.count("acc_a") == 1


async def test_sticky_account_keeps_session_on_one_account():
    router = AccountRouter()
    lease = await router.acquire(
        candidates(),
        strategy=RoutingStrategy.ROUND_ROBIN,
        sticky_account_id="acc_b",
    )

    assert lease.account_id == "acc_b"


async def test_manual_selection_rejects_unavailable_account():
    router = AccountRouter()
    pool = [candidates()[0]]

    with pytest.raises(NoAccountAvailable, match="acc_b"):
        await router.acquire(
            pool,
            strategy=RoutingStrategy.MANUAL,
            manual_account_id="acc_b",
        )


async def test_concurrency_limit_is_atomic():
    router = AccountRouter()
    pool = [RoutingCandidate(account_id="acc_a", concurrency_limit=1)]

    lease = await router.acquire(pool)
    assert router.active_requests("acc_a") == 1

    with pytest.raises(NoAccountAvailable):
        await router.acquire(pool)

    await router.release(lease)
    assert router.active_requests("acc_a") == 0
    second = await router.acquire(pool)
    assert second.account_id == "acc_a"


async def test_cooldown_excludes_account_and_expires():
    router = AccountRouter()
    pool = [RoutingCandidate(account_id="acc_a")]
    lease = await router.acquire(pool)
    await router.release(lease, cooldown_seconds=60)

    with pytest.raises(NoAccountAvailable):
        await router.acquire(pool)

    await router.clear_cooldown("acc_a")
    assert (await router.acquire(pool)).account_id == "acc_a"


async def test_least_busy_spreads_new_requests():
    router = AccountRouter()
    pool = candidates()

    first = await router.acquire(pool, strategy=RoutingStrategy.LEAST_BUSY)
    second = await router.acquire(pool, strategy=RoutingStrategy.LEAST_BUSY)

    assert {first.account_id, second.account_id} == {"acc_a", "acc_b"}


async def test_double_release_is_rejected():
    router = AccountRouter()
    lease = await router.acquire(candidates())
    await router.release(lease)

    with pytest.raises(ValueError):
        await router.release(lease)

