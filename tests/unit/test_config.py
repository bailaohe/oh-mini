"""Tests for config.py (settings.json + custom providers)."""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def _restore_catalog():
    """Clean up custom providers added during a test."""
    from meta_harney import BUILT_IN_PROVIDERS

    original_specs = {name: spec for name, spec in BUILT_IN_PROVIDERS.items()}
    original_names = set(BUILT_IN_PROVIDERS.keys())
    yield
    # Remove any names added during the test
    for name in list(BUILT_IN_PROVIDERS.keys()):
        if name not in original_names:
            del BUILT_IN_PROVIDERS[name]
    # Restore any overwritten specs
    for name, spec in original_specs.items():
        BUILT_IN_PROVIDERS[name] = spec


def test_load_settings_missing_file_returns_defaults(tmp_path):
    from oh_mini.config import load_settings

    s = load_settings(tmp_path / "settings.json")
    assert s.default_provider == "anthropic"
    assert s.default_profile == "default"


def test_load_settings_reads_defaults(tmp_path):
    from oh_mini.config import load_settings

    p = tmp_path / "settings.json"
    p.write_text(
        json.dumps(
            {
                "default_provider": "deepseek",
                "default_profile": "work",
            }
        )
    )
    s = load_settings(p)
    assert s.default_provider == "deepseek"
    assert s.default_profile == "work"


def test_load_settings_registers_custom_providers(tmp_path, _restore_catalog):
    from oh_mini.config import load_settings

    p = tmp_path / "settings.json"
    p.write_text(
        json.dumps(
            {
                "custom_providers": [
                    {
                        "name": "my-llama",
                        "kind": "openai",
                        "base_url": "http://localhost:8080/v1",
                        "default_model": "llama-3.1-8b",
                    }
                ],
            }
        )
    )
    load_settings(p)
    from meta_harney import BUILT_IN_PROVIDERS

    assert "my-llama" in BUILT_IN_PROVIDERS
    assert BUILT_IN_PROVIDERS["my-llama"].base_url == "http://localhost:8080/v1"


def test_load_settings_corrupt_json_returns_defaults(tmp_path, capsys):
    """Soft fail: corrupt settings.json → warn + return defaults."""
    from oh_mini.config import load_settings

    p = tmp_path / "settings.json"
    p.write_text("{ not valid json")
    s = load_settings(p)
    assert s.default_provider == "anthropic"
    captured = capsys.readouterr()
    assert "settings" in captured.err.lower() or "corrupt" in captured.err.lower()


def test_load_settings_bad_custom_provider_entry_skipped(tmp_path, capsys, _restore_catalog):
    """One bad custom_providers entry doesn't break the rest."""
    from oh_mini.config import load_settings

    p = tmp_path / "settings.json"
    p.write_text(
        json.dumps(
            {
                "default_provider": "anthropic",
                "custom_providers": [
                    {"this is malformed": True},
                    {
                        "name": "good-one",
                        "kind": "openai",
                        "base_url": "http://x/v1",
                        "default_model": "x",
                    },
                ],
            }
        )
    )
    load_settings(p)
    from meta_harney import BUILT_IN_PROVIDERS

    assert "good-one" in BUILT_IN_PROVIDERS


def test_load_settings_custom_provider_overwrites_builtin(tmp_path, _restore_catalog):
    """custom_providers entries use overwrite=True (so they can replace built-ins)."""
    from oh_mini.config import load_settings

    p = tmp_path / "settings.json"
    p.write_text(
        json.dumps(
            {
                "custom_providers": [
                    {
                        "name": "openai",
                        "kind": "openai",
                        "base_url": "https://my-private-openai/v1",
                        "default_model": "my-model",
                    }
                ],
            }
        )
    )
    load_settings(p)
    from meta_harney import BUILT_IN_PROVIDERS

    assert BUILT_IN_PROVIDERS["openai"].base_url == "https://my-private-openai/v1"
