import pytest
from backend.services.auth import hash_password, verify_password, generate_token


def test_hash_password():
    h = hash_password("test123")
    assert len(h) == 64
    assert h == hash_password("test123")


def test_verify_password():
    h = hash_password("secret")
    assert verify_password("secret", h) is True
    assert verify_password("wrong", h) is False


def test_generate_token():
    t1 = generate_token()
    t2 = generate_token()
    assert len(t1) > 20
    assert t1 != t2
