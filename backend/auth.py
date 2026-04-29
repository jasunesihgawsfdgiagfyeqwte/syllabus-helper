# auth.py - handles user authentication (email/password + Google OAuth)

import os
import time
import secrets

import bcrypt
import jwt

from database import get_db

JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_EXPIRY = 7 * 24 * 3600  # 7 days

def register_user(email: str, password: str, name: str = "") -> dict:
    email = email.lower().strip()
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")

    conn = get_db()
    existing = conn.execute("SELECT email FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        raise ValueError("Email already registered")

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn.execute(
        "INSERT INTO users (email, name, password_hash, provider, created_at) VALUES (?, ?, ?, ?, ?)",
        (email, name or email.split("@")[0], hashed, "email", time.time())
    )
    conn.commit()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return _make_token(dict(user))



def login_user(email: str, password: str) -> dict:
    email = email.lower().strip()
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if not user:
        raise ValueError("Invalid email or password")

    user = dict(user)
    if not user.get("password_hash"):
        raise ValueError("This account uses Google sign-in. Please use the Google button.")

    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        raise ValueError("Invalid email or password")

    return _make_token(user)



def google_login(credential: str) -> dict:
    payload = _verify_google_token(credential)
    if not payload:
        raise ValueError("Invalid Google credential")

    email = payload["email"].lower()
    name = payload.get("name", "")
    picture = payload.get("picture", "")

    conn = get_db()
    existing = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    if not existing:
        conn.execute(
            "INSERT INTO users (email, name, provider, picture, created_at) VALUES (?, ?, ?, ?, ?)",
            (email, name, "google", picture, time.time())
        )
    else:
        conn.execute(
            "UPDATE users SET name = ?, picture = ? WHERE email = ?",
            (name, picture, email)
        )
    conn.commit()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return _make_token(dict(user))


def _verify_google_token(credential: str) -> dict | None:
    try:
        payload = jwt.decode(credential, options={"verify_signature": False})
        if payload.get("email"):
            return payload
    except Exception:
        pass
    return None



def _make_token(user: dict) -> dict:
    payload = {
        "email": user["email"],
        "name": user.get("name", ""),
        "exp": time.time() + JWT_EXPIRY,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return {
        "token": token,
        "user": {
            "email": user["email"],
            "name": user.get("name", ""),
            "picture": user.get("picture", ""),
            "provider": user.get("provider", "email"),
        },
    }


def verify_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("exp", 0) > time.time():
            return payload
    except Exception:
        pass
    return None
