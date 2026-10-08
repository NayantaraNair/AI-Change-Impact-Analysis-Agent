"""Failed-login tracking; unknown email addresses follow the same lockout policy."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LoginAttempt


class LoginAttemptTracker:
    MAX_FAILURES = 5
    LOCKOUT_WINDOW = timedelta(minutes=15)

    def __init__(self, database: Session) -> None:
        self.database = database

    def is_locked(self, identifier: str, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        attempts = self.database.scalars(
            select(LoginAttempt)
            .where(LoginAttempt.login_identifier == identifier)
            .where(LoginAttempt.attempted_at > now - self.LOCKOUT_WINDOW)
            .order_by(LoginAttempt.attempted_at.desc())
        )
        failures = 0
        for attempt in attempts:
            if attempt.successful:
                break
            failures += 1
            if failures >= self.MAX_FAILURES:
                return True
        return False

    def record(self, identifier: str, user_id: str | None, successful: bool) -> None:
        self.database.add(LoginAttempt(
            login_identifier=identifier,
            user_id=user_id,
            successful=successful,
            attempted_at=datetime.now(timezone.utc),
        ))
        self.database.flush()
