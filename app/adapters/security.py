"""JWT and password implementation without FastAPI dependencies."""
from datetime import timedelta

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.domain.models import utc_now


class SecurityAdapter:
    """Keep the existing password algorithm and HS256 token contract."""

    def __init__(self, secret: str, minutes: int = 60):
        self.secret = secret
        self.minutes = minutes
        self.passwords = PasswordHash.recommended()

    def hash_password(self, password: str) -> str:
        """Hash with the installed pwdlib recommended algorithm."""
        return self.passwords.hash(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        """Treat unknown stored hash formats as invalid credentials."""
        try:
            return self.passwords.verify(plain, hashed)
        except UnknownHashError:
            return False

    def token(self, email: str, role: str) -> str:
        """Issue the unchanged sub/role/exp JWT payload."""
        return jwt.encode({'sub': email, 'role': role,
                           'exp': utc_now() + timedelta(minutes=self.minutes)},
                          self.secret, algorithm='HS256')

    def subject(self, token: str) -> str | None:
        """Validate signature and expiry before returning a subject."""
        try:
            payload = jwt.decode(token, self.secret, algorithms=['HS256'])
            subject = payload.get('sub')
            return subject if isinstance(subject, str) else None
        except jwt.InvalidTokenError:
            return None
