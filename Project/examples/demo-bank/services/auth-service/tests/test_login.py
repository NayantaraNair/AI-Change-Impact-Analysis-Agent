"""Local unit tests exercise login policy without HTTP providers or credentials."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.auth.lockout import LoginAttemptTracker
from app.auth.password import PasswordHasher, PasswordPolicy


class AttemptDatabase:
    def __init__(self, results):
        self.results = results

    def scalars(self, statement):
        return iter(self.results)


def test_correct_password_matches_stored_hash():
    hasher = PasswordHasher()
    encoded = hasher.hash("Fictional River 2048")
    assert hasher.verify(encoded, "Fictional River 2048")
    assert not hasher.verify(encoded, "Different password 2048")


def test_password_policy_rejects_email_account_name():
    with pytest.raises(ValueError, match="email account name"):
        PasswordPolicy().validate("Nadia River 2048", "nadia@example.com")


def test_five_failed_logins_lock_the_account():
    attempts = [SimpleNamespace(successful=False) for _ in range(5)]
    tracker = LoginAttemptTracker(AttemptDatabase(attempts))
    assert tracker.is_locked("nadia@example.com", datetime.now(timezone.utc))


def test_successful_login_breaks_the_failure_sequence():
    attempts = [SimpleNamespace(successful=False), SimpleNamespace(successful=True)]
    attempts += [SimpleNamespace(successful=False) for _ in range(5)]
    tracker = LoginAttemptTracker(AttemptDatabase(attempts))
    assert not tracker.is_locked("nadia@example.com", datetime.now(timezone.utc))
