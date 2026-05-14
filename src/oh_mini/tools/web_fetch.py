"""WebFetchTool — fetch a URL via httpx (https only)."""
from __future__ import annotations

from urllib.parse import urlparse

import httpx
from meta_harney.abstractions.tool import (
    BaseTool,
    ToolContext,
    ToolInvocation,
    ToolResult,
)
from pydantic import BaseModel

_MAX_BODY_BYTES = 1 * 1024 * 1024
_TRUNCATED_MARKER = "\n[truncated at 1MB]"


class _WebFetchInput(BaseModel):
    url: str
    prompt: str | None = None


class WebFetchTool(BaseTool):  # type: ignore[misc]
    name = "web_fetch"
    description = (
        "Fetch the body of an https URL. Returns raw text, truncated to 1MB. "
        "(Phase 8: does not summarize via LLM.)"
    )
    input_schema = _WebFetchInput
    default_timeout: float | None = 30.0

    async def execute(
        self,
        inv: ToolInvocation,
        ctx: ToolContext,
    ) -> ToolResult:
        url = str(inv.args["url"])
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return ToolResult(
                success=False,
                error=f"only http(s) URLs allowed; got: {parsed.scheme}",
            )
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                body = resp.text
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            return ToolResult(success=False, error=f"fetch failed: {exc}")
        if len(body.encode("utf-8")) > _MAX_BODY_BYTES:
            body = body[:_MAX_BODY_BYTES] + _TRUNCATED_MARKER
        return ToolResult(success=True, output=body)
