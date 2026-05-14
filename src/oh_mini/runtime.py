"""Factory to assemble an oh-mini AgentRuntime (Phase 9b: catalog-driven)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from meta_harney import (
    BUILT_IN_PROVIDERS,
    AgentRuntime,
    BaseHook,
    RuntimeConfig,
    provider_from_spec,
)
from meta_harney.builtin.multi_agent.in_process import InProcessMultiAgentBackend
from meta_harney.builtin.session.file_store import FileSessionStore
from meta_harney.builtin.trace.null_sink import NullSink

from oh_mini.permission import InteractiveAskPermissionResolver
from oh_mini.prompts import CodingPromptBuilder
from oh_mini.tools import build_all_tools


def build_runtime(
    *,
    provider: str = "anthropic",
    api_key: str = "",
    model: str | None = None,
    yolo: bool = False,
    sessions_root: Path | None = None,
    permission_resolver: Any | None = None,
    trace_sink: Any | None = None,
) -> AgentRuntime:
    """Assemble a meta-harney AgentRuntime configured for coding scenarios.

    Args:
        provider: Provider name from meta_harney.BUILT_IN_PROVIDERS.
        api_key: Resolved API key. Caller is responsible for resolution.
            Ignored when OH_MINI_TEST_FAKE_PROVIDER=1.
        model: Model id override. None = use spec.default_model.
        yolo: Skip all permission prompts. Ignored when ``permission_resolver``
            is provided (the explicit resolver wins).
        sessions_root: Override session storage root.
        permission_resolver: Optional override for the permission resolver.
            When provided, replaces the default
            ``InteractiveAskPermissionResolver(yolo=yolo)``. Typed as ``Any`` to
            avoid pulling bridge-related imports into runtime.py.
        trace_sink: Optional override for the trace sink. When provided,
            replaces the default ``NullSink()``. Typed as ``Any`` for the same
            reason.

    Raises SystemExit(2) when provider is not in the catalog.
    """
    if os.environ.get("OH_MINI_TEST_FAKE_PROVIDER") == "1":
        from meta_harney.testing import FakeLLMProvider, FakeRound

        prov = FakeLLMProvider(
            rounds=[FakeRound(text="hello from fake", stop_reason="end_turn") for _ in range(20)]
        )
        chosen_model = model or "fake-model"
    else:
        if provider not in BUILT_IN_PROVIDERS:
            print(
                f"error: unknown provider {provider!r}. Try: oh providers list",
                file=sys.stderr,
            )
            sys.exit(2)
        spec = BUILT_IN_PROVIDERS[provider]
        prov = provider_from_spec(spec, api_key=api_key)
        chosen_model = model or spec.default_model

    root = sessions_root or (Path.home() / ".oh-mini" / "sessions")
    root.mkdir(parents=True, exist_ok=True)
    session_store = FileSessionStore(root)

    permission = permission_resolver or InteractiveAskPermissionResolver(yolo=yolo)
    sink = trace_sink or NullSink()
    prompt_builder = CodingPromptBuilder(session_store=session_store)
    tools = build_all_tools()
    config = RuntimeConfig(model=chosen_model, max_iterations=20)
    hooks: list[BaseHook] = []

    multi_agent = InProcessMultiAgentBackend(
        provider=prov,
        permission_resolver=permission,
        session_store=session_store,
        trace_sink=sink,
        config=config,
        all_tools=tools,
        hooks=hooks,
    )

    return AgentRuntime(
        provider=prov,
        prompt_builder=prompt_builder,
        permission_resolver=permission,
        session_store=session_store,
        trace_sink=sink,
        config=config,
        tools=tools,
        hooks=hooks,
        multi_agent=multi_agent,
    )
