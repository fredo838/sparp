import pytest
from typing import Any, Self
from src.sparp.sparp import SPARP, StopConditions, SparpResult
from tests.unit.helpers import req_gen, inspect_response


@pytest.mark.asyncio
class TestSPARPStopConditions:
    async def test_stop_on_hard_fail(self: Self, failing_server: Any) -> None:
        """Verify the loop exits after the very first HARD_FAIL."""
        cond: StopConditions = StopConditions(stop_on_hard_fail=True)
        # We send 10 requests, but it should stop after the 1st
        sparp: SPARP = SPARP(req_gen(10, 8767), inspect_response=inspect_response, stop_conditions=cond, concurrency=1)
        result: SparpResult = await sparp._main()

        assert len(result.failed) == 1
        assert result.stats.success == 0

    async def test_stop_on_soft_fail(self: Self, rate_limited_server: Any) -> None:
        """Verify the loop exits immediately when a SOFT_FAIL (429) is encountered."""
        cond: StopConditions = StopConditions(stop_on_soft_fail=True)
        # rate_limited_server returns 429 for the first two attempts of any value
        sparp: SPARP = SPARP(req_gen(5, 8766), inspect_response=inspect_response, stop_conditions=cond, concurrency=1)
        result: SparpResult = await sparp._main()

        # It should stop at the first request because it receives a SOFT_FAIL
        assert result.stats.soft_retries == 1
        assert result.stats.success == 0

    async def test_stop_on_max_retries_soft_reached(self: Self, rate_limited_server: Any) -> None:
        """Verify the loop exits when one specific request exhausts its retry budget."""
        cond: StopConditions = StopConditions(stop_on_max_retries_by_soft_fail_reached=True)
        # Server requires 3 attempts to succeed. We set max retries to 1 (total 2 attempts).
        sparp: SPARP = SPARP(
            req_gen(5, 8766),
            inspect_response=inspect_response,
            stop_conditions=cond,
            max_retries_by_soft_fail=1,
            concurrency=1,
        )
        result: SparpResult = await sparp._main()

        assert len(result.max_retries_soft_fail_reached) == 1
        assert result.stats.success == 0

    async def test_stop_on_timeout(self: Self, unresponsive_server: Any) -> None:
        """Verify the loop exits when a timeout occurs."""
        cond: StopConditions = StopConditions(stop_on_timeout=True)
        sparp: SPARP = SPARP(
            req_gen(5, 8769), inspect_response=inspect_response, stop_conditions=cond, timeout_s=0.1, concurrency=1
        )
        result: SparpResult = await sparp._main()

        assert result.stats.timeout_retries == 1
        assert result.stats.success == 0

    async def test_no_stop_conditions_continues_on_failure(self: Self, rate_limited_server: Any) -> None:
        """Sanity check: verify that with no stop conditions, the loop finishes all items."""
        cond: StopConditions = StopConditions(stop_on_soft_fail=False)
        # Server fails twice then succeeds. With enough retries, all 5 should succeed.
        sparp: SPARP = SPARP(
            req_gen(5, 8766),
            inspect_response=inspect_response,
            stop_conditions=cond,
            max_retries_by_soft_fail=5,
            concurrency=2,
        )
        result: SparpResult = await sparp._main()

        assert result.stats.success == 5
        assert result.stats.soft_retries == 10  # 5 requests * 2 soft fails each

    async def test_timeout_retry_exhaustion(self: Self, flaky_timeout_server: Any) -> None:
        """Verify results are captured when timeout retries are exhausted without a stop signal."""
        sparp: SPARP = SPARP(
            req_gen(1, 8771), inspect_response=inspect_response, timeout_s=0.1, max_retries_by_timeout=1, concurrency=1
        )
        result: SparpResult = await sparp._main()

        assert result.stats.timeout_retries == 1
        assert len(result.max_retries_timeout_reached) == 1

    async def test_stop_on_max_retries_timeout_reached(self: Self, flaky_timeout_server: Any) -> None:
        """Verify loop exits only after max timeout retries are hit for one request."""
        cond: StopConditions = StopConditions(stop_on_max_retries_by_timeout_reached=True)
        sparp: SPARP = SPARP(
            req_gen(5, 8771),
            inspect_response=inspect_response,
            stop_conditions=cond,
            max_retries_by_timeout=1,  # Fails on 2nd timeout
            timeout_s=0.1,
            concurrency=1,
        )
        result: SparpResult = await sparp._main()

        # Should have 1 retry (the first fail) and then stop
        assert result.stats.timeout_retries == 1
        assert len(result.max_retries_timeout_reached) == 1
        assert result.stats.success == 0
