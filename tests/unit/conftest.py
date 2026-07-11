import asyncio
import pytest
from aiohttp import web
from typing import Any, Dict, List, cast
from collections.abc import AsyncGenerator


async def _start_site(runner: web.AppRunner) -> int:
    """Starts a site on a free OS-assigned port and returns the bound port."""
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 0)
    await site.start()
    assert site._server is not None, "Server failed to start"
    server = cast(asyncio.Server, site._server)
    return server.sockets[0].getsockname()[1]


@pytest.fixture
async def tuned_fast_server() -> AsyncGenerator[int, None]:
    """Server that takes ~0.01s per request. Yields the bound port."""

    async def handle(request: web.Request) -> web.StreamResponse:
        await asyncio.sleep(0.01)
        return web.json_response({"status": "ok"})

    app = web.Application()
    app.router.add_post("/test", handle)
    runner = web.AppRunner(app)
    port = await _start_site(runner)
    yield port
    await runner.cleanup()


@pytest.fixture
async def success_server() -> AsyncGenerator[Dict[str, Any], None]:
    """JSON echo server. Yields {"processed": [...], "port": int}."""
    processed: List[Any] = []

    async def handle(request: web.Request) -> web.StreamResponse:
        data = await request.json()
        processed.append(data.get("value"))
        return web.json_response({"status": "ok", "echo": data.get("value")})

    app = web.Application()
    app.router.add_post("/test", handle)
    runner = web.AppRunner(app)
    port = await _start_site(runner)
    yield {"processed": processed, "port": port}
    await runner.cleanup()


@pytest.fixture
async def rate_limited_server() -> AsyncGenerator[int, None]:
    """Returns 429 for the first two attempts per value, then 200. Yields port."""
    attempts: Dict[Any, int] = {}

    async def handle(request: web.Request) -> web.StreamResponse:
        data = await request.json()
        val = data.get("value")
        attempts[val] = attempts.get(val, 0) + 1
        if attempts[val] <= 2:
            return web.json_response({"error": "limit"}, status=429)
        return web.json_response({"status": "ok"})

    app = web.Application()
    app.router.add_post("/test", handle)
    runner = web.AppRunner(app)
    port = await _start_site(runner)
    yield port
    await runner.cleanup()


@pytest.fixture
async def failing_server() -> AsyncGenerator[int, None]:
    """Always returns 500. Yields port."""

    async def handle(request: web.Request) -> web.StreamResponse:
        return web.json_response({"error": "internal error"}, status=500)

    app = web.Application()
    app.router.add_post("/test", handle)
    runner = web.AppRunner(app)
    port = await _start_site(runner)
    yield port
    await runner.cleanup()


@pytest.fixture
async def unresponsive_server() -> AsyncGenerator[int, None]:
    """Never responds (sleeps indefinitely). Yields port."""

    async def handle(request: web.Request) -> web.StreamResponse:
        await asyncio.sleep(10000)
        return web.json_response({"status": "never"})

    app = web.Application()
    app.router.add_post("/test", handle)
    runner = web.AppRunner(app, shutdown_timeout=0.1)
    port = await _start_site(runner)
    yield port
    await runner.cleanup()


@pytest.fixture
async def timeout_server() -> AsyncGenerator[int, None]:
    """Always sleeps longer than the client timeout. Yields port."""

    async def handle(request: web.Request) -> web.StreamResponse:
        await asyncio.sleep(10)
        return web.json_response({"status": "never"})

    app = web.Application()
    app.router.add_post("/test", handle)
    runner = web.AppRunner(app, shutdown_timeout=0.1)
    port = await _start_site(runner)
    yield port
    await runner.cleanup()


@pytest.fixture
async def flaky_timeout_server() -> AsyncGenerator[Dict[str, Any], None]:
    """Times out N times per value before succeeding. Yields {"attempts": {...}, "port": int}."""
    attempts: Dict[Any, int] = {}

    async def handle(request: web.Request) -> web.StreamResponse:
        data = await request.json()
        val = data.get("value")
        attempts[val] = attempts.get(val, 0) + 1
        if attempts[val] <= 2:
            await asyncio.sleep(10)
            return web.json_response({"error": "timeout"})
        return web.json_response({"status": "ok"})

    app = web.Application()
    app.router.add_post("/test", handle)
    runner = web.AppRunner(app, shutdown_timeout=0.1)
    port = await _start_site(runner)
    yield {"attempts": attempts, "port": port}
    await runner.cleanup()
