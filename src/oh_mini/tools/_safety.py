"""Path-traversal guard shared by file_read / file_write / file_edit tools."""
from __future__ import annotations

import os
from pathlib import Path


class PathOutsideCwdError(Exception):
    """Raised when a tool argument resolves to a path outside the current cwd."""


def resolve_path_within_cwd(path: str) -> Path:
    """Resolve `path` relative to cwd and ensure it stays inside.

    Raises PathOutsideCwdError if the resolved absolute path is not
    a child of (or equal to) the current working directory.
    """
    cwd = Path(os.getcwd()).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = cwd / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(cwd)
    except ValueError as exc:
        raise PathOutsideCwdError(f"path outside cwd: {path}") from exc
    return resolved
