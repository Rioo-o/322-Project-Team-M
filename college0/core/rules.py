"""Business rules.

Anything that automatically *changes* the world (warnings, suspensions,
GPA recomputes, course cancellations, etc.) lives here. The UI just
calls these helpers; this module decides what happens.
"""
from __future__ import annotations

import re
from typing import Iterable

from . import models
from .db import connect
from .models import GRADE_POINTS


# -----------------------------
# Applications
# -----------------------------

def auto_decision_for_student_app(gpa: float) -> tuple[str, str]:
    """Return ``(status, decision_note)`` for an incoming student application.

    Auto rule: GPA ≥ 3.0 and the student quota isn't full → accepted.
    Otherwise rejected. The registrar can still override the result by
    hand (which the UI requires a justification for).
    """
    quota = int(models.get_setting("student_quota", "20"))
    enrolled = sum(1 for u in models.list_users("student") if u["status"] == "active")
    if gpa is None:
        return "rejected", "No GPA provided."
    if enrolled >= quota:
        return "rejected", f"Student quota ({quota}) already reached."
    if gpa >= 3.0:
        return "accepted", "Auto-accepted: GPA >= 3.0 and quota available."
    return "rejected", f"Auto-rejected: GPA {gpa:.2f} below 3.0 threshold."


# -----------------------------
# Taboo word filtering
# -----------------------------

def filter_review_text(text: str, taboo: Iterable[str]) -> tuple[str, int]:
    """Return (masked_text, hit_count). Whole-word, case-insensitive."""
    hits = 0
    out = text
    for w in taboo:
        pattern = re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE)
        def _mask(m, ww=w):
            return "*" * len(ww)
        out, n = pattern.subn(_mask, out)
        hits += n
    return out, hits


def process_review(student_id: int, course_id: int, stars: int, raw_text: str) -> dict:
    """Run the taboo-word check on a review and apply the consequences.

    1 or 2 hits → review is posted with those words masked + 1 warning.
    3+ hits → review is hidden from public/student views + 2 warnings.
    Returns a small summary the UI can show the student.
    """
    taboo = models.list_taboo_words()
    masked, hits = filter_review_text(raw_text, taboo)

    if hits >= 3:
        models.add_review(student_id, course_id, stars, masked, visible=0)
        warn_count_increment(student_id, "Review hidden: >=3 taboo words", times=2)
        return {
            "outcome": "hidden",
            "hits": hits,
            "masked": masked,
            "message": (
                f"Your review was HIDDEN because it contained {hits} taboo words. "
                "You received 2 warnings."
            ),
        }
    if hits >= 1:
        models.add_review(student_id, course_id, stars, masked, visible=1)
        warn_count_increment(student_id, "Review masked: 1-2 taboo words", times=1)
        return {
            "outcome": "masked",
            "hits": hits,
            "masked": masked,
            "message": (
                f"Your review was posted but {hits} taboo word(s) were masked. "
                "You received 1 warning."
            ),
        }
    models.add_review(student_id, course_id, stars, raw_text, visible=1)
    return {"outcome": "ok", "hits": 0, "masked": raw_text,
            "message": "Review posted."}


# -----------------------------
# Warnings / suspension / honors
# -----------------------------

def warn_count_increment(user_id: int, reason: str, times: int = 1) -> dict:
    """Add ``times`` warnings to a user and fire the 3-strike consequence.

    Hitting 3 cumulative warnings suspends the user (students also get a
    $100 fine; instructors don't). Returns a summary so callers can log
    "warned" vs. "suspended" appropriately.
    """
    total = 0
    for _ in range(times):
        total = models.warn_user(user_id, reason)
    user = models.get_user(user_id)
    state = models.get_semester_state()
    consequence = "warned"
    if total >= 3:
        if user["role"] == "student":
            models.suspend_user(user_id, until_semester=state["semester"] + 1, fine=100.0)
            consequence = "suspended"
        elif user["role"] == "instructor":
            # Out for the next semester; no fine.
            models.suspend_user(user_id, until_semester=state["semester"] + 1, fine=0.0)
            consequence = "suspended"
    return {"total_warnings": total, "consequence": consequence}


# -----------------------------
# Phase transition rules
# -----------------------------

