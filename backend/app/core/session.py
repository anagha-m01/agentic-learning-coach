"""Session cookie management and identity generation."""
import secrets

from fastapi import Request, Response

from app.core.config import settings

SESSION_ID_BYTES = 32  # 256-bit entropy


def generate_session_id() -> str:
    return secrets.token_urlsafe(SESSION_ID_BYTES)


def get_or_create_session_id(request: Request, response: Response) -> str:
    """Retrieve existing session ID or generate and set a new one."""
    existing = request.cookies.get(settings.session_cookie_name)
    if existing and _looks_valid(existing):
        return existing

    new_id = generate_session_id()
    set_session_cookie(response, new_id)
    return new_id


def set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.is_production,
        samesite="none" if settings.is_production else "lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.is_production,
        samesite="none" if settings.is_production else "lax",
    )


def _looks_valid(value: str) -> bool:
    # Validate session ID format and length
    return 20 <= len(value) <= 128 and all(
        c.isalnum() or c in "-_" for c in value
    )
