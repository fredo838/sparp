import pytest
import aiohttp
from typing import Any, Dict, Self, Awaitable
from src.sparp.sparp import SPARP, SparpResult
from tests.unit.helpers import req_gen, inspect_response


@pytest.mark.asyncio
class TestSPARPParsing:
    async def test_custom_parser_success_shaping(self: Self, success_server: Any) -> None:
        """Verify the success list contains only what the custom parser returns."""

        async def only_status_parser(request_dict: Dict[str, Any], response: aiohttp.ClientResponse) -> Dict[str, Any]:
            # We ignore the body and just return the HTTP status and the original value
            return {"http_status": response.status, "sent_value": request_dict["json"]["value"]}

        sparp: SPARP = SPARP(
            input_collection=req_gen(2, 8765),
            inspect_response=inspect_response,
            parse_response=only_status_parser,
            concurrency=1,
        )
        result: SparpResult = await sparp._main()

        assert len(result.success) == 2
        # Sorting by sent_value to ensure deterministic access
        items: list[Dict[str, Any]] = sorted(result.success, key=lambda x: x["sent_value"])
        item: Dict[str, Any] = items[0]

        # Verify custom keys exist and default keys (like 'body' or 'text') do not
        assert "http_status" in item
        assert item["sent_value"] == 0
        assert "body" not in item
        assert "text" not in item

    async def test_parser_access_to_headers(self: Self, success_server: Any) -> None:
        """Verify the parser can access aiohttp response headers."""

        async def header_parser(request_dict: Dict[str, Any], response: aiohttp.ClientResponse) -> Dict[str, Any]:
            return {"server_header": response.headers.get("Server", "")}

        sparp: SPARP = SPARP(
            input_collection=req_gen(1, 8765), inspect_response=inspect_response, parse_response=header_parser
        )
        result: SparpResult = await sparp._main()

        item: Dict[str, Any] = result.success[0]
        # aiohttp's web.Application usually identifies as "Python/3.x aiohttp/3.x"
        assert "aiohttp" in item["server_header"].lower()

    async def test_parser_exception_bubbles(self: Self, success_server: Any) -> None:
        """Verify that a crash inside the parse_response function bubbles up."""

        async def crashing_parser(request_dict: Dict[str, Any], response: aiohttp.ClientResponse) -> Dict[str, Any]:
            raise ValueError("Parser Error")

        sparp: SPARP = SPARP(
            input_collection=req_gen(1, 8765), inspect_response=inspect_response, parse_response=crashing_parser
        )

        with pytest.raises(ExceptionGroup) as eg:
            await sparp._main()

        assert eg.group_contains(ValueError, match="Parser Error")

    async def test_parser_handles_multiple_content_types(self: Self, success_server: Any) -> None:
        """Verify parser can perform complex async operations like reading text twice if needed."""

        async def double_read_parser(request_dict: Dict[str, Any], response: aiohttp.ClientResponse) -> Dict[str, Any]:
            body_json: Any = await response.json()
            body_text: str = await response.text()
            return {"j": body_json, "t": body_text}

        sparp: SPARP = SPARP(
            input_collection=req_gen(1, 8765), inspect_response=inspect_response, parse_response=double_read_parser
        )
        result: SparpResult = await sparp._main()

        item: Dict[str, Any] = result.success[0]

        # Check the JSON object
        assert item["j"]["status"] == "ok"
        assert item["j"]["echo"] == 0

        # Check the raw text string contains the key and value
        assert '"status": "ok"' in item["t"]
        assert '"echo": 0' in item["t"]
