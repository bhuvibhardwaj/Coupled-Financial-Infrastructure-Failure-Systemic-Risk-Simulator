"""Database-backed login sessions and role checks."""

import hashlib
import hmac
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.db import connect

router = APIRouter(prefix="/api/auth", tags=["auth"])
COOKIE_NAME = "risk_session"
SESSION_SECONDS = 8 * 60 * 60
ITERATIONS = 600_000


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must have at least 12 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        method, rounds, salt, expected = stored.split("$")
        if method != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(rounds)
        )
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(request: Request) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Please sign in")
    with connect() as conn:
        user = conn.execute(
            "SELECT u.id, u.name, u.email, u.role "
            "FROM user_sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = %s AND s.expires_at > now() AND u.active",
            (token_hash(token),),
        ).fetchone()
    if user is None:
        raise HTTPException(401, "Session expired; please sign in again")
    return user


def admin_user(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator access required")
    return user


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=1024)


@router.post("/login")
def login(body: LoginRequest, response: Response):
    with connect() as conn:
        user = conn.execute(
            "SELECT id, name, email, role, password_hash FROM users "
            "WHERE lower(email) = lower(%s) AND active",
            (body.email.strip(),),
        ).fetchone()
        if user is None or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(401, "Invalid email or password")
        token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO user_sessions (token_hash, user_id, expires_at) "
            "VALUES (%s, %s, now() + interval '8 hours')",
            (token_hash(token), user["id"]),
        )
    response.set_cookie(
        key=COOKIE_NAME, value=token, httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax", path="/api", max_age=SESSION_SECONDS,
    )
    return {key: user[key] for key in ("id", "name", "email", "role")}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return user


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        with connect() as conn:
            conn.execute(
                "DELETE FROM user_sessions WHERE token_hash = %s", (token_hash(token),)
            )
    response.delete_cookie(COOKIE_NAME, path="/api")
    return {"ok": True}
