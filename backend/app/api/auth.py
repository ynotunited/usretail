"""
Auth API router.

Endpoints:
  POST /auth/token  — issue a JWT access token (username + password)
  GET  /auth/me     — return current user info and role
  GET  /auth/roles  — list available roles and their permissions
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated

from app.auth.dependencies import (
    authenticate_user,
    create_access_token,
    get_current_user,
    _auth_disabled,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", summary="Issue a JWT access token")
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> JSONResponse:
    """
    OAuth2 password flow. Returns a Bearer JWT on success.

    Default dev credentials (when AUTH_DISABLED=false):
      - analyst / analyst123
      - reviewer / reviewer123
      - admin / admin123
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(username=user["username"], role=user["role"])
    return JSONResponse({
        "access_token": token,
        "token_type": "bearer",
        "username": user["username"],
        "role": user["role"],
        "auth_disabled": _auth_disabled(),
    })


@router.get("/me", summary="Return current user info and role")
def get_me(user: dict = Depends(get_current_user)) -> JSONResponse:
    return JSONResponse({
        "username": user["username"],
        "role": user["role"],
        "auth_disabled": _auth_disabled(),
    })


@router.get("/roles", summary="List roles and their permissions")
def list_roles() -> JSONResponse:
    return JSONResponse({
        "roles": [
            {
                "role": "analyst",
                "level": 0,
                "permissions": [
                    "GET /datasets", "GET /analyses/runs",
                    "POST /analyses/run", "POST /analyses/overrides",
                ],
            },
            {
                "role": "reviewer",
                "level": 1,
                "permissions": [
                    "All analyst permissions",
                    "POST /report/generate",
                    "GET /report/{run_id}/csv",
                ],
            },
            {
                "role": "admin",
                "level": 2,
                "permissions": [
                    "All reviewer permissions",
                    "GET /audit", "GET /audit/{entity_id}",
                    "DELETE operations",
                ],
            },
        ],
        "auth_disabled": _auth_disabled(),
    })
