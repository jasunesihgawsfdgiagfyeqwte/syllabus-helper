# storage.py - SQLite persistence for syllabus data
# raw_text is encrypted at rest using Fernet (AES) for data privacy

import json
import time
import os
import base64
import hashlib

from cryptography.fernet import Fernet

from database import get_db

# derive encryption key from JWT_SECRET
_secret = os.environ.get("JWT_SECRET", "dev-fallback-key")
_key = base64.urlsafe_b64encode(hashlib.sha256(_secret.encode()).digest())
_fernet = Fernet(_key)


def _encrypt(text: str) -> str:
    return _fernet.encrypt(text.encode()).decode()


def _decrypt(token: str) -> str:
    try:
        return _fernet.decrypt(token.encode()).decode()
    except Exception:
        # Fallback: might be unencrypted legacy data
        return token


def save_syllabus(user_email: str, syllabus_id: str, data: dict) -> None:
    conn = get_db()
    conn.execute("""
        INSERT INTO syllabi (user_email, syllabus_id, course_info, deadlines, grading, grade_scale, policies, raw_text, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_email, syllabus_id)
        DO UPDATE SET course_info=excluded.course_info, deadlines=excluded.deadlines,
                      grading=excluded.grading, grade_scale=excluded.grade_scale,
                      policies=excluded.policies, raw_text=excluded.raw_text
    """, (
        user_email, syllabus_id,
        json.dumps(data.get("course_info", {}), ensure_ascii=False),
        json.dumps(data.get("deadlines", []), ensure_ascii=False),
        json.dumps(data.get("grading", []), ensure_ascii=False),
        json.dumps(data.get("grade_scale", []), ensure_ascii=False),
        json.dumps(data.get("policies", []), ensure_ascii=False),
        _encrypt(data.get("raw_text", "")),
        time.time(),
    ))
    conn.commit()
    conn.close()


def load_user_syllabi(user_email: str) -> dict[str, dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM syllabi WHERE user_email = ?", (user_email,)
    ).fetchall()
    conn.close()

    syllabi = {}
    for row in rows:
        row = dict(row)
        sid = row["syllabus_id"]
        syllabi[sid] = {
            "syllabus_id": sid,
            "course_info": json.loads(row["course_info"]),
            "deadlines": json.loads(row["deadlines"]),
            "grading": json.loads(row["grading"]),
            "grade_scale": json.loads(row["grade_scale"]),
            "policies": json.loads(row["policies"]),
            "raw_text": _decrypt(row["raw_text"]),
        }
    return syllabi


def delete_syllabus(user_email: str, syllabus_id: str) -> bool:
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM syllabi WHERE user_email = ? AND syllabus_id = ?",
        (user_email, syllabus_id)
    )
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def save_schedule(user_email: str, data: dict) -> None:
    conn = get_db()
    conn.execute("""
        INSERT INTO schedules (user_email, data) VALUES (?, ?)
        ON CONFLICT(user_email) DO UPDATE SET data=excluded.data
    """, (user_email, json.dumps(data, ensure_ascii=False)))
    conn.commit()
    conn.close()


def load_schedule(user_email: str) -> dict:
    conn = get_db()
    row = conn.execute(
        "SELECT data FROM schedules WHERE user_email = ?", (user_email,)
    ).fetchone()
    conn.close()
    if row:
        return json.loads(row["data"])
    return {}
