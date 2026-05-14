"""Factory to assemble an oh-mini AgentRuntime."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

from meta_harney import (
    AgentRuntime,
    AnthropicProvider,
    BaseHook,
    OpenAIProvider,
    RuntimeConfig,
)
from meta_harney.builtin.multi_agent.in_process import InProcessMultiAgentBackend
from meta_harney.builtin.session.file_store import FileSessionStore
from meta_harney.builtin.trace.null_sink import NullSink

from oh_mini.permission import InteractiveAskPermissionResolver
from oh_mini.prompts import CodingPromptBuilder
from oh_mini.tools import build_all_tools

_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-4-5",
    "openai": "gpt-4o",
}


def build_runtime(
    *,
    provider: Literal["anthropic", "openai"] = "anthropic",
    model: str | None = None,
    yolo: bool = False,
    sessions_root: Path | None = None,
) -> AgentRuntime:
    """Assemble a meta-harney AgentRuntime configured for coding scenarios.

    If OH_MINI_TEST_FAKE_PROVIDER=1, swap in a FakeLLMProvider that returns
    canned 'hello from fake' rounds. Used only by integration tests.
    """
    if os.environ.get("OH_MINI_TEST_FAKE_PROVIDER") == "1":
        from meta_harney import FakeLLMProvider, FakeRound

        prov = FakeLLMProvider(
            rounds=[FakeRound(text="hello from fake", stop_reason="end_turn") for _ in range(20)]
        )
    elif provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            sys.exit("error: ANTHROPIC_API_KEY env var not set")
        prov = AnthropicProvider(api_key=api_key)
    else:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            sys.exit("error: OPENAI_API_KEY env var not set")
        prov = OpenAIProvider(api_key=api_key)

    chosen_model = model or _DEFAULT_MODELS[provider]

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
