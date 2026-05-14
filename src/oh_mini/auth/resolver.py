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
    3. backend.get(CredentialKey(provider, profile))  -> on hit, backend.touch()
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
        key = CredentialKey(provider, profile)
        stored = self._backend.get(key)
        if stored:
            self._backend.touch(key)
            return stored
        raise NoCredentialError(provider, profile)


def pick_default_provider(backend: CredentialBackend) -> str | None:
    """Smart fallback when settings.default_provider is unset.

    - 0 credentials: None
    - 1 credential: that provider
    - N credentials: provider with largest last_used (ties broken by name)
    """
    keys = backend.list()
    if not keys:
        return None
    if len(keys) == 1:
        return keys[0].provider
    keys_sorted = sorted(
        keys,
        key=lambda k: (backend.get_last_used(k), k.provider),
        reverse=True,
    )
    return keys_sorted[0].provider