def advance_phase(target: str) -> dict:
    """Move the semester to ``target`` and run any rules that fire on entry.

    Returns ``{"events": [...]}`` — a human-readable log the UI panel can
    display so users can actually see the automatic stuff happen.
    """
    state = models.get_semester_state()
    current = state["phase"]
    semester = state["semester"]
    events: list[str] = []

    # Phase order: setup → registration → running → grading → setup (next sem)
    if target not in {"setup", "registration", "running", "grading"}:
        return {"error": f"Unknown phase {target}"}

    # Entering "running": cancel under-enrolled courses and warn anyone
    # who didn't pick enough classes.
    if target == "running" and current != "running":
        cancelled = _cancel_underenrolled(semester)
        events += cancelled["events"]
        # Students with fewer than 2 enrollments earn a warning. We go
        # through warn_count_increment so the 3-strike rule applies here
        # too, not just to taboo-word offenses.
        for s in models.list_students():
            if s["status"] != "active":
                continue
            n = len([e for e in models.student_enrollments(s["id"], semester=semester,
                                                           statuses=["enrolled"])])
            if n < 2:
                res = warn_count_increment(
                    s["id"], f"Has only {n} course(s) at semester start.")
                tail = " → SUSPENDED" if res["consequence"] == "suspended" else ""
                events.append(
                    f"Student warned ({s['full_name']}): only {n} course(s){tail}.")
        # Show "one more chance" recipients in the event log.
        affected = models.list_special_reg_students()
        if affected:
            names = ", ".join(a["full_name"] for a in affected)
            events.append(
                "Special registration window OPEN (one more chance) for: " + names
            )

    # Entering "grading": shut the "one more chance" window down.
    if target == "grading" and current != "grading":
        cleared = models.clear_all_special_reg()
        if cleared:
            events.append(
                f"Special registration window CLOSED ({cleared} student(s) "
                "no longer eligible for re-registration)."
            )

    models.set_phase(target)
    return {"events": events}


def _cancel_underenrolled(semester: int) -> dict:
    """Cancel any course with fewer than 3 students, warn its instructor,
    and open the "one more chance" window for its enrolled students.

    Instructors who end up losing *every* class they were teaching get
    suspended for the next semester on top of the warning.
    """
    events: list[str] = []
    courses = models.list_courses(semester=semester, only_active=True)
    instructors_affected: dict[int, dict] = {}
    for c in courses:
        enrolled = models.course_enrollments(c["id"], statuses=["enrolled"])
        if len(enrolled) < 3:
            models.cancel_course(c["id"])
            events.append(f"Course {c['code']} cancelled ({len(enrolled)} enrolled).")
            inst_id = c["instructor_id"]
            if inst_id:
                # Funnel through warn_count_increment so cancelled-course
                # warnings count toward the 3-strike suspension threshold.
                res = warn_count_increment(
                    inst_id, f"Course {c['code']} cancelled (low enrollment).")
                if res["consequence"] == "suspended":
                    events.append(
                        f"Instructor of {c['code']} reached 3 warnings → SUSPENDED.")
                inst_state = instructors_affected.setdefault(inst_id,
                                                             {"cancelled": 0, "total": 0})
                inst_state["cancelled"] += 1
            # Drop the students from the cancelled course and flag them
            # for the "one more chance" re-registration window.
            for e in enrolled:
                models.update_enrollment_status(e["id"], "dropped")
                models.set_special_reg(e["student_id"], 1)

    # Catch instructors who lost every single one of their classes.
    for inst_id in instructors_affected:
        all_courses = [c for c in models.list_courses(semester=semester)
                       if c["instructor_id"] == inst_id]
        if all_courses and all(c["status"] == "cancelled" for c in all_courses):
            state = models.get_semester_state()
            models.suspend_user(inst_id,
                                until_semester=state["semester"] + 1, fine=0.0)
            events.append(f"Instructor user_id={inst_id} suspended (all classes cancelled).")
    return {"events": events}


# -----------------------------
# Grading / end-of-semester
# -----------------------------

def recompute_student_gpa(student_id: int) -> dict:
    """Recalculate a student's overall + current-semester GPA from scratch.

    Walks every completed / failed enrollment, averages the grade points,
    writes the result back to the ``students`` row, and returns the
    metrics so the caller can act on them (e.g. honor-roll detection).
    """
    with connect() as c:
        rows = c.execute(
            """
            SELECT e.grade, e.semester FROM enrollments e
            WHERE e.student_id=? AND e.status IN ('completed','failed') AND e.grade IS NOT NULL
            """,
            (student_id,),
        ).fetchall()
    points = [GRADE_POINTS.get(r["grade"], 0) for r in rows]
    if not points:
        overall = 0.0
    else:
        overall = sum(points) / len(points)

    state = models.get_semester_state()
    sem_rows = [r for r in rows if r["semester"] == state["semester"]]
    sem_points = [GRADE_POINTS.get(r["grade"], 0) for r in sem_rows]
    semester_gpa = (sum(sem_points) / len(sem_points)) if sem_points else 0.0

    courses_completed = sum(1 for r in rows if r["grade"] != "F")
    with connect() as c:
        c.execute(
            """
            UPDATE students
               SET gpa=?, semester_gpa=?, courses_completed=?
             WHERE user_id=?
            """,
            (round(overall, 2), round(semester_gpa, 2), courses_completed, student_id),
        )
        c.commit()
    return {"gpa": round(overall, 2), "semester_gpa": round(semester_gpa, 2),
            "courses_completed": courses_completed}


