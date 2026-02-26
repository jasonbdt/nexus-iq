"""Unit tests for auth module."""

import pytest
from datetime import timedelta
from unittest.mock import patch

from app.internal.auth import (
    create_access_token,
    verify_password,
    get_password_hash,
)


def test_create_access_token_default_expiry():
    with patch("app.internal.auth.JWT_SECRET", "test-secret"):
        with patch("app.internal.auth.JWT_ALGORITHM", "HS256"):
            token = create_access_token({"sub": "user@test.com"})
            assert isinstance(token, str)
            assert len(token) > 0


def test_create_access_token_custom_expiry():
    with patch("app.internal.auth.JWT_SECRET", "test-secret"):
        with patch("app.internal.auth.JWT_ALGORITHM", "HS256"):
            token = create_access_token(
                {"sub": "user@test.com"},
                expires_delta=timedelta(minutes=60),
            )
            assert isinstance(token, str)


def test_verify_password_correct():
    hashed = get_password_hash("correct_password")
    assert verify_password("correct_password", hashed) is True


def test_verify_password_incorrect():
    hashed = get_password_hash("correct_password")
    assert verify_password("wrong_password", hashed) is False


def test_get_password_hash_produces_different_hashes():
    h1 = get_password_hash("same_password")
    h2 = get_password_hash("same_password")
    assert h1 != h2  # bcrypt uses random salt
    assert verify_password("same_password", h1)
    assert verify_password("same_password", h2)
