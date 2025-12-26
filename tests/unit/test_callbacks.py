import pytest
from typing import Any, Self
from src.sparp.sparp import SPARP, Callbacks, SparpResult
from tests.unit.helpers import req_gen, inspect_response


@pytest.mark.asyncio
class TestSPARPCallbacks:
    async def test_success_and_hard_fail_callbacks(self: Self, success_server: Any, failing_server: Any) -> None:
        """Verify on_success and on_hard_fail trigger with the correct data."""
        results: dict[str, list[int]] = {"success": [], "hard_fail": []}

        def on_s(req: dict[str, Any], resp: Any) -> None:
            results["success"].append(req["json"]["value"])

        def on_h(req: dict[str, Any], resp: Any) -> None:
            results["hard_fail"].append(req["json"]["value"])

        cb: Callbacks = Callbacks(on_success=on_s, on_hard_fail=on_h)

        # 1. Test Success
        sparp_s: SPARP = SPARP(req_gen(2, 8765), inspect_response, callbacks=cb, concurrency=2)
        result_s: SparpResult = await sparp_s._main()

        # 2. Test Hard Fail
        sparp_f: SPARP = SPARP(req_gen(2, 8767), inspect_response, callbacks=cb, concurrency=2)
        result_f: SparpResult = await sparp_f._main()

        # Assertions
        assert sorted(results["success"]) == [0, 1]
        assert sorted(results["hard_fail"]) == [0, 1]
        assert result_s.stats.success == 2
        assert result_f.stats.failed == 2

    async def test_soft_fail_callback_increments(self: Self, rate_limited_server: Any) -> None:
        """Verify on_soft_fail triggers for every retry attempt with the current count."""
        attempts: list[tuple[int, int]] = []

        def on_soft(req: dict[str, Any], retry_count: int) -> None:
            attempts.append((req["json"]["value"], retry_count))

        cb: Callbacks = Callbacks(on_soft_fail=on_soft)

        sparp: SPARP = SPARP(req_gen(1, 8766), inspect_response, callbacks=cb, max_retries_by_soft_fail=5)
        result: SparpResult = await sparp._main()

        assert len(attempts) == 2
        assert attempts == [(0, 0), (0, 1)]
        assert result.stats.soft_retries == 2

    async def test_timeout_callback(self: Self, flaky_timeout_server: Any) -> None:
        """Verify on_timeout triggers when a request hangs."""
        timeout_calls: list[int] = []

        def on_to(req: dict[str, Any], retry_count: int) -> None:
            timeout_calls.append(retry_count)

        cb: Callbacks = Callbacks(on_timeout=on_to)

        sparp: SPARP = SPARP(req_gen(1, 8771), inspect_response, callbacks=cb, timeout_s=0.1, max_retries_by_timeout=5)
        result: SparpResult = await sparp._main()

        assert len(timeout_calls) == 2
        assert timeout_calls == [0, 1]
        assert result.stats.timeout_retries == 2

    async def test_max_retries_reached_callbacks(
        self: Self, rate_limited_server: Any, flaky_timeout_server: Any
    ) -> None:
        """Verify the 'exhaustion' callbacks trigger when retries run out."""
        exhaustion_events: list[str] = []

        cb: Callbacks = Callbacks(
            on_max_retries_by_soft_fail_reached=lambda req: exhaustion_events.append("soft"),
            on_max_retries_by_timeout_reached=lambda req: exhaustion_events.append("timeout"),
        )

        # Soft fail exhaustion
        sparp_s: SPARP = SPARP(req_gen(1, 8766), inspect_response, callbacks=cb, max_retries_by_soft_fail=1)
        result_s: SparpResult = await sparp_s._main()

        # Timeout exhaustion
        sparp_t: SPARP = SPARP(
            req_gen(1, 8771), inspect_response, callbacks=cb, timeout_s=0.1, max_retries_by_timeout=1
        )
        result_t: SparpResult = await sparp_t._main()

        assert "soft" in exhaustion_events
        assert "timeout" in exhaustion_events
        assert len(result_s.max_retries_soft_fail_reached) == 1
        assert len(result_t.max_retries_timeout_reached) == 1

    async def test_callback_error_bubbles_up(self: Self, success_server: Any) -> None:
        """Verify that a crash inside a callback bubbles up through the TaskGroup."""

        def exploding_callback(req: dict[str, Any], resp: Any) -> None:
            raise RuntimeError("Callback Crash")

        cb: Callbacks = Callbacks(on_success=exploding_callback)
        sparp: SPARP = SPARP(req_gen(1, 8765), inspect_response, callbacks=cb)

        with pytest.raises(ExceptionGroup) as eg:
            await sparp._main()

        assert eg.group_contains(RuntimeError, match="Callback Crash")