def end_of_grading_sweep() -> list[str]:
    """End-of-semester housekeeping.

    Called once when the registrar advances out of grading. Runs every
    "did anything bad happen this term?" check in one pass: missing
    grades, out-of-band class GPAs, low student GPAs, honor roll,
    average-rating warnings, etc. Returns a list of human-readable
    events for the UI to show.
    """
    events: list[str] = []
    state = models.get_semester_state()
    semester = state["semester"]

    # Instructors with ungraded students get a warning.
    for inst in models.list_instructors():
        if inst["status"] != "active":
            continue
        missing = 0
        my_courses = [c for c in models.list_courses(semester=semester, only_active=True)
                      if c["instructor_id"] == inst["id"]]
        for c in my_courses:
            for e in models.course_enrollments(c["id"], statuses=["enrolled"]):
                if not e["grade"]:
                    missing += 1
        if missing:
            warn_count_increment(inst["id"],
                                 f"{missing} students ungraded.", times=1)
            events.append(f"Instructor {inst['full_name']} warned for {missing} missing grade(s).")

    # Flag any class whose average GPA looks suspiciously high or low —
    # the registrar reviews these by hand.
    flag_messages = []
    for inst in models.list_instructors():
        my_courses = [c for c in models.list_courses(semester=semester, only_active=True)
                      if c["instructor_id"] == inst["id"]]
        all_grades: list[float] = []
        for c in my_courses:
            for e in models.course_enrollments(c["id"], statuses=["completed", "failed"]):
                if e["grade"]:
                    all_grades.append(GRADE_POINTS.get(e["grade"], 0))
        if all_grades:
            class_gpa = sum(all_grades) / len(all_grades)
            if class_gpa > 3.5 or class_gpa < 2.5:
                flag_messages.append(
                    f"Instructor {inst['full_name']}: class GPA {class_gpa:.2f} "
                    f"({'high' if class_gpa>3.5 else 'low'}). Registrar review required."
                )
    if flag_messages:
        models.set_setting("instructor_review_flags", "\n".join(flag_messages))
        events.extend(flag_messages)
    else:
        models.set_setting("instructor_review_flags", "")

    # Per-student GPA outcomes for the semester just finished.
    for s in models.list_students():
        if s["status"] != "active":
            continue
        metrics = recompute_student_gpa(s["id"])
        gpa = metrics["gpa"]
        sem_gpa = metrics["semester_gpa"]

        # Hard stop: overall GPA below 2.0 → terminate.
        if gpa < 2.0 and metrics["courses_completed"] >= 1:
            models.set_status(s["id"], "terminated")
            events.append(f"Student {s['full_name']} TERMINATED (GPA {gpa}).")
            continue
        # Hard stop: failed the same course twice → terminate.
        with connect() as c:
            row = c.execute(
                """
                SELECT c.code, COUNT(*) AS fails FROM enrollments e
                JOIN courses c ON c.id=e.course_id
                WHERE e.student_id=? AND e.status='failed'
                GROUP BY c.code HAVING fails >= 2
                """,
                (s["id"],),
            ).fetchone()
        if row:
            models.set_status(s["id"], "terminated")
            events.append(
                f"Student {s['full_name']} TERMINATED (failed {row['code']} twice).")
            continue

        # Borderline GPA (2.0–2.25): warn and require an interview.
        if 2.0 <= gpa <= 2.25 and metrics["courses_completed"] >= 1:
            warn_count_increment(s["id"], f"GPA {gpa} - interview required.")
            events.append(f"Student {s['full_name']} warned; interview required.")

        # Honor-roll check: either a strong semester or strong overall GPA
        # (overall version only kicks in once the student has at least one
        # full semester under their belt).
        with connect() as c:
            sem_done = c.execute(
                "SELECT semesters_completed FROM students WHERE user_id=?",
                (s["id"],),
            ).fetchone()[0]
        is_honor = False
        if sem_gpa >= 3.75:
            is_honor = True
            events.append(f"Honor roll: {s['full_name']} (semester GPA {sem_gpa}).")
        if sem_done >= 1 and gpa >= 3.5:
            is_honor = True
            events.append(f"Honor roll: {s['full_name']} (overall GPA {gpa}).")
        if is_honor:
            with connect() as c:
                c.execute(
                    "UPDATE students SET honors=honors+1 WHERE user_id=?", (s["id"],))
                c.commit()

    # Tick up the semester counter for everyone who's still active.
    with connect() as c:
        c.execute("""
            UPDATE students
               SET semesters_completed = semesters_completed + 1
             WHERE user_id IN (SELECT id FROM users WHERE status='active' AND role='student')
        """)
        c.commit()

    # Classes whose average review rating dipped below 2 → instructor warned.
    with connect() as c:
        rows = c.execute(
            """
            SELECT c.id, c.code, c.instructor_id, ROUND(AVG(r.stars),2) AS avg_stars,
                   COUNT(r.id) AS n
              FROM courses c JOIN reviews r ON r.course_id=c.id AND r.visible=1
             WHERE c.semester=?
             GROUP BY c.id
            """,
            (semester,),
        ).fetchall()
    for r in rows:
        if r["n"] >= 1 and r["avg_stars"] is not None and r["avg_stars"] < 2 and r["instructor_id"]:
            warn_count_increment(r["instructor_id"],
                                 f"Course {r['code']} avg rating {r['avg_stars']} (<2).")
            events.append(f"Instructor of {r['code']} warned (avg rating {r['avg_stars']}).")

    return events


