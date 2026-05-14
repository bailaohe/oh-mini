"""Tests for InteractiveAskPermissionResolver."""
from __future__ import annotations

from meta_harney.abstractions.tool import ToolInvocation

from oh_mini.permission import (
    DANGEROUS_TOOLS,
    InteractiveAskPermissionResolver,
)


def _make_inv(name: str, args: dict[str, object] | None = None) -> ToolInvocation:
    return ToolInvocation(
        name=name,
        args=args or {},
        invocation_id="t1",
        session_id="s1",
    )


async def test_yolo_always_allows() -> None:
    r = InteractiveAskPermissionResolver(yolo=True, ask=lambda _p: "N")
    decision = await r.resolve(_make_inv("bash", {"command": "rm -rf /"}), "s1")
    assert decision.verdict == "allow"


async def test_non_dangerous_silently_allowed() -> None:
    r = InteractiveAskPermissionResolver(yolo=False, ask=lambda _p: "N")
    decision = await r.resolve(_make_inv("file_read", {"path": "foo.py"}), "s1")
    assert decision.verdict == "allow"


async def test_dangerous_y_allows() -> None:
    r = InteractiveAskPermissionResolver(yolo=False, ask=lambda _p: "y")
    decision = await r.resolve(_make_inv("bash", {"command": "ls"}), "s1")
    assert decision.verdict == "allow"


async def test_dangerous_n_denies() -> None:
    r = InteractiveAskPermissionResolver(yolo=False, ask=lambda _p: "N")
    decision = await r.resolve(_make_inv("bash", {"command": "ls"}), "s1")
    assert decision.verdict == "deny"
    assert "user" in (decision.reason or "").lower() or "denied" in (decision.reason or "").lower()


async def test_dangerous_a_promotes_yolo() -> None:
    r = InteractiveAskPermissionResolver(yolo=False, ask=lambda _p: "a")
    decision = await r.resolve(_make_inv("bash", {"command": "ls"}), "s1")
    assert decision.verdict == "allow"
    # Second call: ask should NOT be called (yolo is now True)
    r._ask = lambda _p: (_ for _ in ()).throw(AssertionError("should not ask"))
    decision2 = await r.resolve(_make_inv("file_write", {"path": "x", "content": "y"}), "s1")
    assert decision2.verdict == "allow"


async def test_dangerous_eof_denies() -> None:
    def _ask(_p: str) -> str:
        raise EOFError
    r = InteractiveAskPermissionResolver(yolo=False, ask=_ask)
    decision = await r.resolve(_make_inv("bash", {"command": "ls"}), "s1")
    assert decision.verdict == "deny"


def test_dangerous_tools_set_includes_expected_names() -> None:
    assert "bash" in DANGEROUS_TOOLS
    assert "file_write" in DANGEROUS_TOOLS
    assert "file_edit" in DANGEROUS_TOOLS
    assert "notebook_edit" in DANGEROUS_TOOLS
    assert "file_read" not in DANGEROUS_TOOLS
    assert "grep" not in DANGEROUS_TOOLS
