"""Issue signed JWT pairs and persist only digests of refresh tokens."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RefreshToken, User


class TokenIssuer:
    ACCESS_LIFETIME = timedelta(minutes=15)
    REFRESH_LIFETIME = timedelta(days=7)

    def __init__(self, signing_key: str) -> None:
        if len(signing_key) < 32:
            raise ValueError("JWT signing key must contain at least 32 characters")
        self.signing_key = signing_key

    def issue(self, user_id: str, token_id: str, kind: str, expires_at: datetime) -> str:
        return jwt.encode({
            "sub": user_id, "jti": token_id, "token_type": kind,
            "iss": "demo-bank-auth", "aud": "demo-bank-services",
            "iat": datetime.now(timezone.utc), "exp": expires_at,
        }, self.signing_key, algorithm="HS256")

    def decode_refresh(self, token: str) -> dict:
        claims = jwt.decode(
            token, self.signing_key, algorithms=["HS256"],
            issuer="demo-bank-auth", audience="demo-bank-services",
            options={"require": ["sub", "jti", "exp", "iat", "token_type"]},
        )
        if claims["token_type"] != "refresh":
            raise ValueError("Refresh token required")
        return claims


class SessionManager:
    """Refresh rotation and logout are committed by the caller's transaction."""

    def __init__(self, database: Session, issuer: TokenIssuer) -> None:
        self.database = database
        self.issuer = issuer

    def create(self, user: User) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        token_id = str(uuid4())
        expires_at = now + self.issuer.REFRESH_LIFETIME
        refresh = self.issuer.issue(user.id, token_id, "refresh", expires_at)
        self.database.add(RefreshToken(
            id=token_id, user_id=user.id, token_digest=sha256(refresh.encode()).hexdigest(),
            expires_at=expires_at,
        ))
        access = self.issuer.issue(user.id, str(uuid4()), "access", now + self.issuer.ACCESS_LIFETIME)
        return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}

    def _find_active(self, token: str) -> RefreshToken:
        claims = self.issuer.decode_refresh(token)
        record = self.database.scalar(
            select(RefreshToken).where(RefreshToken.id == claims["jti"]).with_for_update()
        )
        if (record is None or record.revoked_at is not None
                or record.token_digest != sha256(token.encode()).hexdigest()
                or record.user_id != claims["sub"]
                or record.expires_at <= datetime.now(timezone.utc)):
            raise ValueError("Session is no longer active")
        return record

    def refresh(self, token: str) -> dict[str, str]:
        record = self._find_active(token)
        user = self.database.get(User, record.user_id)
        if user is None or not user.active:
            raise ValueError("Account is unavailable")
        record.revoked_at = datetime.now(timezone.utc)
        return self.create(user)

    def revoke(self, token: str) -> None:
        record = self._find_active(token)
        record.revoked_at = datetime.now(timezone.utc)
