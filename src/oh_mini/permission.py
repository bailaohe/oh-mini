"""InteractiveAskPermissionResolver — interactive y/N/a prompting for dangerous tools."""
from __future__ import annotations

from collections.abc import Callable

from meta_harney.abstractions.permission import PermissionDecision
from meta_harney.abstractions.tool import ToolInvocation

DANGEROUS_TOOLS: frozenset[str] = frozenset(
    {"bash", "file_write", "file_edit", "notebook_edit"}
)


def _default_ask(prompt: str) -> str:
    return input(prompt)


class InteractiveAskPermissionResolver:
    """Implements meta-harney's PermissionResolver Protocol.

    Behavior:
    - yolo=True: always allow.
    - tool not in DANGEROUS_TOOLS: always allow.
    - Otherwise: call ask() with a prompt; answer 'y' or 'yes' → allow;
      'a' → allow + promote to yolo for the rest of this resolver's life;
      anything else (incl. EOFError, KeyboardInterrupt) → deny.
    """

    def __init__(
        self,
        *,
        yolo: bool,
        dangerous_tools: frozenset[str] = DANGEROUS_TOOLS,
        ask: Callable[[str], str] = _default_ask,
    ) -> None:
        self._yolo = yolo
        self._dangerous = dangerous_tools
        self._ask = ask

    async def resolve(
        self,
        inv: ToolInvocation,
        session_id: str,
    ) -> PermissionDecision:
        if self._yolo:
            return PermissionDecision(verdict="allow")
        if inv.name not in self._dangerous:
            return PermissionDecision(verdict="allow")
        prompt = (
            f"\n[!] Tool [{inv.name}] wants to run:\n"
            f"   {_format_args(inv.args)}\n"
            "Allow? [y/N/a=always]: "
        )
        try:
            answer = self._ask(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return PermissionDecision(verdict="deny", reason="user interrupted")
        if answer == "a":
            self._yolo = True
            return PermissionDecision(verdict="allow")
        if answer in {"y", "yes"}:
            return PermissionDecision(verdict="allow")
        return PermissionDecision(verdict="deny", reason="user denied")


def _format_args(args: dict[str, object]) -> str:
    parts: list[str] = []
    for k, v in args.items():
        s = repr(v)
        if len(s) > 80:
            s = s[:77] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)
