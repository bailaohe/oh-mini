"""Unit tests for oh_mini.bridge module."""

from __future__ import annotations

import argparse

import pytest


def _args(**kwargs) -> argparse.Namespace:
    defaults = {
        "provider_flag": None,
        "profile_flag": None,
        "model": None,
        "api_key": None,
        "framing": "newline",
        "sessions_root": None,
        "yolo": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_select_framing_newline() -> None:
    from meta_harney.bridge import NewlineFraming

    from oh_mini.bridge import _select_framing

    framing = _select_framing("newline")
    assert isinstance(framing, NewlineFraming)


def test_select_framing_content_length() -> None:
    from meta_harney.bridge import ContentLengthFraming

    from oh_mini.bridge import _select_framing

    framing = _select_framing("content-length")
    assert isinstance(framing, ContentLengthFraming)


def test_select_framing_unknown_raises() -> None:
    from oh_mini.bridge import _select_framing

    with pytest.raises(SystemExit):
        _select_framing("totally-fake")


def test_select_permission_resolver_yolo() -> None:
    from oh_mini.bridge import _select_permission_resolver

    resolver = _select_permission_resolver(yolo=True, send_request=None)
    assert resolver.__class__.__name__ == "AllowAllPermissionResolver"


def test_select_permission_resolver_bridge() -> None:
    from meta_harney.bridge import BridgePermissionResolver

    from oh_mini.bridge import _select_permission_resolver

    async def send(method, params):
        return {"decision": "allow"}

    resolver = _select_permission_resolver(yolo=False, send_request=send)
    assert isinstance(resolver, BridgePermissionResolver)
