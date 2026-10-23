import hashlib
import hmac
import os
import secrets
import time

from db import execute, q1, now


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000)
    return f"pbkdf2${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt, digest = stored.split("$", 2)
    except ValueError:
        return False
    if algo != "pbkdf2":
        return False
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000)
    return hmac.compare_digest(test.hex(), digest)


SESSION_TTL = 30 * 24 * 3600


def create_session(user_id: int) -> str:
    token = secrets.token_hex(32)
    execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
        (token, user_id, now(), now() + SESSION_TTL),
    )
    return token


def session_user(token: str):
    if not token:
        return None
    row = q1(
        "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token=? AND s.expires_at>?",
        (token, now()),
    )
    if not row:
        return None
    try:
        execute("DELETE FROM sessions WHERE expires_at<?", (now(),))
    except Exception:
        pass
    return row


def drop_session(token: str):
    execute("DELETE FROM sessions WHERE token=?", (token,))
