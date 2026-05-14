"""Tests for path-traversal guard."""
from __future__ import annotations

import pytest

from oh_mini.tools._safety import PathOutsideCwdError, resolve_path_within_cwd


def test_relative_path_inside_cwd_resolves(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "foo.py").write_text("x")
    result = resolve_path_within_cwd("foo.py")
    assert result == (tmp_path / "foo.py").resolve()


def test_relative_dot_dot_path_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(PathOutsideCwdError):
        resolve_path_within_cwd("../etc/passwd")


def test_absolute_path_inside_cwd_resolves(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "foo.py"
    p.write_text("x")
    result = resolve_path_within_cwd(str(p))
    assert result == p.resolve()


def test_absolute_path_outside_cwd_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(PathOutsideCwdError):
        resolve_path_within_cwd("/etc/passwd")
