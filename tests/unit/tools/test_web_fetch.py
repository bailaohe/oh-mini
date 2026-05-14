"""Tests for WebFetchTool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from meta_harney.abstractions.tool import ToolContext, ToolInvocation
from meta_harney.builtin.session.memory_store import MemorySessionStore
from meta_harney.builtin.trace.null_sink import NullSink

from oh_mini.tools.web_fetch import WebFetchTool


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_store=MemorySessionStore(),
        trace_sink=NullSink(),
        current_span_id="span-1",
        new_span_id=lambda: "span-x",
        multi_agent=None,
    )


def _make_inv(args: dict[str, object]) -> ToolInvocation:
    return ToolInvocation(name="web_fetch", args=args, invocation_id="t1", session_id="s1")


def _fake_response(text: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.text = text
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


async def test_web_fetch_https_success():
    fake_get = AsyncMock(return_value=_fake_response("hello world"))
    fake_client = MagicMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)
    fake_client.get = fake_get
    with patch("oh_mini.tools.web_fetch.httpx.AsyncClient", return_value=fake_client):
        inv = _make_inv({"url": "https://example.com/"})
        result = await WebFetchTool().execute(inv, _make_ctx())
    assert result.success
    assert "hello world" in str(result.output)


async def test_web_fetch_non_https_rejected():
    inv = _make_inv({"url": "ftp://example.com/file"})
    result = await WebFetchTool().execute(inv, _make_ctx())
    assert not result.success
    assert "http" in (result.error or "").lower()


async def test_web_fetch_truncates_at_1mb():
    big = "x" * (2 * 1024 * 1024)
    fake_get = AsyncMock(return_value=_fake_response(big))
    fake_client = MagicMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)
    fake_client.get = fake_get
    with patch("oh_mini.tools.web_fetch.httpx.AsyncClient", return_value=fake_client):
        inv = _make_inv({"url": "https://example.com/"})
        result = await WebFetchTool().execute(inv, _make_ctx())
    assert result.success
    body = str(result.output)
    assert len(body) <= (1 * 1024 * 1024 + 100)
    assert "truncated" in body.lower()


async def test_web_fetch_http_error_returned_as_failure():
    fake_get = AsyncMock(side_effect=httpx.TimeoutException("slow"))
    fake_client = MagicMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)
    fake_client.get = fake_get
    with patch("oh_mini.tools.web_fetch.httpx.AsyncClient", return_value=fake_client):
        inv = _make_inv({"url": "https://example.com/"})
        result = await WebFetchTool().execute(inv, _make_ctx())
    assert not result.success
    err = (result.error or "").lower()
    assert "timeout" in err or "slow" in err
