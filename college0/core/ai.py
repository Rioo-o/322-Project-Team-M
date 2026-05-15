"""AI Q&A backend.

Two layers:
  1. A small role-scoped Q&A corpus stored in SQLite (``qa_corpus``).
     We score the user's question against each entry with a quick
     bag-of-words coverage metric so we don't need a real embedding lib.
  2. If the best local hit is below ``LOCAL_KB_THRESHOLD`` we treat that
     as "we don't know this" and forward the question to a general LLM
     (Anthropic Claude). Whatever it returns is tagged as ungrounded
     because it's not based on College0's own data.

If the Anthropic SDK isn't installed, ``ANTHROPIC_API_KEY`` isn't set,
or the call fails for any reason, we fall back to a templated answer so
the app stays usable fully offline.
"""
from __future__ import annotations

import os
import re
from typing import Iterable, Optional

from . import models

# If the best local match scores below this, we give up on the KB and
# forward the question to the general LLM. Kept at module level so we
# can tune it without digging through the function.
LOCAL_KB_THRESHOLD = 0.35

# Which Anthropic model to hit for the fallback. A small/fast one is
# plenty for these generic "we don't actually know this" answers.
_ANTHROPIC_MODEL = os.environ.get("COLLEGE0_LLM_MODEL", "claude-haiku-4-5")

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
        # Main signal: what fraction of the user's words appear anywhere
        # in this KB entry. Short, focused queries get rewarded.
        coverage = len(q_tokens & kb_all) / len(q_tokens)
        # Small tiebreaker: prefer entries where the user's words show up
        # in the corpus *question* itself, not just the answer body.
        q_match_bonus = len(q_tokens & q_kb) / max(len(q_kb), 1)
        score = coverage * 0.7 + q_match_bonus * 0.3
        if score > best_score:
            best_score = score
            best = r

    if best and best_score >= LOCAL_KB_THRESHOLD:
        return {
            "answer": best["answer"],
            "source": "local-kb",
            "score": round(best_score, 2),
            "matched_question": best["question"],
        }

    # KB came up short — hand off to the general LLM. We pass the
    # best near-miss along as a soft hint so the model can use it as
    # context without being told to trust it.
    related = best["answer"] if best else None
    llm_answer, llm_source = _call_general_llm(question, user, related=related)
    return {
        "answer": llm_answer,
        "source": llm_source,           # "llm-anthropic" or "llm-templated"
        "score": round(best_score, 2),
        "hallucination_warning": True,
    }


# ---------------------------------------------------------------------------
# General LLM fallback
# ---------------------------------------------------------------------------

def _system_prompt(user: Optional[dict]) -> str:
    role = (user["role"] if user else "visitor")
    return (
        "You are a fallback general-purpose assistant for College0, a small "
        "graduate-school management app. You are being called ONLY because the "
        "user's question did NOT match College0's local knowledge base. "
        "Therefore:\n"
        " - Do NOT invent College0-specific policies, course codes, deadlines "
        "or names. If the answer would require those, say so.\n"
        " - You may answer general academic / programming / life questions "
        "from your own training, briefly.\n"
        " - Keep replies under ~120 words and use plain text (no markdown "
        "headings).\n"
        f" - The user's role in College0 is: {role}."
    )


def _call_general_llm(question: str, user: Optional[dict],
                      related: Optional[str] = None) -> tuple[str, str]:
    """Try the real Anthropic API and fall back to a templated answer.

    Returns ``(answer_text, source_tag)``. ``source_tag`` is either
    ``"llm-anthropic"`` (real API call) or ``"llm-templated"`` (offline
    fallback) so the UI can show how the answer was produced.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _templated_llm(question, user,
                              reason="ANTHROPIC_API_KEY not set"), "llm-templated"

    try:
        # Import here, not at module top, so the app still starts cleanly
        # on machines that never installed the SDK.
        import anthropic  # type: ignore
    except ImportError:
        return _templated_llm(question, user,
                              reason="anthropic SDK not installed"), "llm-templated"

    user_msg = question.strip()
    if related:
        user_msg += (
            "\n\n(For your reference only — this is the closest entry from "
            "College0's own knowledge base, which did NOT match the question "
            "well. Use it as a weak hint, not as fact:\n"
            f"{related})"
        )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=_ANTHROPIC_MODEL,
            max_tokens=400,
            system=_system_prompt(user),
            messages=[{"role": "user", "content": user_msg}],
        )
        # The SDK gives us a list of content blocks; we only care about text.
        parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        answer = "\n".join(p for p in parts if p).strip()
        if not answer:
            return _templated_llm(question, user,
                                  reason="empty response from LLM"), "llm-templated"
        # Prefix the answer so the user can always tell where it came from.
        return (
            f"(General LLM — Anthropic {_ANTHROPIC_MODEL}) {answer}\n\n"
            "WARNING: This answer is NOT grounded in College0's data and may "
            "be wrong (hallucinated). Treat as informational only."
        ), "llm-anthropic"
    except Exception as exc:  # network down, bad key, rate limit, you name it
        return _templated_llm(question, user,
                              reason=f"LLM call failed: {exc}"), "llm-templated"


def _templated_llm(question: str, user: Optional[dict], reason: str = "") -> str:
    """Fallback used when the real LLM isn't reachable.

    Deliberately wordy so it's obvious from the UI which branch ran, even
    when there's no API key configured.
    """
    role = (user["role"] if user else "visitor").capitalize()
    why = f" [offline reason: {reason}]" if reason else ""
    return (
        f"(LLM fallback — templated{why}) I don't have specific College0 "
        f"information about: \"{question.strip()}\". A best-guess from a "
        f"general AI model would be: 'This appears to relate to college "
        f"operations or {role.lower()} workflows. Please confirm with the "
        f"registrar or your course materials.'\n\n"
        "WARNING: This answer is NOT grounded in College0's data and may be "
        "wrong (hallucinated). Treat as informational only."
    )


def seed_corpus() -> None:
    """Load the canned Q&A into the database. Safe to call repeatedly."""
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
