import json
import pytest
from typing import Any, Dict, List, Self
from src.sparp import SPARP, SparpResult
from tests.unit.helpers import req_gen, inspect_response


@pytest.mark.asyncio
class TestSPARPCore:
    async def test_successful_run_and_body_parsing(self: Self, success_server: Dict[str, Any]) -> None:
        """Verify that successful requests are parsed and stored correctly in SparpResult."""
        port: int = success_server["port"]
        sparp: SPARP = SPARP(inspect_response=inspect_response, concurrency=2)
        result: SparpResult = await sparp._main(req_gen(5, port))

        assert len(result.success) == 5
        assert result.stats.success == 5

        first_item: Dict[str, Any] = result.success[0]
        assert json.loads(first_item["text"])["status"] == "ok"
        assert len(success_server["processed"]) == 5

    async def test_retry_queues_on_exhaustion(self: Self, rate_limited_server: int) -> None:
        """Verify that requests hitting max soft-fail retries end up in the correct result list."""
        sparp: SPARP = SPARP(
            inspect_response=inspect_response,
            max_retries_when_soft_fail=1,
            concurrency=1,
        )
        result: SparpResult = await sparp._main(req_gen(1, rate_limited_server))

        assert len(result.max_retries_soft_fail_reached) == 1
        assert result.stats.success == 0

    async def test_hard_fail_queue(self: Self, failing_server: int) -> None:
        """Verify that hard-failing requests are collected in the failed list."""
        sparp: SPARP = SPARP(inspect_response=inspect_response)
        result: SparpResult = await sparp._main(req_gen(2, failing_server))

        assert len(result.failed) == 2
        assert result.stats.failed == 2
