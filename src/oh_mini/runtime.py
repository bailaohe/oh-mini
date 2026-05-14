"""Factory to assemble an oh-mini AgentRuntime (Phase 9b: catalog-driven)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

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
) -> AgentRuntime:
    """Assemble a meta-harney AgentRuntime configured for coding scenarios.

    Args:
        provider: Provider name from meta_harney.BUILT_IN_PROVIDERS.
        api_key: Resolved API key. Caller is responsible for resolution.
            Ignored when OH_MINI_TEST_FAKE_PROVIDER=1.
        model: Model id override. None = use spec.default_model.
        yolo: Skip all permission prompts.
        sessions_root: Override session storage root.

    Raises SystemExit(2) when provider is not in the catalog.
    """
    if os.environ.get("OH_MINI_TEST_FAKE_PROVIDER") == "1":
        from meta_harney.testing import FakeLLMProvider, FakeRound

        prov = FakeLLMProvider(
            rounds=[
                FakeRound(text="hello from fake", stop_reason="end_turn")
                for _ in range(20)
            ]
        )
        chosen_model = model or "fake-model"
    else:
        if provider not in BUILT_IN_PROVIDERS:
            print(
                f"error: unknown provider {provider!r}. "
                f"Try: oh providers list",
                file=sys.stderr,
            )
            sys.exit(2)
        spec = BUILT_IN_PROVIDERS[provider]
        prov = provider_from_spec(spec, api_key=api_key)
        chosen_model = model or spec.default_model

    root = sessions_root or (Path.home() / ".oh-mini" / "sessions")
    root.mkdir(parents=True, exist_ok=True)
    session_store = FileSessionStore(root)

    permission = InteractiveAskPermissionResolver(yolo=yolo)
    prompt_builder = CodingPromptBuilder(session_store=session_store)
    tools = build_all_tools()
    trace_sink = NullSink()
    config = RuntimeConfig(model=chosen_model, max_iterations=20)
    hooks: list[BaseHook] = []

    multi_agent = InProcessMultiAgentBackend(
        provider=prov,
        permission_resolver=permission,
        session_store=session_store,
        trace_sink=trace_sink,
        config=config,
        all_tools=tools,
        hooks=hooks,
    )

    return AgentRuntime(
        provider=prov,
        prompt_builder=prompt_builder,
        permission_resolver=permission,
        session_store=session_store,
        trace_sink=trace_sink,
        config=config,
        tools=tools,
        hooks=hooks,
        multi_agent=multi_agent,
    )
