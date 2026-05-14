"""Thin CRUD helpers around the SQLite database.

Each function opens its own connection and commits before returning,
so callers don't need to worry about transactions.
"""
from __future__ import annotations

from typing import Iterable, Optional

from .db import connect

GRADE_POINTS = {
    "A": 4.0, "A-": 3.7,
    "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7,
    "D+": 1.3, "D": 1.0,
    "F": 0.0,
}

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]


# ---------- semester ----------

def get_semester_state() -> dict:
    with connect() as c:
        row = c.execute("SELECT semester, phase FROM semester_state WHERE id=1").fetchone()
    return dict(row)


def set_phase(phase: str) -> None:
    with connect() as c:
        c.execute("UPDATE semester_state SET phase=? WHERE id=1", (phase,))
        c.commit()


def advance_semester() -> list[str]:
    """Roll forward to the next semester (setup phase).

    Spec: "any students receiving up to 3 warnings will be suspended for
    1 semester …". The suspension is time-boxed, so when we cross into
    the new semester we lift the hold on anyone whose
    ``suspended_until_semester`` has now arrived. Their warning counter
    is reset to 0 (clean slate after serving the punishment); any
    outstanding fine is left in place so the registrar / student can
    still settle it.

    Returns a list of human-readable events for the UI's "Latest rule
    events" panel.
    """
    events: list[str] = []
    with connect() as c:
        c.execute(
            "UPDATE semester_state SET semester=semester+1, phase='setup' WHERE id=1"
        )
        new_sem = c.execute(
            "SELECT semester FROM semester_state WHERE id=1"
        ).fetchone()[0]
        # Anyone whose suspension was set to end at-or-before this new
        # semester is reactivated.
        rows = c.execute(
            """
            SELECT id, full_name, role, fine_due FROM users
             WHERE status='suspended'
               AND suspended_until_semester IS NOT NULL
               AND suspended_until_semester <= ?
            """,
            (new_sem,),
        ).fetchall()
        for r in rows:
            c.execute(
                """
                UPDATE users
                   SET status='active',
                       suspended_until_semester=NULL,
                       warnings=0
                 WHERE id=?
                """,
                (r["id"],),
            )
            note = (f"Reinstated {r['role']} {r['full_name']} "
                    f"(suspension served; warnings cleared)")
            if r["fine_due"]:
                note += f" — outstanding fine: ${r['fine_due']:.0f}"
            events.append(note + ".")
        c.commit()
    return events


# ---------- users ----------

def get_user(user_id: int) -> Optional[dict]:
    with connect() as c:
        r = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(r) if r else None


def find_user(username: str) -> Optional[dict]:
    with connect() as c:
        r = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return dict(r) if r else None


