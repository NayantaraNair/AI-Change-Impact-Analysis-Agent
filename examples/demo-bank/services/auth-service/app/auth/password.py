"""Password hashing and enrollment policy for password-based accounts."""

from argon2 import PasswordHasher as ArgonHasher
from argon2.exceptions import InvalidHashError, VerificationError


class PasswordHasher:
    """Keep the hashing algorithm out of controllers and persistence models."""

    def __init__(self) -> None:
        self._hasher = ArgonHasher(time_cost=3, memory_cost=65536, parallelism=2)

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, encoded_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(encoded_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, encoded_hash: str) -> bool:
        return self._hasher.check_needs_rehash(encoded_hash)


class PasswordPolicy:
    """Validate new passwords before storing an Argon2 hash."""

    MIN_LENGTH = 12
    MAX_LENGTH = 128

    def validate(self, password: str, email: str) -> None:
        if not self.MIN_LENGTH <= len(password) <= self.MAX_LENGTH:
            raise ValueError("Password must contain between 12 and 128 characters")
        if not any(character.isalpha() for character in password):
            raise ValueError("Password must contain a letter")
        if not any(character.isdigit() for character in password):
            raise ValueError("Password must contain a number")
        if email.split("@", 1)[0].casefold() in password.casefold():
            raise ValueError("Password must not contain the email account name")
