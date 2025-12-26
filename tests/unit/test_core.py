import json
import pytest
from typing import Any, Dict, List, Self
from src.sparp.sparp import SPARP, SparpResult
from tests.unit.helpers import req_gen, inspect_response


@pytest.mark.asyncio
class TestSPARPCore:
    async def test_successful_run_and_body_parsing(self: Self, success_server: Dict[str, List[Any]]) -> None:
        """Verify that successful requests are parsed and stored correctly in SparpResult."""
        sparp: SPARP = SPARP(input_collection=req_gen(5, 8765), inspect_response=inspect_response, concurrency=2)
        # We capture the result object because the internal queues are drained at the end
        result: SparpResult = await sparp._main()

        assert len(result.success) == 5
        assert result.stats.success == 5

        # Verify the content of the first parsed response
        first_item: Dict[str, Any] = result.success[0]
        assert json.loads(first_item["text"])["status"] == "ok"
        assert len(success_server["processed"]) == 5

    async def test_retry_queues_on_exhaustion(self: Self, rate_limited_server: Any) -> None:
        """Verify that requests hitting max soft-fail retries end up in the correct result list."""
        sparp: SPARP = SPARP(
            input_collection=req_gen(1, 8766),
            inspect_response=inspect_response,
            max_retries_by_soft_fail=1,
            concurrency=1,
        )
        result: SparpResult = await sparp._main()

        # Queues are drained into SparpResult collections
        assert len(result.max_retries_soft_fail_reached) == 1
        assert result.stats.success == 0

    async def test_hard_fail_queue(self: Self, failing_server: Any) -> None:
        """Verify that hard-failing requests are collected in the failed list."""
        sparp: SPARP = SPARP(input_collection=req_gen(2, 8767), inspect_response=inspect_response)
        result: SparpResult = await sparp._main()

        assert len(result.failed) == 2
        assert result.stats.failed == 2
