import secrets
from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, status

from versionweaver.config import Settings, get_settings

Role = Literal["developer", "runner", "admin"]


def _presented_token(authorization: str | None, x_api_token: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:]
    return x_api_token


def _authenticate(
    authorization: Annotated[str | None, Header()] = None,
    x_api_token: Annotated[str | None, Header()] = None,
) -> Role:
    settings: Settings = get_settings()
    presented = _presented_token(authorization, x_api_token)
    if not presented:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing API token")

    # Development and test fall back to one token. Production startup requires distinct values.
    candidates: tuple[tuple[Role, str], ...] = (
        ("admin", settings.admin_api_token or settings.api_token),
        ("runner", settings.runner_api_token or settings.api_token),
        ("developer", settings.api_token),
    )
    for role, expected in candidates:
        if secrets.compare_digest(presented, expected):
            return role
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API token")


def require_control_token(role: Annotated[Role, Depends(_authenticate)]) -> Role:
    if role not in {"developer", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="developer role required")
    return role


def require_runner_token(role: Annotated[Role, Depends(_authenticate)]) -> Role:
    if role not in {"runner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="runner role required")
    return role


def require_admin_token(role: Annotated[Role, Depends(_authenticate)]) -> Role:
    if role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin role required")
    return role
