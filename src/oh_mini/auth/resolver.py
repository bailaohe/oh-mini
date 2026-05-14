"""CredentialResolver — resolve an API key by priority."""
from __future__ import annotations

import os

from oh_mini.auth.storage import CredentialBackend, CredentialKey


class NoCredentialError(Exception):
    """Raised when no credential is found across CLI / env / storage."""

    def __init__(self, provider: str, profile: str) -> None:
        super().__init__(f"no credential for {provider}/{profile}")
        self.provider = provider
        self.profile = profile


class CredentialResolver:
    """Resolves an API key by priority:

    1. cli_api_key (if non-empty)
    2. env var <PROVIDER>_API_KEY (if non-empty)
    3. backend.get(CredentialKey(provider, profile))
    4. raise NoCredentialError
    """

    def __init__(self, backend: CredentialBackend) -> None:
        self._backend = backend

    def resolve(
        self,
        provider: str,
        profile: str = "default",
        *,
        cli_api_key: str | None = None,
    ) -> str:
        if cli_api_key:
            return cli_api_key
        env_value = os.environ.get(f"{provider.upper()}_API_KEY", "")
        if env_value:
            return env_value
        stored = self._backend.get(CredentialKey(provider, profile))
        if stored:
            return stored
        raise NoCredentialError(provider, profile)
