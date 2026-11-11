import asyncio

import httpx

from rackmind_sim.__main__ import simulation_active


def _status(handler: httpx.MockTransport) -> bool:
    """Run `simulation_active` against a fake API instead of a real one."""

    async def check() -> bool:
        async with httpx.AsyncClient(transport=handler, base_url="http://api") as client:
            return await simulation_active(client)

    return asyncio.run(check())


def test_active_when_the_api_says_so() -> None:
    api = httpx.MockTransport(lambda request: httpx.Response(200, json={"active": True}))

    assert _status(api) is True


def test_paused_when_nobody_is_in_simulation_mode() -> None:
    api = httpx.MockTransport(lambda request: httpx.Response(200, json={"active": False}))

    assert _status(api) is False


def test_paused_when_the_api_fails() -> None:
    api = httpx.MockTransport(lambda request: httpx.Response(503))

    assert _status(api) is False