# -----------------------------
# Registration validation
# -----------------------------

def try_register(student_id: int, course_id: int) -> dict:
    """Validate everything and put the student on the course (or its waitlist).

    Returns ``{"ok": bool, "msg": str, ...}``. Failure modes covered: bad
    phase, inactive student, missing course, double-enrollment, retake of
    an already-passed course, hitting the 4-course cap, time conflict,
    and finally capacity (which falls through to waitlist).
    """
    state = models.get_semester_state()
    user = models.get_user(student_id)
    if not user or user["status"] != "active":
        return {"ok": False, "msg": "Inactive student."}
    # Registration is normally only open during the REGISTRATION phase,
    # but students whose course was just cancelled get a private "one
    # more chance" window during RUNNING (via the special_reg_open flag).
    if state["phase"] == "registration":
        pass
    elif state["phase"] == "running" and models.get_special_reg(student_id):
        pass
    else:
        return {"ok": False, "msg": "Registration is closed in this phase."}

    target = models.get_course(course_id)
    if not target or target["status"] != "active":
        return {"ok": False, "msg": "Course not available."}
    if target["semester"] != state["semester"]:
        return {"ok": False, "msg": "Course is not in the current semester."}

    # Already enrolled or already on the waitlist for this course?
    current = models.student_enrollments(student_id, semester=state["semester"],
                                         statuses=["enrolled", "waitlist"])
    if any(e["course_id"] == course_id for e in current):
        return {"ok": False, "msg": "You are already on this course's roster."}

    # Already passed this course before — retakes are only allowed after an F.
    if models.has_passed_course(student_id, target["code"]):
        return {"ok": False, "msg": "You already passed this course; cannot retake."}

    # Hard cap of 4 enrolled courses per semester.
    enrolled_now = [e for e in current if e["status"] == "enrolled"]
    if len(enrolled_now) >= 4:
        return {"ok": False, "msg": "You already have 4 enrolled courses (the max)."}

    # Same day + overlapping hours with anything we're already taking?
    for e in enrolled_now:
        if e["day"] == target["day"] and not (
                e["end_hour"] <= target["start_hour"]
                or target["end_hour"] <= e["start_hour"]):
            return {"ok": False,
                    "msg": f"Time conflict with {e['code']} ({e['day']} {e['start_hour']}-{e['end_hour']})."}

    # Last gate: capacity. Full courses bump the student to the waitlist.
    confirmed = models.course_enrollments(course_id, statuses=["enrolled"])
    if len(confirmed) >= target["capacity"]:
        models.enroll(student_id, course_id, status="waitlist", semester=state["semester"])
        return {"ok": True, "waitlist": True,
                "msg": f"Course full ({target['capacity']}). Added to waitlist."}

    models.enroll(student_id, course_id, status="enrolled", semester=state["semester"])
    return {"ok": True, "waitlist": False, "msg": "Enrolled."}


# -----------------------------
# Graduation check
# -----------------------------

def check_graduation(student_id: int) -> dict:
    """Decide whether a student is eligible to apply for graduation.

    Our rule of thumb: at least 8 distinct non-failed completions, the
    core course (CS501), and at least one of the track courses
    (CS510 or CS520). The remaining four slots can be anything they've
    passed.
    """
    history = models.student_history(student_id)
    passed = [h for h in history if h["status"] == "completed" and h["grade"] != "F"]
    codes = {h["code"] for h in passed}
    needs_core = "CS501" not in codes
    needs_track = not ({"CS510", "CS520"} & codes)
    if len(passed) < 8:
        return {"ok": False, "msg": f"Only {len(passed)} completed courses; need 8."}
    if needs_core:
        return {"ok": False, "msg": "Missing required core course CS501."}
    if needs_track:
        return {"ok": False, "msg": "Missing track course (need CS510 or CS520)."}
    return {"ok": True, "msg": "All graduation requirements met."}
