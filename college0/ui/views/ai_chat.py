"""Role-scoped AI Q&A area."""
from __future__ import annotations

import tkinter as tk

from core import ai, models
from .. import theme


class AIChatView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG, padx=24, pady=18)
        self.app = app

        tk.Label(self, text="Ask College0 AI", bg=theme.BG, fg=theme.TEXT,
                 font=theme.FONT_H1).pack(anchor="w")

        scope_msg = self._scope_msg()
        tk.Label(self, text=scope_msg, bg=theme.BG, fg=theme.MUTED,
                 font=theme.FONT, wraplength=900, justify="left").pack(anchor="w",
                                                                        pady=(4, 4))
        tk.Label(self,
                 text=("Note (simplification): the 'vector DB' is a small canned "
                       "College0 knowledge base, and the LLM fallback is a templated "
                       "response — no external API call. Real systems would route "
                       "unmatched questions to a hosted LLM."),
                 bg=theme.BG, fg=theme.WARN, font=theme.FONT_SMALL,
                 wraplength=900, justify="left").pack(anchor="w", pady=(0, 10))

        # Chat history pane.
        self.log = tk.Text(self, height=18, font=theme.FONT, wrap="word",
                           bg="white", fg=theme.TEXT,
                           insertbackground=theme.TEXT,
                           relief="flat", padx=10, pady=8)
        self.log.pack(fill="both", expand=True)
        self.log.tag_configure("you", foreground=theme.ACCENT_DARK, font=theme.FONT_BOLD)
        self.log.tag_configure("ai_kb", foreground=theme.GOOD, font=theme.FONT_BOLD)
        self.log.tag_configure("ai_llm", foreground=theme.WARN, font=theme.FONT_BOLD)
        self.log.tag_configure("warn", foreground=theme.BAD, font=theme.FONT_BOLD)
        self.log.configure(state="disabled")

        row = tk.Frame(self, bg=theme.BG)
        row.pack(fill="x", pady=(10, 0))
        self.entry = tk.Entry(row, font=theme.FONT,
                              bg="white", fg=theme.TEXT, insertbackground=theme.TEXT)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda *_: self._ask())
        theme.make_button(row, text="Ask", command=self._ask,
                          bg=theme.ACCENT, fg="white",
                          padx=18, pady=6).pack(side="left", padx=(8, 0))

        # Suggestion chips.
        tips = tk.Frame(self, bg=theme.BG)
        tips.pack(fill="x", pady=(8, 0))
        for q in self._suggestions():
            theme.make_button(tips, text=q,
                              command=lambda t=q: self._set_q(t),
                              bg=theme.PANEL, fg=theme.TEXT,
                              hover_bg="#e6ecff",
                              font=theme.FONT_SMALL,
                              padx=8, pady=2,
                              bordercolor=theme.BORDER).pack(side="left", padx=4)

        self._greet()

    # ----- helpers -----

    def _scope_msg(self):
        if not self.app.user:
            return ("You're asking as a visitor. The AI is limited to general "
                    "information about College0. If the answer is not in the local "
                    "knowledge base, it will be marked as a possible hallucination.")
        role = self.app.user["role"]
        if role == "student":
            return ("As a student, you can also ask about the classes you're taking. "
                    "Unknown questions fall back to a generic AI answer (with a hallucination warning).")
        if role == "instructor":
            return ("As an instructor, you can also ask about your classes / students. "
                    "Unknown questions fall back to a generic AI answer (with a hallucination warning).")
        return ("As registrar you have full access. Unknown questions still fall "
                "back to a generic AI answer (with a hallucination warning).")

    def _suggestions(self):
        if not self.app.user:
            return ["What is College0?", "When is the registration window?",
                    "What courses are offered?"]
        role = self.app.user["role"]
        if role == "student":
            return ["How do I retake a course?", "How do I write a review?",
                    "What is CS501 about?"]
        if role == "instructor":
            return ["How do I approve waitlist students?",
                    "How do I assign grades?"]
        return ["What is the warning policy?", "What is the honor roll?"]

    def _set_q(self, q):
        self.entry.delete(0, "end")
        self.entry.insert(0, q)
        self.entry.focus_set()

    def _course_codes_for_user(self):
        if not self.app.user:
            return []
        sem = models.get_semester_state()["semester"]
        if self.app.user["role"] == "student":
            rows = models.student_enrollments(self.app.user["id"], semester=sem,
                                              statuses=["enrolled"])
            return [r["code"] for r in rows]
        if self.app.user["role"] == "instructor":
            return [c["code"] for c in models.list_courses(semester=sem)
                    if c["instructor_id"] == self.app.user["id"]]
        return []

    def _greet(self):
        scope_codes = self._course_codes_for_user()
        intro = "Hi! Ask me anything about College0."
        if scope_codes:
            intro += f" Your scoped courses this semester: {', '.join(scope_codes)}."
        self._append("College0 AI", intro, tag="ai_kb")

    def _ask(self):
        q = self.entry.get().strip()
        if not q:
            return
        self.entry.delete(0, "end")
        self._append("You", q, tag="you")
        r = ai.ask(q, self.app.user, course_codes=self._course_codes_for_user())
        if r["source"] == "local-kb":
            header = f"College0 AI (local KB · match {r['score']})"
            self._append(header, r["answer"], tag="ai_kb")
        else:
            self._append("College0 AI (LLM fallback)", r["answer"], tag="ai_llm")
            self._append("Warning", "This response was not grounded in College0's data and may be a hallucination.",
                          tag="warn")

    def _append(self, who: str, text: str, tag: str):
        self.log.configure(state="normal")
        self.log.insert("end", f"{who}:\n", tag)
        self.log.insert("end", f"{text}\n\n")
        self.log.see("end")
        self.log.configure(state="disabled")
