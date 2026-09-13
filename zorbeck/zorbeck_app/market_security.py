"""Password authentication, opaque sessions and CSRF checks for the marketplace."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from urllib.parse import parse_qsl, urlsplit

from fastapi import HTTPException, Request

from zorbeck_app.config import settings
from zorbeck_app.market_store import available, database, rate_limit


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password: str) -> str:
    # OWASP's 32 MiB scrypt profile: N=2^15, r=8, p=3.
    salt = secrets.token_hex(16)
    hashed = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3,
                            maxmem=67108864, dklen=32)
    return f"scrypt-32768-8-3${salt}${hashed.hex()}"


def password_matches(password: str, stored: str) -> bool:
    try:
        algorithm, salt, expected = stored.split("$")
        if algorithm != "scrypt-32768-8-3" or len(password) > 128:
            return False
        hashed = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3,
                                maxmem=67108864, dklen=32)
        return hmac.compare_digest(hashed.hex(), expected)
    except (ValueError, TypeError):
        return False


DUMMY_HASH = password_hash(secrets.token_urlsafe(32))


def validate_password(value) -> str:
    if not isinstance(value, str) or not 12 <= len(value) <= 128:
        raise HTTPException(400, "Use a password with 12–128 characters.")
    if value.lower() in {"password1234", "123456789012", "qwerty123456", "passwordpassword"}:
        raise HTTPException(400, "Please choose a less common password.")
    return value


def email_address(value) -> str:
    if not isinstance(value, str):
        raise HTTPException(400, "Enter a valid email address.")
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+", value):
        raise HTTPException(400, "Enter a valid email address.")
    return value


def session_cookie() -> str:
    return "__Host-zorbeck-session" if settings.cookie_secure else "zorbeck-session"


def csrf_cookie() -> str:
    return "__Host-zorbeck-csrf" if settings.cookie_secure else "zorbeck-csrf"


def user_for(request: Request):
    if not available():
        return None
    token = request.cookies.get(session_cookie(), "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return None
    with database() as conn:
        row = conn.execute(
            "SELECT u.id,u.email,u.role,u.marketing FROM users u JOIN sessions s ON u.id=s.user_id "
            "WHERE s.token_hash=? AND s.expires_at>?", (digest(token), int(time.time()))).fetchone()
    return dict(row) if row else None


def require_user(request: Request):
    user = user_for(request)
    if not user:
        raise HTTPException(401, "Please sign in to continue.")
    return user


def require_admin(request: Request):
    user = require_user(request)
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator access required.")
    return user


def start_session(response, user_id: str) -> None:
    token, now = secrets.token_urlsafe(32), int(time.time())
    with database(write=True) as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at<=?", (now,))
        conn.execute("INSERT INTO sessions VALUES (?,?,?,?)", (digest(token), user_id, now+604800, now))
    response.set_cookie(session_cookie(), token, max_age=604800, secure=settings.cookie_secure,
                        httponly=True, samesite="lax", path="/")
    set_csrf(response, secrets.token_urlsafe(32))


def set_csrf(response, token: str):
    response.set_cookie(csrf_cookie(), token, max_age=604800, secure=settings.cookie_secure,
                        httponly=True, samesite="lax", path="/")


def csrf_for(request):
    value = request.cookies.get(csrf_cookie(), "")
    return value if re.fullmatch(r"[A-Za-z0-9_-]{43}", value) else secrets.token_urlsafe(32)


async def read_input(request: Request, limit=12000):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(413, "The submission is too large.")
    try:
        if "application/json" in request.headers.get("content-type", ""):
            import json
            data = json.loads(body)
        else:
            data = dict(parse_qsl(body.decode(), max_num_fields=80))
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, "Please check the form and try again.") from None
    if not isinstance(data, dict):
        raise HTTPException(400, "Please submit the form.")
    token = request.headers.get("x-csrf-token", "") or data.get("csrf", "")
    expected = request.cookies.get(csrf_cookie(), "")
    if not isinstance(token, str) or not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(403, "This form expired. Refresh the page and try again.")
    origin = request.headers.get("origin")
    expected_origin = settings.public_base_url or str(request.base_url).rstrip("/")
    if origin and origin != expected_origin:
        raise HTTPException(403, "Please submit the form from Zorbeck.")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Please submit the form from Zorbeck.")
    if data.get("website"):
        raise HTTPException(400, "This submission could not be accepted.")
    return data


def auth_limit(request: Request, email: str):
    # Railway supplies X-Real-IP. Never trust a caller's leftmost X-Forwarded-For.
    ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
    rate_limit("auth-ip:"+digest(ip), 30)
    rate_limit("auth-email:"+digest(email), 10)
    rate_limit("auth-global", 120, 60)


def safe_next(value) -> str:
    if not isinstance(value, str) or len(value) > 250 or "\\" in value:
        return "/account"
    parts = urlsplit(value)
    if parts.scheme or parts.netloc or parts.query or parts.fragment:
        return "/account"
    return value if re.fullmatch(r"/(?:account|sell(?:/new)?|admin(?:/claim)?|properties/[a-z0-9-]+)", value) else "/account"
