"""Simplified AI question area.

- A small "vector DB" of canned Q&A scoped by user role.
- "Vector" search = bag-of-words Jaccard overlap (no external libs).
- If no local entry is good enough, a templated "LLM fallback" answer
  is returned with an explicit hallucination warning.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from . import models

STOP = {
    "the", "a", "an", "is", "are", "to", "of", "in", "on", "for",
    "what", "how", "where", "when", "who", "do", "does", "i", "my",
    "can", "and", "or", "this", "that", "be", "with", "about",
}


def _tokens(text: str) -> set[str]:
    return {w for w in re.split(r"\W+", text.lower()) if w and w not in STOP}


def _scope_for(user: Optional[dict], course_codes: Iterable[str] = ()) -> list[str]:
    scopes = ["general"]
    if not user:
        return scopes
    role = user["role"]
    if role == "student":
        scopes.append("student")
        for code in course_codes:
            scopes.append(f"course:{code}")
    elif role == "instructor":
        scopes.append("instructor")
        for code in course_codes:
            scopes.append(f"course:{code}")
    elif role == "registrar":
        scopes += ["student", "instructor"]
    return scopes


def ask(question: str, user: Optional[dict],
        course_codes: Iterable[str] = ()) -> dict:
    """Return {answer, source, score, scope, hallucination_warning?}."""
    scopes = _scope_for(user, course_codes)
    q_tokens = _tokens(question)

    from .db import connect
    with connect() as c:
        placeholder = ",".join(["?"] * len(scopes))
        rows = c.execute(
            f"SELECT * FROM qa_corpus WHERE scope IN ({placeholder})",
            list(scopes),
        ).fetchall()

    best = None
    best_score = 0.0
    for r in rows:
        q_kb = _tokens(r["question"])
        a_kb = _tokens(r["answer"])
        kb_all = q_kb | a_kb
        if not q_tokens or not kb_all:
            continue
        # Score = how many of the user's query terms appear in the KB entry
        # (gives weight to short, specific queries). Add a small Jaccard
        # tiebreaker so that overlapping-but-vague matches don't beat focused ones.
        coverage = len(q_tokens & kb_all) / len(q_tokens)
        # Bonus if the user's words specifically appear in the corpus *question*.
        q_match_bonus = len(q_tokens & q_kb) / max(len(q_kb), 1)
        score = coverage * 0.7 + q_match_bonus * 0.3
        if score > best_score:
            best_score = score
            best = r

    if best and best_score >= 0.35:
        return {
            "answer": best["answer"],
            "source": "local-kb",
            "score": round(best_score, 2),
            "matched_question": best["question"],
        }

    # Fallback: simulated LLM with hallucination warning.
    return {
        "answer": _simulated_llm(question, user),
        "source": "llm-fallback",
        "score": round(best_score, 2),
        "hallucination_warning": True,
    }


def _simulated_llm(question: str, user: Optional[dict]) -> str:
    role = (user["role"] if user else "visitor").capitalize()
    return (
        f"(LLM fallback to general model) I don't have specific College0 "
        f"information about: \"{question.strip()}\". A best-guess from a "
        f"general AI model would be: 'This appears to relate to college "
        f"operations or {role.lower()} workflows. Please confirm with the "
        f"registrar or your course materials.'\n\n"
        "WARNING: This answer is NOT grounded in College0's data and may be "
        "wrong (hallucinated). Treat as informational only."
    )


def seed_corpus() -> None:
    """Insert canned Q&A. Idempotent."""
    items: list[tuple[str, str, str]] = [
        ("general", "What is College0?",
         "College0 is a graduate program with a 4-phase semester: class set-up, "
         "course registration, class running, and grading."),
        ("general", "How do I apply to College0?",
         "From the Home page click 'Apply'. Choose Student or Instructor. "
         "Student applications with GPA >= 3.0 are auto-accepted if the quota allows."),
        ("general", "What courses are offered?",
         "Sample courses include CS501 Intro to Programming, CS510 Data Structures, "
         "CS520 Algorithms, CS530 Databases, CS540 AI, CS550 Software Engineering."),
        ("general", "How many courses must I take?",
         "Students must register for 2 to 4 courses per semester. Fewer than 2 "
         "earns a warning; more than 4 is not allowed."),
        ("general", "When is the registration window?",
         "Course registration is the 2nd of 4 semester phases. The registrar "
         "advances the system to that phase. Outside this window, registration is closed."),
        ("general", "What happens if a course has too few students?",
         "Courses with fewer than 3 students are cancelled. Their instructor "
         "receives a warning; if all of an instructor's courses are cancelled, "
         "they are suspended for next semester. Affected students get a special "
         "registration window."),
        ("general", "What is the warning policy?",
         "3 warnings suspend a student (1 semester + fine) or instructor "
         "(cannot teach next semester). Honor-roll students can spend 1 honor "
         "to clear 1 warning."),
        ("general", "What is the honor roll?",
         "Semester GPA >= 3.75, or overall GPA >= 3.5 after 2+ semesters."),

        ("student", "How do I retake a course?",
         "You can retake a course only if you previously got an F in it."),
        ("student", "How do I write a review?",
         "Open the Reviews tab in your dashboard, pick a course you're enrolled in "
         "(but only before the instructor posts a grade), give 1-5 stars, and write "
         "the body. Reviews with taboo words are masked or hidden, and you receive warnings."),
        ("student", "How do I graduate?",
         "After completing 8 classes including CS501 plus CS510 or CS520, submit a "
         "graduation application from the Records tab. The registrar will review."),

        ("instructor", "How do I approve waitlist students?",
         "Open the Roster tab for the course, find the Waitlist section, click 'Admit'. "
         "The student moves into the enrolled list (if capacity has space)."),
        ("instructor", "How do I assign grades?",
         "Only during the Grading phase. Open the Grades tab and select a grade from the dropdown. "
         "Missing grades at the end of the period earn you a warning."),

        ("course:CS501", "What is CS501 about?",
         "CS501 Intro to Programming covers Python fundamentals, control flow, "
         "data structures, and small projects. Required core course."),
        ("course:CS510", "What is CS510 about?",
         "CS510 Data Structures covers lists, stacks, queues, trees and hash tables. "
         "Pre-req: CS501."),
        ("course:CS520", "What is CS520 about?",
         "CS520 Algorithms covers sorting, graph algorithms and dynamic programming. "
         "Pre-req: CS501."),
        ("course:CS530", "What is CS530 about?",
         "CS530 Databases covers relational design, SQL, transactions."),
        ("course:CS540", "What is CS540 about?",
         "CS540 AI covers search, machine learning basics, and neural network intro."),
        ("course:CS550", "What is CS550 about?",
         "CS550 Software Engineering covers requirements, design, testing, and demos."),
    ]
    from .db import connect
    with connect() as c:
        for scope, q, a in items:
            existing = c.execute(
                "SELECT 1 FROM qa_corpus WHERE scope=? AND question=?", (scope, q)
            ).fetchone()
            if existing:
                continue
            c.execute(
                "INSERT INTO qa_corpus (scope, question, answer) VALUES (?,?,?)",
                (scope, q, a),
            )
        c.commit()
