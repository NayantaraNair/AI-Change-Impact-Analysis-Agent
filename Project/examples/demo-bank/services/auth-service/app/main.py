"""Password authentication API; configuration is supplied by the deployment."""

import logging
import os
from datetime import datetime, timezone

import httpx
import jwt
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.auth.lockout import LoginAttemptTracker
from app.auth.password import PasswordHasher
from app.auth.session import SessionManager, TokenIssuer
from app.clients.notification import NotificationClient
from app.models import User

app = FastAPI(title="Demo Bank Authentication")
router = APIRouter()
logger = logging.getLogger(__name__)
engine = create_engine(os.environ["AUTH_DATABASE_URL"], pool_pre_ping=True)
sessions = sessionmaker(bind=engine)
issuer = TokenIssuer(os.environ["AUTH_JWT_SIGNING_KEY"])
password_hasher = PasswordHasher()
dummy_hash = password_hasher.hash(os.urandom(32).hex())
notifications = NotificationClient(os.environ.get("NOTIFICATION_URL", "http://notification-service:8080"))


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=4096)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


def get_database():
    with sessions() as database:
        yield database


@router.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest, database: Session = Depends(get_database)):
    identifier = str(body.email).casefold()
    tracker = LoginAttemptTracker(database)
    if tracker.is_locked(identifier):
        raise HTTPException(status_code=429, detail="Try again after the lockout window")
    user = database.scalar(select(User).where(User.email == identifier))
    valid = password_hasher.verify(user.password_hash if user else dummy_hash, body.password)
    if not user or not user.active or not valid:
        tracker.record(identifier, user.id if user else None, False)
        database.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")
    tracker.record(identifier, user.id, True)
    if password_hasher.needs_rehash(user.password_hash):
        user.password_hash = password_hasher.hash(body.password)
    tokens = SessionManager(database, issuer).create(user)
    database.commit()
    try:
        await notifications.login_alert(user.email, datetime.now(timezone.utc).isoformat())
    except httpx.HTTPError:
        logger.warning("Login alert delivery failed")
    return tokens


@router.post("/auth/logout", status_code=204)
def logout(body: RefreshRequest, database: Session = Depends(get_database)):
    try:
        SessionManager(database, issuer).revoke(body.refresh_token)
        database.commit()
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid session") from None
    return Response(status_code=204)


@router.post("/auth/token/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshRequest, database: Session = Depends(get_database)):
    try:
        tokens = SessionManager(database, issuer).refresh(body.refresh_token)
        database.commit()
        return tokens
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid session") from None


@router.post("/auth/password/reset", status_code=501)
def reset_password(body: PasswordResetRequest):
    # TODO: implement password reset request handling and audited recovery workflow.
    raise HTTPException(status_code=501, detail="Password reset is not implemented")


app.include_router(router)
