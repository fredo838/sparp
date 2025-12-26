import time
import pytest
import aiohttp
from typing import Any, Dict, List, Self, Generator
from src.sparp.sparp import SPARP, ResponseState
from tests.unit.helpers import req_gen, inspect_response


@pytest.mark.asyncio
class TestSPARPExceptions:
    async def test_broken_inspector_bubbles_up(self: Self, success_server: Dict[str, List[Any]]) -> None:
        """Test exception in the synchronous inspect_response function."""

        def broken_inspector(response: aiohttp.ClientResponse) -> ResponseState:
            raise ValueError("Crash in Inspector")

        sparp: SPARP = SPARP(req_gen(2, 8765), inspect_response=broken_inspector)

        with pytest.raises(ExceptionGroup) as eg_info:
            await sparp._main()
        assert eg_info.group_contains(ValueError, match="Crash in Inspector")

    async def test_broken_generator_bubbles_up(self: Self) -> None:
        """Test exception inside the input generator (Producer task)."""

        def broken_gen() -> Generator[Dict[str, Any], None, None]:
            yield {"method": "POST", "url": "http://localhost:8765/test", "json": {"value": 0}}
            raise RuntimeError("Generator Failed")

        sparp: SPARP = SPARP(input_collection=broken_gen(), inspect_response=inspect_response)

        with pytest.raises(ExceptionGroup) as eg_info:
            await sparp._main()
        assert eg_info.group_contains(RuntimeError, match="Generator Failed")

    async def test_broken_parser_bubbles_up(self: Self, success_server: Dict[str, List[Any]]) -> None:
        """Test exception in the asynchronous parse_response function."""

        async def broken_parser(request_dict: Dict[str, Any], response: aiohttp.ClientResponse) -> Any:
            raise TypeError("Parser Crash")

        sparp: SPARP = SPARP(req_gen(1, 8765), inspect_response=inspect_response, parse_response=broken_parser)

        with pytest.raises(ExceptionGroup) as eg_info:
            await sparp._main()
        assert eg_info.group_contains(TypeError, match="Parser Crash")

    async def test_network_connection_error_bubbles_up(self: Self) -> None:
        """Test standard aiohttp exceptions (e.g. connecting to a port with no server)."""
        # Port 9999 is (hopefully) not in use
        sparp: SPARP = SPARP(req_gen(1, 9999), inspect_response=inspect_response)

        with pytest.raises(ExceptionGroup) as eg_info:
            await sparp._main()
        assert eg_info.group_contains(aiohttp.ClientConnectorError)

    async def test_multiple_workers_crashing_bubbles_group(self: Self) -> None:
        def ultra_broken_inspector(response: aiohttp.ClientResponse) -> ResponseState:
            # Blocking sleep ensures multiple workers "pile up" here
            # before the TaskGroup can cancel them.
            time.sleep(0.1)
            raise ValueError("Massive Failure")

        reqs = [{"method": "GET", "url": "http://localhost:8765"} for _ in range(10)]
        sparp = SPARP(reqs, inspect_response=ultra_broken_inspector, concurrency=5)

        with pytest.raises(ExceptionGroup) as eg_info:
            await sparp._main()

        # Now len(exceptions) is much more likely to be > 1
        assert len(eg_info.value.exceptions) > 1
