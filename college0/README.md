# College0

A small AI-enabled online graduate program management system built for
CSC 322. Single-window Tkinter GUI, SQLite for storage, and an optional
real LLM fallback for the AI Q&A area.

## Requirements

Python 3.10 or later with Tk support. Nothing else is required to run
the core system — it uses only the standard library.

The optional "real LLM" fallback for the AI Q&A area additionally needs
the `anthropic` Python SDK and a valid API key. The app works fine
without it (see [AI fallback](#ai-fallback) below).

| OS | Recommended setup |
|---|---|
| **macOS** | Install Python from [python.org](https://www.python.org/downloads/) (the bundled Tk in Apple's stock `python3` renders a blank window). Launch with `python3.12 main.py` (or whatever 3.x you installed). |
| **Windows** | Install Python from [python.org](https://www.python.org/downloads/). Launch with `python main.py`. |
| **Linux** | Install Python 3 and Tk via your package manager (`sudo apt-get install python3 python3-tk` on Debian/Ubuntu). Launch with `python3 main.py`. |

## Run it

```bash
git clone https://github.com/Rioo-o/322-Project-Team-M.git
cd 322-Project-Team-M/college0

# macOS (python.org install — the system python3 will render a blank window)
python3.12 main.py

# Windows
python main.py

# Linux
python3 main.py
```

On first launch the app creates `college0.db` next to `main.py` and
seeds it with demo data. To reset everything, quit the app, delete
`college0.db`, and relaunch.

## Demo accounts

All passwords are `password` unless noted otherwise.

| Role       | Username     | Password | Notes |
| ---------- | ------------ | -------- | ----- |
| Registrar  | `registrar`  | `admin`  | Super-user; sees everything. |
| Instructor | `prof_adams` | password | Teaches CS501 + CS520. |
| Instructor | `prof_brown` | password | Teaches CS510. |
| Instructor | `prof_chen`  | password | Teaches CS530 + CS550. |
| Instructor | `prof_diaz`  | password | Teaches CS540 only — will be auto-suspended in the demo. |
| Student    | `alice`      | password | No CS501 history → demos the waitlist path. |
| Student    | `bob`        | password | Has a prior F in CS510 → demos the retake-F rule. |
| Student    | `eve`        | password | 8 prior completions → demos a graduation approval. |
| Student    | `frank`      | password | Low GPA → demos auto-termination after grading. |
| Student    | `new_grad`   | `welcome` | First-time login → demos the forced password change + tutorial. |

Additional student accounts (all `password`): `carol`, `dan`, `grace`,
`hank`, `ivy`, `jay`.

## AI fallback

The AI Q&A area first checks a small role-scoped Q&A corpus stored in
SQLite. If nothing matches well enough, the question is forwarded to
Anthropic's Claude API and the answer is shown with an explicit
"ungrounded — may be a hallucination" warning so it's obvious where
the response came from.

**To enable the real LLM** (recommended for the full experience):

```bash
pip install anthropic
export ANTHROPIC_API_KEY="sk-ant-..."   # macOS / Linux
# Windows PowerShell:
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

Then launch the app normally. In the AI Chat tab, ask something the
local corpus doesn't cover (e.g. `who is the chancellor of Stanford?`)
and the answer will be tagged `(General LLM — Anthropic ...)`.

**To run without it**: don't install the package and don't set the
variable. Any question that misses the local corpus falls back to a
templated offline answer (still flagged as a possible hallucination).
Everything else in the system continues to work.

The model can be overridden with `COLLEGE0_LLM_MODEL` (defaults to
`claude-haiku-4-5`).

## Project layout

```
college0/
  main.py            # entry point
  README.md
  core/
    db.py            # SQLite schema + connection helpers
    seed.py          # demo data
    auth.py          # login / password change
    models.py        # CRUD helpers
    rules.py         # business rules (warnings, GPAs, suspensions, ...)
    ai.py            # local Q&A corpus + LLM fallback
  ui/
    app.py           # single-window router
    theme.py         # colors / fonts / cross-platform button helper
    views/
      home.py        # public landing page
      login.py       # sign-in + first-login password change
      apply.py       # visitor applications
      registrar.py   # registrar dashboard
      instructor.py  # instructor dashboard
      student.py     # student dashboard
      ai_chat.py     # AI Q&A
```

## Known simplifications

A few corners are intentionally cut so the demo stays small and fully
offline-capable:

- Passwords are stored in plaintext.
- The "vector DB" is a bag-of-words coverage score over a small canned
  Q&A corpus, not a real embedding store.
- Semester phases advance manually from the registrar dashboard — no
  clock-based progression.
- Fines and "email" notifications are surfaced as in-app banners
  rather than actually charged or sent.
- Graduation requires 8+ completed non-failed courses, including CS501
  plus either CS510 or CS520.
