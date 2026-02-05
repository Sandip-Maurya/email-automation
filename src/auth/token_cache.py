"""MSAL token cache for persistent delegated auth. Tokens are stored on disk and auto-refreshed."""

import time
from pathlib import Path
from typing import Any

from azure.core.credentials import AccessToken, TokenCredential
import msal

# Token cache location (plan: ~/.email-automation/token_cache.json)
TOKEN_CACHE_DIR = Path.home() / ".email-automation"
TOKEN_CACHE_PATH = TOKEN_CACHE_DIR / "token_cache.json"

# Microsoft Graph delegated scopes
DELEGATED_SCOPES = [
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/Mail.Send",
]


def _ensure_cache_dir() -> None:
    TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_cache() -> msal.SerializableTokenCache:
    """Create a SerializableTokenCache and load from disk if file exists."""
    cache = msal.SerializableTokenCache()
    if TOKEN_CACHE_PATH.exists():
        try:
            cache.deserialize(TOKEN_CACHE_PATH.read_text())
        except Exception:
            pass
    return cache


def _save_cache(cache: msal.SerializableTokenCache) -> None:
    """Persist token cache to disk."""
    _ensure_cache_dir()
    if cache.has_state_changed:
        TOKEN_CACHE_PATH.write_text(cache.serialize())


class MSALDelegatedCredential(TokenCredential):
    """
    TokenCredential that uses MSAL with a persistent file-based token cache.
    Uses device code flow on first run; subsequent runs use cached tokens and refresh silently.
    """

    def __init__(self, tenant_id: str, client_id: str):
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._cache = _load_cache()
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        self._app = msal.PublicClientApplication(
            client_id=client_id,
            authority=authority,
            token_cache=self._cache,
        )

    def get_token(self, *scopes: str, **kwargs: Any) -> AccessToken:
        scopes_list = list(scopes) if scopes else DELEGATED_SCOPES
        account = None
        accounts = self._app.get_accounts()
        if accounts:
            account = accounts[0]

        # Try silent acquisition first (uses cache / refresh token)
        result = self._app.acquire_token_silent(scopes_list, account=account)
        if result:
            _save_cache(self._cache)
            expires_on = int(time.time()) + int(result.get("expires_in", 0))
            return AccessToken(token=result["access_token"], expires_on=expires_on)

        # Fall back to device code flow (first run or cache expired and refresh failed)
        flow = self._app.initiate_device_flow(scopes=scopes_list)
        if not flow:
            raise RuntimeError("Failed to create device flow")
        print(flow["message"])
        result = self._app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise RuntimeError(
                result.get("error_description", result.get("error", "Device flow failed"))
            )
        _save_cache(self._cache)
        expires_on = int(time.time()) + int(result.get("expires_in", 0))
        return AccessToken(token=result["access_token"], expires_on=expires_on)


def get_persistent_device_code_credential(tenant_id: str, client_id: str) -> TokenCredential:
    """
    Return a TokenCredential that uses MSAL with persistent token cache at
    ~/.email-automation/token_cache.json. Use this with GraphServiceClient for
    delegated access that survives restarts without re-authentication.
    """
    return MSALDelegatedCredential(tenant_id=tenant_id, client_id=client_id)
