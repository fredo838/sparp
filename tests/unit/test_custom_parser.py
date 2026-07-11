import pytest
import aiohttp
from typing import Any, Dict, Self, Awaitable
from src.sparp import SPARP, SparpResult
from tests.unit.helpers import req_gen, inspect_response


@pytest.mark.asyncio
class TestSPARPParsing:
    async def test_custom_parser_success_shaping(self: Self, success_server: Dict[str, Any]) -> None:
        """Verify the success list contains only what the custom parser returns."""

        async def only_status_parser(request_dict: Dict[str, Any], response: aiohttp.ClientResponse) -> Dict[str, Any]:
            return {"http_status": response.status, "sent_value": request_dict["json"]["value"]}

        sparp: SPARP = SPARP(
            inspect_response=inspect_response,
            parse_response_fn=only_status_parser,
            concurrency=1,
        )
        result: SparpResult = await sparp._main(req_gen(2, success_server["port"]))

        assert len(result.success) == 2
        items: list[Dict[str, Any]] = sorted(result.success, key=lambda x: x["sent_value"])
        item: Dict[str, Any] = items[0]

        assert "http_status" in item
        assert item["sent_value"] == 0
        assert "body" not in item
        assert "text" not in item

    async def test_parser_access_to_headers(self: Self, success_server: Dict[str, Any]) -> None:
        """Verify the parser can access aiohttp response headers."""

        async def header_parser(request_dict: Dict[str, Any], response: aiohttp.ClientResponse) -> Dict[str, Any]:
            return {"server_header": response.headers.get("Server", "")}

        sparp: SPARP = SPARP(inspect_response=inspect_response, parse_response_fn=header_parser)
        result: SparpResult = await sparp._main(req_gen(1, success_server["port"]))

        item: Dict[str, Any] = result.success[0]
        assert "aiohttp" in item["server_header"].lower()

    async def test_parser_exception_bubbles(self: Self, success_server: Dict[str, Any]) -> None:
        """Verify that a crash inside the parse_response_fn function bubbles up."""

        async def crashing_parser(request_dict: Dict[str, Any], response: aiohttp.ClientResponse) -> Dict[str, Any]:
            raise ValueError("Parser Error")

        sparp: SPARP = SPARP(inspect_response=inspect_response, parse_response_fn=crashing_parser)

        with pytest.raises(ExceptionGroup) as eg:
            await sparp._main(req_gen(1, success_server["port"]))

        assert eg.group_contains(ValueError, match="Parser Error")

    async def test_parser_handles_multiple_content_types(self: Self, success_server: Dict[str, Any]) -> None:
        """Verify parser can perform complex async operations like reading text twice if needed."""

        async def double_read_parser(request_dict: Dict[str, Any], response: aiohttp.ClientResponse) -> Dict[str, Any]:
            body_json: Any = await response.json()
            body_text: str = await response.text()
            return {"j": body_json, "t": body_text}

        sparp: SPARP = SPARP(inspect_response=inspect_response, parse_response_fn=double_read_parser)
        result: SparpResult = await sparp._main(req_gen(1, success_server["port"]))

        item: Dict[str, Any] = result.success[0]

        assert item["j"]["status"] == "ok"
        assert item["j"]["echo"] == 0
        assert '"status": "ok"' in item["t"]
        assert '"echo": 0' in item["t"]
