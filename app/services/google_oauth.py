"""Google Sign-In and env-only Google Sheets token refresh."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings

logger = logging.getLogger(__name__)

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO = "https://www.googleapis.com/oauth2/v3/userinfo"
SHEETS_VALUES = "https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_}"
LOGIN_SCOPES = "openid email profile"
SHEETS_SCOPES = "https://www.googleapis.com/auth/spreadsheets.readonly"
STATE_MAX_AGE = 600

_sheets_access: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


class GoogleNotConfigured(RuntimeError):
    pass


class GoogleOAuthError(RuntimeError):
    pass


class SheetsReconnectRequired(GoogleOAuthError):
    """Google rejected the stored refresh token: an operator must reconnect Sheets."""


def _signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt="xautopilot-google-oauth")


def dumps_state(payload: dict[str, str]) -> str:
    return _signer().dumps(payload)


def loads_state(token: str) -> dict[str, str]:
    try:
        data = _signer().loads(token, max_age=STATE_MAX_AGE)
    except (BadSignature, SignatureExpired) as exc:
        raise GoogleOAuthError("invalid OAuth state") from exc
    if not isinstance(data, dict):
        raise GoogleOAuthError("invalid OAuth state")
    return {str(k): str(v) for k, v in data.items()}


def authorization_url(*, redirect_uri: str, state: str, scopes: str, offline: bool = False) -> str:
    if not settings.google_oauth_client_id.strip():
        raise GoogleNotConfigured("GOOGLE_OAUTH_CLIENT_ID is not set")
    params = {
        "client_id": settings.google_oauth_client_id.strip(),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scopes,
        "state": state,
        "include_granted_scopes": "false",
    }
    if offline:
        params["access_type"] = "offline"
        params["prompt"] = "consent"
    return f"{GOOGLE_AUTH}?{urlencode(params)}"


async def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    if not settings.google_oauth_client_id.strip() or not settings.google_oauth_client_secret.strip():
        raise GoogleNotConfigured("Google OAuth client is not set")
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            GOOGLE_TOKEN,
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id.strip(),
                "client_secret": settings.google_oauth_client_secret.strip(),
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if response.status_code >= 400:
        logger.warning("Google token exchange failed: %s", response.text[:500])
        raise GoogleOAuthError("Google token exchange failed")
    return response.json()


async def fetch_userinfo(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            GOOGLE_USERINFO,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code >= 400:
        raise GoogleOAuthError("Google userinfo failed")
    data = response.json()
    email = (data.get("email") or "").strip().lower()
    if not email:
        raise GoogleOAuthError("Google account has no email")
    data["email"] = email
    return data


def cache_sheets_access_token(access_token: str, expires_in: int) -> None:
    _sheets_access["access_token"] = access_token
    _sheets_access["expires_at"] = time.time() + max(int(expires_in) - 60, 0)


def clear_sheets_access_cache() -> None:
    _sheets_access["access_token"] = None
    _sheets_access["expires_at"] = 0.0


async def sheets_access_token() -> str:
    now = time.time()
    cached = _sheets_access.get("access_token")
    if cached and float(_sheets_access.get("expires_at") or 0) > now:
        return str(cached)
    refresh = settings.google_sheets_refresh_token.strip()
    if not refresh:
        raise GoogleNotConfigured("GOOGLE_SHEETS_REFRESH_TOKEN is not set")
    if not settings.google_oauth_client_id.strip() or not settings.google_oauth_client_secret.strip():
        raise GoogleNotConfigured("Google OAuth client is not set")
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            GOOGLE_TOKEN,
            data={
                "client_id": settings.google_oauth_client_id.strip(),
                "client_secret": settings.google_oauth_client_secret.strip(),
                "refresh_token": refresh,
                "grant_type": "refresh_token",
            },
        )
    if response.status_code >= 400:
        logger.warning("Sheets token refresh failed: %s", response.text[:500])
        if response.status_code < 500:
            # 400 invalid_grant / 401: the refresh token itself is dead.
            raise SheetsReconnectRequired("Sheets refresh token was rejected; reconnect needed")
        raise GoogleOAuthError("Sheets token refresh failed")
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise GoogleOAuthError("Sheets token refresh returned no access_token")
    cache_sheets_access_token(token, int(payload.get("expires_in") or 3600))
    return str(token)


async def read_sheet_values() -> dict[str, Any]:
    spreadsheet_id = settings.google_sheets_spreadsheet_id.strip()
    if not spreadsheet_id:
        raise GoogleNotConfigured("GOOGLE_SHEETS_SPREADSHEET_ID is not set")
    token = await sheets_access_token()
    range_ = settings.google_sheets_range.strip() or "Sheet1!A1:D20"
    url = SHEETS_VALUES.format(spreadsheet_id=spreadsheet_id, range_=range_)
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    if response.status_code >= 400:
        logger.warning("Sheets read failed: %s", response.text[:500])
        raise GoogleOAuthError("Sheets read failed")
    payload = response.json()
    values = payload.get("values") or []
    return {
        "spreadsheet_id": spreadsheet_id,
        "range": payload.get("range") or range_,
        "row_count": len(values),
        "rows": values[:20],
    }
