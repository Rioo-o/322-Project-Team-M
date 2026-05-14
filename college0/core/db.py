"""SQLite schema and connection helpers."""
from __future__ import annotations

import os
import sqlite3

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(HERE, "college0.db")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('registrar','instructor','student')),
    full_name TEXT NOT NULL,
    must_change_pw INTEGER NOT NULL DEFAULT 0,
    warnings INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
        -- active | suspended | terminated | fired | graduated
    suspended_until_semester INTEGER,
    fine_due REAL NOT NULL DEFAULT 0,
    is_new INTEGER NOT NULL DEFAULT 0   -- triggers tutorial on first login
);

CREATE TABLE IF NOT EXISTS students (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    gpa REAL NOT NULL DEFAULT 0,
    semester_gpa REAL NOT NULL DEFAULT 0,
    courses_completed INTEGER NOT NULL DEFAULT 0,
    honors INTEGER NOT NULL DEFAULT 0,
    semesters_completed INTEGER NOT NULL DEFAULT 0,
    -- Spec: students of cancelled courses get "one more chance" to choose
    -- other courses. We flip this flag on those students when their course
    -- cancels, which lets `try_register` accept them during the RUNNING
    -- phase. Cleared automatically when the registrar advances to GRADING.
    special_reg_open INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS instructors (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    apply_type TEXT NOT NULL CHECK(apply_type IN ('student','instructor')),
    full_name TEXT NOT NULL,
    gpa REAL,
    note TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
        -- pending | accepted | rejected
    decision_note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    title TEXT NOT NULL,
    instructor_id INTEGER REFERENCES users(id),
    day TEXT NOT NULL,            -- Mon | Tue | Wed | Thu | Fri
    start_hour INTEGER NOT NULL,  -- 9..18
    end_hour INTEGER NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 10,
    semester INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'  -- active | cancelled
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES users(id),
    course_id INTEGER NOT NULL REFERENCES courses(id),
    status TEXT NOT NULL DEFAULT 'enrolled',
        -- enrolled | waitlist | completed | failed | dropped
    grade TEXT,         -- A,B+,B,C+,C,D,F or NULL
    semester INTEGER NOT NULL,
    UNIQUE(student_id, course_id, semester)
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES users(id),
    course_id INTEGER NOT NULL REFERENCES courses(id),
    stars INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 5),
    body TEXT NOT NULL,
    visible INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS taboo_words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user_id INTEGER NOT NULL REFERENCES users(id),
    against_user_id INTEGER REFERENCES users(id),
    against_role TEXT NOT NULL,    -- student | instructor
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',  -- open | resolved
    action TEXT,                   -- warn_target | warn_filer | dismissed
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS semester_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    semester INTEGER NOT NULL DEFAULT 1,
    phase TEXT NOT NULL DEFAULT 'setup'
        -- setup | registration | running | grading
);

CREATE TABLE IF NOT EXISTS warnings_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS qa_corpus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,   -- general | student | instructor | course:CODE
    question TEXT NOT NULL,
    answer TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS graduation_apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def init_schema() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        # Make sure singleton state row exists.
        conn.execute(
            "INSERT OR IGNORE INTO semester_state (id, semester, phase) VALUES (1, 1, 'setup')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('student_quota', '20')"
        )
        # Backwards-compat migrations for users with an older college0.db.
        _ensure_column(conn, "students", "special_reg_open",
                       "INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    finally:
        conn.close()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str,
                   definition: str) -> None:
    """Add `column` to `table` if it isn't there yet (idempotent migration)."""
    cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
