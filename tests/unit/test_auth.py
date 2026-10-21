"""Password and token contract regression tests."""
from datetime import datetime, timezone
import jwt
import pytest
from app.adapters.security import SecurityAdapter


@pytest.mark.parametrize('minutes', [15, 60])
def test_token_claims_and_expiry(minutes):
    security = SecurityAdapter('test-secret', minutes)
    token = security.token('user@test.com', 'member')
    decoded = jwt.decode(token, 'test-secret', algorithms=['HS256'])
    assert decoded['sub'] == 'user@test.com'
    assert decoded['role'] == 'member'
    assert abs(decoded['exp'] - datetime.now(timezone.utc).timestamp() - minutes * 60) < 2
    assert security.subject(token) == 'user@test.com'


def test_password_verification_and_random_salts():
    security = SecurityAdapter('test-secret')
    first = security.hash_password('same_password')
    second = security.hash_password('same_password')
    assert first != second
    assert security.verify_password('same_password', first)
    assert security.verify_password('same_password', second)
    assert not security.verify_password('wrong', first)
    assert not security.verify_password('same_password', 'unknown-format')


def test_invalid_tokens_are_rejected():
    security = SecurityAdapter('test-secret')
    expired = SecurityAdapter('test-secret', -1).token('test@example.test', 'member')
    assert security.subject(expired) is None
    assert security.subject('invalid') is None
    assert SecurityAdapter('other-secret').subject(security.token('test@test.com', 'member')) is None
