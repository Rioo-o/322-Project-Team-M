"""Seed demo data.

Re-running this on an existing DB is a no-op (uses INSERT OR IGNORE
or checks first).
"""
from __future__ import annotations

from .db import connect
from . import models, ai, rules


def _insert_user(username: str, password: str, role: str, full_name: str,
                 must_change_pw: int = 0, is_new: int = 0) -> int:
    with connect() as c:
        r = c.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if r:
            return r["id"]
        cur = c.execute(
            """
            INSERT INTO users (username, password, role, full_name, must_change_pw, is_new)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username, password, role, full_name, must_change_pw, is_new),
        )
        c.commit()
        return cur.lastrowid


def seed_all() -> None:
    # Registrar
    reg_id = _insert_user("registrar", "admin", "registrar", "Reggie Strarsen")

    # Instructors
    inst_adams = _insert_user("prof_adams", "password", "instructor", "Prof. Adams")
    inst_brown = _insert_user("prof_brown", "password", "instructor", "Prof. Brown")
    inst_chen = _insert_user("prof_chen", "password", "instructor", "Prof. Chen")
    inst_diaz = _insert_user("prof_diaz", "password", "instructor", "Prof. Diaz")
    with connect() as c:
        for uid in (inst_adams, inst_brown, inst_chen, inst_diaz):
            c.execute("INSERT OR IGNORE INTO instructors (user_id) VALUES (?)", (uid,))
        c.commit()

    # Students  (10 total to satisfy "~10")
    students = [
        ("alice", "Alice Johnson", 3.6),
        ("bob", "Bob Martinez", 2.9),
        ("carol", "Carol Singh", 3.8),
        ("dan", "Dan Kowalski", 3.1),
        ("eve", "Eve Tanaka", 3.95),
        ("frank", "Frank Müller", 2.4),
        ("grace", "Grace O'Neil", 3.4),
        ("hank", "Hank Patel", 2.2),
        ("ivy", "Ivy Robinson", 3.7),
        ("jay", "Jay Park", 3.0),
    ]
    student_ids: dict[str, int] = {}
    for uname, name, gpa in students:
        uid = _insert_user(uname, "password", "student", name)
        student_ids[uname] = uid
        with connect() as c:
            r = c.execute("SELECT 1 FROM students WHERE user_id=?", (uid,)).fetchone()
            if not r:
                c.execute(
                    "INSERT INTO students (user_id, gpa, courses_completed, semesters_completed) VALUES (?,?,?,?)",
                    (uid, gpa, 4, 1),
                )
                c.commit()

    # A brand-new student to demo first-login flow
    new_grad_id = _insert_user("new_grad", "welcome", "student", "Nina Newman",
                                must_change_pw=1, is_new=1)
    with connect() as c:
        r = c.execute("SELECT 1 FROM students WHERE user_id=?", (new_grad_id,)).fetchone()
        if not r:
            c.execute("INSERT INTO students (user_id) VALUES (?)", (new_grad_id,))
            c.commit()

    # Courses - semester 1 = current
    course_specs = [
        ("CS501", "Intro to Programming", inst_adams, "Mon", 10, 12, 4, 1),
        ("CS510", "Data Structures",      inst_brown, "Tue", 13, 15, 4, 1),
        ("CS520", "Algorithms",           inst_adams, "Wed", 10, 12, 4, 1),
        ("CS530", "Databases",            inst_chen,  "Thu", 9, 11, 4, 1),
        ("CS540", "Artificial Intelligence", inst_diaz, "Mon", 13, 15, 3, 1),
        ("CS550", "Software Engineering", inst_chen,  "Fri", 10, 12, 3, 1),
    ]
    course_ids: dict[str, int] = {}
    with connect() as c:
        for code, title, inst_id, day, sh, eh, cap, sem in course_specs:
            r = c.execute("SELECT id FROM courses WHERE code=? AND semester=?",
                          (code, sem)).fetchone()
            if r:
                course_ids[code] = r["id"]
                continue
            cur = c.execute(
                """
                INSERT INTO courses (code, title, instructor_id, day, start_hour, end_hour, capacity, semester)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (code, title, inst_id, day, sh, eh, cap, sem),
            )
            course_ids[code] = cur.lastrowid
        c.commit()

    # Historical (semester 0) enrollments + grades so reviews/GPAs/honors have data.
    # Note: alice intentionally has NO CS501 in her history so she can demo the
    # waitlist for the currently-full CS501. Bob has an F in CS510 for the retake demo.
    # Eve and Carol have 8-course histories so the graduation flow can be approved.
    history = [
        ("alice", [("CS510", "B+"), ("CS520", "A-"), ("CS530", "A-"), ("CS540", "B")]),
        ("bob",   [("CS501", "C"),  ("CS510", "F"),  ("CS530", "C+"), ("CS540", "B-")]),
        ("carol", [("CS501", "A"),  ("CS510", "A-"), ("CS520", "A"),  ("CS530", "A-"),
                   ("CS540", "A-"), ("CS550", "A"),  ("CS560", "A-"), ("CS570", "A")]),
        ("dan",   [("CS501", "B"),  ("CS510", "B+"), ("CS520", "C+"), ("CS530", "B")]),
        ("eve",   [("CS501", "A"),  ("CS510", "A"),  ("CS520", "A"),  ("CS530", "A"),
                   ("CS540", "A"),  ("CS550", "A"),  ("CS560", "A"),  ("CS570", "A")]),
        ("frank", [("CS501", "C"),  ("CS510", "D"),  ("CS530", "C-"), ("CS550", "C+")]),
        ("grace", [("CS501", "B+"), ("CS530", "A-"), ("CS540", "B"),  ("CS550", "B+")]),
        ("hank",  [("CS501", "D"),  ("CS510", "C-"), ("CS530", "C-"), ("CS540", "D+")]),
        ("ivy",   [("CS501", "A-"), ("CS520", "A"),  ("CS540", "A-"), ("CS550", "B+")]),
        ("jay",   [("CS501", "B"),  ("CS510", "B"),  ("CS530", "B"),  ("CS550", "C+")]),
    ]
    # Historic-only courses to support 8-course graduation history.
    historic_only = [
        ("CS560", "Operating Systems", inst_chen, "Tue", 9, 11, 6, 0),
        ("CS570", "Computer Networks", inst_brown, "Wed", 13, 15, 6, 0),
    ]
    # Use semester=0 (prior semester) for the historical record + a few historic courses.
    historic_courses = ["CS501", "CS510", "CS520", "CS530", "CS540", "CS550"]
    with connect() as c:
        for code in historic_courses:
            r = c.execute("SELECT id FROM courses WHERE code=? AND semester=0",
                          (code,)).fetchone()
            if r:
                continue
            # Copy semester-1 layout for historic semester=0.
            base = c.execute("SELECT * FROM courses WHERE code=? AND semester=1",
                             (code,)).fetchone()
            c.execute(
                """
                INSERT INTO courses (code, title, instructor_id, day, start_hour, end_hour, capacity, semester, status)
                VALUES (?,?,?,?,?,?,?,?, 'active')
                """,
                (base["code"], base["title"], base["instructor_id"],
                 base["day"], base["start_hour"], base["end_hour"], base["capacity"], 0),
            )
        # Add CS560/CS570 historic electives.
        for code, title, inst_id, day, sh, eh, cap, sem in historic_only:
            r = c.execute("SELECT id FROM courses WHERE code=? AND semester=?",
                          (code, sem)).fetchone()
            if r:
                continue
            c.execute(
                """
                INSERT INTO courses (code, title, instructor_id, day, start_hour, end_hour, capacity, semester)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (code, title, inst_id, day, sh, eh, cap, sem),
            )
        c.commit()

        # Insert historical enrollments.
        for uname, items in history:
            sid = student_ids[uname]
            for code, grade in items:
                course_row = c.execute(
                    "SELECT id FROM courses WHERE code=? AND semester=0", (code,)
                ).fetchone()
                if not course_row:
                    continue
                cid = course_row["id"]
                status = "failed" if grade == "F" else "completed"
                c.execute(
                    """
                    INSERT OR IGNORE INTO enrollments
                       (student_id, course_id, status, grade, semester)
                    VALUES (?,?,?,?,?)
                    """,
                    (sid, cid, status, grade, 0),
                )
        c.commit()

    # Recompute GPAs from this historical data.
    for uname in student_ids:
        rules.recompute_student_gpa(student_ids[uname])

    # Seed a few visible reviews so Home looks alive.
    review_specs = [
        ("alice", "CS501", 5, "Great intro. Adams is friendly and clear."),
        ("carol", "CS501", 4, "Solid foundation, projects were fun."),
        ("dan",   "CS501", 5, "Loved it. Best course this year."),
        ("eve",   "CS510", 5, "Tough but rewarding. Highly recommended."),
        ("ivy",   "CS520", 5, "Adams again - excellent."),
        ("frank", "CS540", 2, "Material was confusing and disorganized."),
        ("hank",  "CS540", 1, "Lectures were unhelpful, slides were sparse."),
        ("grace", "CS530", 4, "Liked it. Good labs."),
        ("jay",   "CS550", 3, "Average. Demos could be tighter."),
        ("bob",   "CS510", 2, "Lost me halfway through."),
    ]
    # Use a "semester 0" course id so we can review historic classes.
    with connect() as c:
        for uname, code, stars, body in review_specs:
            sid = student_ids[uname]
            cr = c.execute("SELECT id FROM courses WHERE code=? AND semester=0", (code,)).fetchone()
            if not cr:
                continue
            cid = cr["id"]
            exists = c.execute(
                "SELECT 1 FROM reviews WHERE student_id=? AND course_id=?", (sid, cid)
            ).fetchone()
            if exists:
                continue
            c.execute(
                "INSERT INTO reviews (student_id, course_id, stars, body, visible) VALUES (?,?,?,?,1)",
                (sid, cid, stars, body),
            )
        c.commit()

    # Pre-enroll a handful of students in the CURRENT semester so the demo can
    # show:
    #  - CS501 already full -> Alice gets waitlisted
    #  - CS510/CS520 have room for Alice to enroll cleanly
    #  - CS540 under-enrolled, CS550 empty -> both cancelled when phase advances
    #  - prof_diaz teaches only CS540, so they will be auto-suspended on that sweep
    current_sem_enrol = {
        "CS501": ["carol", "dan", "eve", "ivy"],   # full
        "CS510": ["carol", "dan", "grace"],         # 3 -> survives
        "CS520": ["eve", "ivy", "jay"],             # 3 -> survives
        "CS530": ["carol", "dan", "eve", "ivy"],    # full
        "CS540": ["bob"],                           # 1 -> will cancel
        "CS550": [],                                # 0 -> will cancel
    }
    with connect() as c:
        for code, unames in current_sem_enrol.items():
            cr = c.execute("SELECT id FROM courses WHERE code=? AND semester=1",
                            (code,)).fetchone()
            if not cr:
                continue
            cid = cr["id"]
            for un in unames:
                sid = student_ids.get(un)
                if not sid:
                    continue
                c.execute(
                    "INSERT OR IGNORE INTO enrollments (student_id, course_id, status, semester) "
                    "VALUES (?,?, 'enrolled', 1)",
                    (sid, cid),
                )
        c.commit()

    # Default taboo words.
    for w in ("stupid", "idiot", "dumb", "trash", "garbage"):
        models.add_taboo_word(w)

    # A sample pending application for demo (visitor wants to be a student).
    with connect() as c:
        r = c.execute("SELECT 1 FROM applications WHERE full_name='Pending Sample'").fetchone()
        if not r:
            c.execute(
                "INSERT INTO applications (apply_type, full_name, gpa, note) "
                "VALUES ('student', 'Pending Sample', 3.4, 'Excited to join College0.')"
            )
            c.commit()

    # AI corpus.
    ai.seed_corpus()
