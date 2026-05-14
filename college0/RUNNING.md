# College0 - AI-enabled Online College Program Management System

A toy local GUI demo built with **Python + Tkinter + SQLite** for CSC 322.

## Prerequisites

This app uses only the Python standard library — no `pip install` required. You do need **Python 3.10+** with Tkinter included.

| OS | Recommended install | Launch command |
|---|---|---|
| **macOS** | [python.org installer](https://www.python.org/downloads/) (includes Tk) | `python3.12 main.py` (or whichever 3.x version you installed) |
| **Windows** | [python.org installer](https://www.python.org/downloads/) | `python main.py` |
| **Linux** | System package manager | `python3 main.py` |

> **macOS users — important:** macOS ships two different Python 3 binaries that behave very differently with Tkinter:
> - `python3` → Apple's Xcode Command Line Tools Python. Its Tk framework is broken and renders a blank grey window.
> - `python3.12` (or `python3.11`, etc.) → the Python you installed from python.org. This includes a correct Tk build and works fine.
>
> If you haven't installed Python from python.org yet, download it from https://www.python.org/downloads/ and use the versioned command (e.g. `python3.12 main.py`).

> **Linux users:** If you see `ModuleNotFoundError: No module named 'tkinter'`, install it once:
> Ubuntu/Debian → `sudo apt-get install python3-tk`

## Quick start

From the folder that contains this README (i.e. the `college0/` folder):

```bash
# macOS
python3.12 main.py

# Windows
python main.py

# Linux
python3 main.py
```

Or, from anywhere on your machine:

```bash
cd "path/to/College 0 CSC 322/college0"
python3.12 main.py   # adjust command for your OS per the table above
```

On first launch the file `college0.db` is created in this folder and pre-loaded with demo data (10 students + 1 brand-new student, 4 instructors, 1 registrar, several courses and reviews). To reset the demo, just delete `college0.db` and relaunch.

## Demo accounts

| Role       | Username     | Password   | Notes                                                          |
| ---------- | ------------ | ---------- | -------------------------------------------------------------- |
| Registrar  | `registrar`  | `admin`    | Super-user. Sees everything.                                   |
| Instructor | `prof_adams` | `password` | Teaches CS501 + CS520                                          |
| Instructor | `prof_brown` | `password` | Teaches CS510                                                  |
| Instructor | `prof_chen`  | `password` | Teaches CS530 + CS550                                          |
| Instructor | `prof_diaz`  | `password` | Teaches CS540 (will be auto-suspended in demo)                 |
| Student    | `alice`      | `password` | No CS501 history → can demo the **CS501 waitlist**.            |
| Student    | `bob`        | `password` | Has a prior F in CS510 → can demo the **retake-F** rule.       |
| Student    | `eve`        | `password` | 8 completed courses → can demo the **graduation-approved** flow. |
| Student    | `frank`      | `password` | GPA 1.75 → demos the auto-termination rule after grading.      |
| Student    | `new_grad`   | `welcome`  | First-login → demos forced **password change + tutorial**.     |

Other student accounts: `carol`, `dan`, `grace`, `hank`, `ivy`, `jay` (all `password`).

## What the demo covers (spec mapping)

1. **Public Home** - intro, top-rated and lowest-rated classes, students with the highest GPA.
2. **Visitor applications** - apply to become a student (auto-rule = GPA ≥ 3.0 + quota; manual override requires justification) or instructor.
3. **Registrar dashboard**
   - Approve / reject applications. Auto-rule fires; override needs justification.
   - Move the semester through its 4 phases (Set-up → Registration → Class Running → Grading → next semester).
   - Create courses and assign instructors.
   - Manage the taboo-word list.
   - Process student / instructor complaints (warn target, warn filer, dismiss).
   - See warnings, suspensions, fines and instructor class-GPA flags.
   - Review and decide graduation applications.
   - "People" tab: see every user's status, warnings, fines.
4. **Instructor dashboard** - class roster, wait-list admit, grade entry during Grading phase, file a complaint about a student.
5. **Student dashboard** - register for 2–4 courses (conflict + capacity + retake-F rules), see records, write reviews (with taboo-word filtering and warnings), submit complaints, apply for graduation, **password change on first login**, **tutorial banner** for new students. Honor tokens can be spent to clear warnings; fines can be paid in-app.
6. **AI Q&A** - role-scoped chat area. Looks up a local "vector-style" Q&A corpus first; if nothing matches well enough, it falls back to a simulated LLM answer with a clear hallucination warning. Visitors see general info only; students see their currently-enrolled courses; instructors see their classes.
7. **Creative feature: Study Buddy Matcher** - in the student dashboard, ranks classmates by Jaccard similarity over current-semester enrollments and shows the courses you share.

## Run the app

```bash
cd college0

# macOS (python.org install)
python3.12 main.py

# Windows
python main.py

# Linux
python3 main.py
```

A 5-minute demo script with exact click order is in **`demo_script.md`**.

## Project layout

```
college0/
  main.py                # entry point
  college0.db            # created on first run
  README.md
  demo_script.md         # what to click for the demo
  requirements.txt       # (intentionally empty — stdlib only)
  core/
    db.py                # schema + connection
    seed.py              # demo data
    auth.py              # login / password change
    models.py            # CRUD helpers
    rules.py             # business rules (warnings, GPA, suspensions...)
    ai.py                # local Q&A corpus + simulated LLM fallback
  ui/
    app.py               # single-window router
    theme.py             # colors / fonts
    views/
      home.py            # public landing
      login.py           # login + first-login password change
      apply.py           # visitor applications
      registrar.py       # registrar dashboard
      instructor.py
      student.py
      ai_chat.py         # AI Q&A
```

## Notes / simplifications

These are intentionally simplified to keep the demo simple and offline:

- Passwords are stored in plaintext. **Do not use this code for anything real.**
- The "vector DB" is a query-coverage score over a small canned Q&A corpus stored in SQLite, not a real embedding store.
- The "LLM fallback" is a templated response with an explicit hallucination warning; no external API is called, so the demo runs fully offline.
- Semester phases are advanced manually by the registrar (no clock-based progression).
- The "special re-registration window" for students of cancelled courses is simplified: those students are simply moved to `dropped` for the cancelled course; the registrar can reopen registration manually if desired.
- Fines and "email" notifications are surfaced in-app (banners, lists), not actually charged or sent.
- Graduation requirements are simplified to: 8+ completed courses (grade ≥ D) including CS501 plus either CS510 or CS520.

## Creative feature: Study Buddy Matcher

Open the **Study Buddies** tab inside the student dashboard. The system computes Jaccard similarity over each student's current-semester enrolled courses and shows the top 5 best-matched classmates along with the courses they share - a small but real social-graph layer on top of the data the system already has.
