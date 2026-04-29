# database.py - SQLite setup for users and syllabus data

import sqlite3
import os
from pathlib import Path

DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).resolve().parent / "data" / "syllabus_helper.db"))


def get_db() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            password_hash TEXT,
            provider TEXT NOT NULL DEFAULT 'email',
            picture TEXT DEFAULT '',
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS syllabi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            syllabus_id TEXT NOT NULL,
            course_info TEXT NOT NULL DEFAULT '{}',
            deadlines TEXT NOT NULL DEFAULT '[]',
            grading TEXT NOT NULL DEFAULT '[]',
            grade_scale TEXT NOT NULL DEFAULT '[]',
            policies TEXT NOT NULL DEFAULT '[]',
            raw_text TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            UNIQUE(user_email, syllabus_id),
            FOREIGN KEY(user_email) REFERENCES users(email)
        );

        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT UNIQUE NOT NULL,
            data TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY(user_email) REFERENCES users(email)
        );

        CREATE INDEX IF NOT EXISTS idx_syllabi_user ON syllabi(user_email);
    """)
    conn.commit()
    conn.close()