def list_users(role: Optional[str] = None) -> list[dict]:
    with connect() as c:
        if role:
            rows = c.execute("SELECT * FROM users WHERE role=? ORDER BY full_name", (role,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM users ORDER BY role, full_name").fetchall()
    return [dict(r) for r in rows]


def list_students() -> list[dict]:
    """Students plus their academic record."""
    with connect() as c:
        rows = c.execute(
            """
            SELECT u.*, s.gpa, s.semester_gpa, s.courses_completed, s.honors
            FROM users u JOIN students s ON s.user_id=u.id
            WHERE u.role='student'
            ORDER BY u.full_name
            """
        ).fetchall()
    return [dict(r) for r in rows]


def list_instructors() -> list[dict]:
    with connect() as c:
        rows = c.execute(
            """
            SELECT u.* FROM users u JOIN instructors i ON i.user_id=u.id
            WHERE u.role='instructor'
            ORDER BY u.full_name
            """
        ).fetchall()
    return [dict(r) for r in rows]


def update_password(user_id: int, new_password: str) -> None:
    with connect() as c:
        c.execute(
            "UPDATE users SET password=?, must_change_pw=0 WHERE id=?",
            (new_password, user_id),
        )
        c.commit()


def clear_first_login(user_id: int) -> None:
    with connect() as c:
        c.execute("UPDATE users SET is_new=0 WHERE id=?", (user_id,))
        c.commit()


def warn_user(user_id: int, reason: str) -> int:
    """Increment warning counter, log it, return total warnings (after)."""
    with connect() as c:
        c.execute(
            "UPDATE users SET warnings = warnings + 1 WHERE id=?",
            (user_id,),
        )
        c.execute(
            "INSERT INTO warnings_log (user_id, reason) VALUES (?,?)",
            (user_id, reason),
        )
        total = c.execute(
            "SELECT warnings FROM users WHERE id=?", (user_id,)
        ).fetchone()[0]
        c.commit()
    return total


def list_warnings(user_id: int) -> list[dict]:
    with connect() as c:
        rows = c.execute(
            "SELECT reason, created_at FROM warnings_log WHERE user_id=? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def set_status(user_id: int, status: str) -> None:
    with connect() as c:
        c.execute("UPDATE users SET status=? WHERE id=?", (status, user_id))
        c.commit()


def suspend_user(user_id: int, until_semester: int, fine: float = 100.0) -> None:
    with connect() as c:
        c.execute(
            """
            UPDATE users SET status='suspended',
                             suspended_until_semester=?,
                             fine_due=fine_due+?
             WHERE id=?
            """,
            (until_semester, fine, user_id),
        )
        c.commit()


def pay_fine(user_id: int) -> None:
    with connect() as c:
        c.execute("UPDATE users SET fine_due=0 WHERE id=?", (user_id,))
        c.commit()


def consume_honor_to_clear_warning(user_id: int) -> bool:
    """Use one honor token to remove one warning. Returns True on success."""
    with connect() as c:
        row = c.execute(
            """
            SELECT s.honors, u.warnings FROM users u
            JOIN students s ON s.user_id=u.id WHERE u.id=?
            """,
            (user_id,),
        ).fetchone()
        if not row or row[0] <= 0 or row[1] <= 0:
            return False
        c.execute("UPDATE students SET honors=honors-1 WHERE user_id=?", (user_id,))
        c.execute("UPDATE users SET warnings=warnings-1 WHERE id=?", (user_id,))
        c.commit()
    return True


# ---------- special re-registration window ----------

def set_special_reg(student_id: int, value: int) -> None:
    """Open (1) or close (0) the special re-registration window for one student."""
    with connect() as c:
        c.execute(
            "UPDATE students SET special_reg_open=? WHERE user_id=?",
            (value, student_id),
        )
        c.commit()


def get_special_reg(student_id: int) -> int:
    with connect() as c:
        r = c.execute(
            "SELECT special_reg_open FROM students WHERE user_id=?",
            (student_id,),
        ).fetchone()
    return int(r["special_reg_open"]) if r else 0


def list_special_reg_students() -> list[dict]:
    """Active students currently eligible for the 'one more chance' window."""
    with connect() as c:
        rows = c.execute(
            """
            SELECT u.id, u.full_name FROM users u
            JOIN students s ON s.user_id = u.id
            WHERE u.role='student' AND u.status='active' AND s.special_reg_open=1
            ORDER BY u.full_name
            """
        ).fetchall()
    return [dict(r) for r in rows]


def clear_all_special_reg() -> int:
    """Close the window for everyone. Returns rows affected."""
    with connect() as c:
        cur = c.execute(
            "UPDATE students SET special_reg_open=0 WHERE special_reg_open=1"
        )
        c.commit()
        return cur.rowcount


# ---------- applications ----------

def create_application(apply_type: str, full_name: str, gpa: Optional[float], note: str) -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO applications (apply_type, full_name, gpa, note) VALUES (?,?,?,?)",
            (apply_type, full_name, gpa, note),
        )
        c.commit()
        return cur.lastrowid


def list_applications(status: Optional[str] = None) -> list[dict]:
    with connect() as c:
        if status:
            rows = c.execute(
                "SELECT * FROM applications WHERE status=? ORDER BY id DESC",
                (status,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM applications ORDER BY id DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def update_application(app_id: int, status: str, decision_note: str) -> None:
    with connect() as c:
        c.execute(
            "UPDATE applications SET status=?, decision_note=? WHERE id=?",
            (status, decision_note, app_id),
        )
        c.commit()


def create_student_user(full_name: str) -> tuple[int, str, str]:
    """Make a new student user with auto username + temp password."""
    base = full_name.lower().split()[0]
    with connect() as c:
        username = base
        i = 1
        while c.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            i += 1
            username = f"{base}{i}"
        password = f"temp{i if i > 1 else 1}"
        cur = c.execute(
            """
            INSERT INTO users (username, password, role, full_name, must_change_pw, is_new)
            VALUES (?, ?, 'student', ?, 1, 1)
            """,
            (username, password, full_name),
        )
        uid = cur.lastrowid
        c.execute("INSERT INTO students (user_id) VALUES (?)", (uid,))
        c.commit()
    return uid, username, password


def create_instructor_user(full_name: str) -> tuple[int, str, str]:
    base = full_name.lower().split()[0]
    with connect() as c:
        username = f"prof_{base}"
        i = 1
        while c.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            i += 1
            username = f"prof_{base}{i}"
        password = f"temp{i if i > 1 else 1}"
        cur = c.execute(
            """
            INSERT INTO users (username, password, role, full_name, must_change_pw, is_new)
            VALUES (?, ?, 'instructor', ?, 1, 1)
            """,
            (username, password, full_name),
        )
        uid = cur.lastrowid
        c.execute("INSERT INTO instructors (user_id) VALUES (?)", (uid,))
        c.commit()
    return uid, username, password


# ---------- courses ----------

def list_courses(semester: Optional[int] = None, only_active: bool = False) -> list[dict]:
    q = "SELECT c.*, u.full_name AS instructor_name FROM courses c LEFT JOIN users u ON u.id=c.instructor_id"
    args: list = []
    clauses = []
    if semester is not None:
        clauses.append("c.semester=?")
        args.append(semester)
    if only_active:
        clauses.append("c.status='active'")
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY c.code"
    with connect() as c:
        rows = c.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def get_course(course_id: int) -> Optional[dict]:
    with connect() as c:
        r = c.execute(
            "SELECT c.*, u.full_name AS instructor_name FROM courses c "
            "LEFT JOIN users u ON u.id=c.instructor_id WHERE c.id=?",
            (course_id,),
        ).fetchone()
    return dict(r) if r else None


def create_course(code: str, title: str, instructor_id: int, day: str,
                  start: int, end: int, capacity: int, semester: int) -> int:
    with connect() as c:
        cur = c.execute(
            """
            INSERT INTO courses (code, title, instructor_id, day, start_hour, end_hour, capacity, semester)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (code, title, instructor_id, day, start, end, capacity, semester),
        )
        c.commit()
        return cur.lastrowid


def cancel_course(course_id: int) -> None:
    with connect() as c:
        c.execute("UPDATE courses SET status='cancelled' WHERE id=?", (course_id,))
        c.commit()


# ---------- enrollments ----------

def student_enrollments(student_id: int, semester: Optional[int] = None,
                        statuses: Optional[Iterable[str]] = None) -> list[dict]:
    q = (
        "SELECT e.*, c.code, c.title, c.day, c.start_hour, c.end_hour, c.status AS course_status, "
        "u.full_name AS instructor_name "
        "FROM enrollments e JOIN courses c ON c.id=e.course_id "
        "LEFT JOIN users u ON u.id=c.instructor_id WHERE e.student_id=?"
    )
    args: list = [student_id]
    if semester is not None:
        q += " AND e.semester=?"
        args.append(semester)
    if statuses:
        marks = ",".join("?" * len(list(statuses)))
        q += f" AND e.status IN ({marks})"
        args.extend(list(statuses))
    q += " ORDER BY c.code"
    with connect() as c:
        rows = c.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def course_enrollments(course_id: int, statuses: Optional[Iterable[str]] = None) -> list[dict]:
    q = (
        "SELECT e.*, u.full_name, u.id AS student_user_id FROM enrollments e "
        "JOIN users u ON u.id=e.student_id WHERE e.course_id=?"
    )
    args: list = [course_id]
    if statuses:
        marks = ",".join("?" * len(list(statuses)))
        q += f" AND e.status IN ({marks})"
        args.extend(list(statuses))
    q += " ORDER BY u.full_name"
    with connect() as c:
        rows = c.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def enroll(student_id: int, course_id: int, status: str, semester: int) -> None:
    with connect() as c:
        c.execute(
            "INSERT OR IGNORE INTO enrollments (student_id, course_id, status, semester) VALUES (?,?,?,?)",
            (student_id, course_id, status, semester),
        )
        c.commit()


def update_enrollment_status(enrollment_id: int, status: str) -> None:
    with connect() as c:
        c.execute("UPDATE enrollments SET status=? WHERE id=?", (status, enrollment_id))
        c.commit()


def drop_enrollment(enrollment_id: int) -> None:
    with connect() as c:
        c.execute("DELETE FROM enrollments WHERE id=?", (enrollment_id,))
        c.commit()


def set_grade(enrollment_id: int, grade: str) -> None:
    status = "failed" if grade == "F" else "completed"
    with connect() as c:
        c.execute(
            "UPDATE enrollments SET grade=?, status=? WHERE id=?",
            (grade, status, enrollment_id),
        )
        c.commit()


def student_history(student_id: int) -> list[dict]:
    with connect() as c:
        rows = c.execute(
            """
            SELECT e.*, c.code, c.title FROM enrollments e
            JOIN courses c ON c.id=e.course_id
            WHERE e.student_id=? AND e.status IN ('completed','failed')
            ORDER BY e.semester, c.code
            """,
            (student_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def has_failed_course(student_id: int, course_code: str) -> bool:
    with connect() as c:
        r = c.execute(
            """
            SELECT 1 FROM enrollments e JOIN courses c ON c.id=e.course_id
            WHERE e.student_id=? AND c.code=? AND e.status='failed' LIMIT 1
            """,
            (student_id, course_code),
        ).fetchone()
    return r is not None


def has_passed_course(student_id: int, course_code: str) -> bool:
    with connect() as c:
        r = c.execute(
            """
            SELECT 1 FROM enrollments e JOIN courses c ON c.id=e.course_id
            WHERE e.student_id=? AND c.code=? AND e.status='completed' AND e.grade<>'F' LIMIT 1
            """,
            (student_id, course_code),
        ).fetchone()
    return r is not None


def fail_count(student_id: int, course_code: str) -> int:
    with connect() as c:
        r = c.execute(
            """
            SELECT COUNT(*) FROM enrollments e JOIN courses c ON c.id=e.course_id
            WHERE e.student_id=? AND c.code=? AND e.status='failed'
            """,
            (student_id, course_code),
        ).fetchone()
    return r[0] or 0


# ---------- reviews ----------

def add_review(student_id: int, course_id: int, stars: int, body: str, visible: int) -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO reviews (student_id, course_id, stars, body, visible) VALUES (?,?,?,?,?)",
            (student_id, course_id, stars, body, visible),
        )
        c.commit()
        return cur.lastrowid


def reviews_for_course(course_id: int, include_hidden: bool = False) -> list[dict]:
    with connect() as c:
        if include_hidden:
            rows = c.execute(
                """
                SELECT r.*, u.full_name FROM reviews r
                JOIN users u ON u.id=r.student_id
                WHERE r.course_id=? ORDER BY r.id DESC
                """,
                (course_id,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM reviews WHERE course_id=? AND visible=1 ORDER BY id DESC",
                (course_id,),
            ).fetchall()
    return [dict(r) for r in rows]


def avg_rating(course_id: int) -> Optional[float]:
    with connect() as c:
        r = c.execute(
            "SELECT AVG(stars) FROM reviews WHERE course_id=? AND visible=1",
            (course_id,),
        ).fetchone()
    return r[0]


def top_rated_courses(limit: int = 3) -> list[dict]:
    with connect() as c:
        rows = c.execute(
            """
            SELECT c.id, c.code, c.title, ROUND(AVG(r.stars), 2) AS avg_stars,
                   COUNT(r.id) AS n_reviews
              FROM courses c
              JOIN reviews r ON r.course_id=c.id AND r.visible=1
             GROUP BY c.id
            HAVING n_reviews > 0
             ORDER BY avg_stars DESC, n_reviews DESC
             LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def bottom_rated_courses(limit: int = 3) -> list[dict]:
    with connect() as c:
        rows = c.execute(
            """
            SELECT c.id, c.code, c.title, ROUND(AVG(r.stars), 2) AS avg_stars,
                   COUNT(r.id) AS n_reviews
              FROM courses c
              JOIN reviews r ON r.course_id=c.id AND r.visible=1
             GROUP BY c.id
            HAVING n_reviews > 0
             ORDER BY avg_stars ASC, n_reviews DESC
             LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def top_gpa_students(limit: int = 5) -> list[dict]:
    with connect() as c:
        rows = c.execute(
            """
            SELECT u.full_name, s.gpa
              FROM users u JOIN students s ON s.user_id=u.id
             WHERE u.status='active' AND s.gpa > 0
             ORDER BY s.gpa DESC, u.full_name
             LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------- taboo ----------

def list_taboo_words() -> list[str]:
    with connect() as c:
        rows = c.execute("SELECT word FROM taboo_words ORDER BY word").fetchall()
    return [r["word"] for r in rows]


def add_taboo_word(word: str) -> None:
    with connect() as c:
        c.execute("INSERT OR IGNORE INTO taboo_words (word) VALUES (?)", (word.lower().strip(),))
        c.commit()


def remove_taboo_word(word: str) -> None:
    with connect() as c:
        c.execute("DELETE FROM taboo_words WHERE word=?", (word.lower().strip(),))
        c.commit()


# ---------- complaints ----------

def add_complaint(from_user_id: int, against_user_id: Optional[int],
                  against_role: str, body: str) -> int:
    with connect() as c:
        cur = c.execute(
            """
            INSERT INTO complaints (from_user_id, against_user_id, against_role, body)
            VALUES (?,?,?,?)
            """,
            (from_user_id, against_user_id, against_role, body),
        )
        c.commit()
        return cur.lastrowid


def list_complaints(status: Optional[str] = None) -> list[dict]:
    q = (
        "SELECT cmp.*, uf.full_name AS from_name, ua.full_name AS against_name "
        "FROM complaints cmp "
        "JOIN users uf ON uf.id=cmp.from_user_id "
        "LEFT JOIN users ua ON ua.id=cmp.against_user_id"
    )
    args: list = []
    if status:
        q += " WHERE cmp.status=?"
        args.append(status)
    q += " ORDER BY cmp.id DESC"
    with connect() as c:
        rows = c.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def resolve_complaint(cid: int, action: str) -> None:
    with connect() as c:
        c.execute(
            "UPDATE complaints SET status='resolved', action=? WHERE id=?",
            (action, cid),
        )
        c.commit()


# ---------- graduation ----------

def submit_graduation(student_id: int) -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO graduation_apps (student_id) VALUES (?)", (student_id,)
        )
        c.commit()
        return cur.lastrowid


def list_graduation_apps(status: Optional[str] = None) -> list[dict]:
    q = (
        "SELECT g.*, u.full_name FROM graduation_apps g "
        "JOIN users u ON u.id=g.student_id"
    )
    args: list = []
    if status:
        q += " WHERE g.status=?"
        args.append(status)
    q += " ORDER BY g.id DESC"
    with connect() as c:
        rows = c.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def decide_graduation(gid: int, status: str, note: str) -> None:
    with connect() as c:
        c.execute(
            "UPDATE graduation_apps SET status=?, note=? WHERE id=?",
            (status, note, gid),
        )
        c.commit()


# ---------- settings ----------

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with connect() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(key: str, value: str) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO settings (key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        c.commit()
