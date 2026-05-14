"""Student dashboard."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from core import models, rules
from core.db import connect
from .. import theme


class StudentView(tk.Frame):
    def __init__(self, parent, app, section: str):
        super().__init__(parent, bg=theme.BG, padx=20, pady=14)
        self.app = app
        self.section = section

        # Hard banner for suspended / terminated / graduated users.
        if app.user.get("status") in ("suspended", "terminated", "graduated"):
            self._hard_status_banner()

        # Tutorial banner for new students (shown only the first time).
        if app.user.get("is_new") and section == "records":
            self._tutorial_banner()
            models.clear_first_login(app.user["id"])
            app.user["is_new"] = 0

        # Status banner for fines / warnings.
        if app.user.get("warnings") or app.user.get("fine_due"):
            self._status_banner()

        # Special re-registration banner (spec: one more chance for students
        # whose course was cancelled). Visible on every section so the
        # student can't miss it.
        if (models.get_special_reg(app.user["id"])
                and models.get_semester_state()["phase"] == "running"
                and section != "register"):
            self._special_reg_banner()

        header_map = {
            "records":   ("My Records",
                          "Your GPA, honors, warnings, transcript, and current enrollments."),
            "register":  ("Course Registration",
                          "Open only during the REGISTRATION phase. 2–4 courses; no time conflicts; full courses go to waitlist; you can retake a course only if you previously got an F."),
            "reviews":   ("Reviews",
                          "Rate a class you're currently taking (only before the instructor posts your grade). Reviews with taboo words are masked or hidden and earn warnings."),
            "complaint": ("File a Complaint",
                          "Send a complaint to the registrar about another student or an instructor."),
            "grad":      ("Graduation Application",
                          "Apply when you've completed 8 courses (incl. CS501 + CS510 or CS520). A rejected reckless application earns a warning."),
            "buddies":   ("Study Buddy Matcher",
                          "Creative feature: classmates ranked by Jaccard similarity over your current courses."),
        }
        title, subtitle = header_map.get(section, (section, ""))
        tk.Label(self, text=f"Student · {title}", bg=theme.BG,
                 fg=theme.TEXT, font=theme.FONT_H1).pack(anchor="w")
        if subtitle:
            tk.Label(self, text=subtitle, bg=theme.BG, fg=theme.MUTED,
                     font=theme.FONT, wraplength=950,
                     justify="left").pack(anchor="w", pady=(2, 6))

        getattr(self, f"_render_{section}", self._not_found)()

    def _not_found(self):
        tk.Label(self, text=f"Unknown section: {self.section}", bg=theme.BG).pack()

    def _panel(self, title=""):
        p = tk.Frame(self, bg=theme.PANEL, highlightthickness=1,
                     highlightbackground=theme.BORDER, padx=14, pady=10)
        if title:
            tk.Label(p, text=title, bg=theme.PANEL, fg=theme.TEXT,
                     font=theme.FONT_H2).pack(anchor="w", pady=(0, 4))
        return p

    # ----- banners -----

    def _hard_status_banner(self):
        status = self.app.user["status"]
        until = self.app.user.get("suspended_until_semester")
        susp_msg = ("Your account is SUSPENDED for this semester. You cannot "
                    "register, review, or file complaints right now. You can "
                    "still pay your outstanding fine and redeem any honor "
                    "tokens below. ")
        if until:
            susp_msg += (f"You will be automatically reinstated when the "
                         f"registrar advances to semester {until}.")
        msg = {
            "suspended":  susp_msg,
            "terminated": "Your account has been TERMINATED. Please contact the registrar.",
            "graduated":  "Congratulations — you've graduated! Most features are now read-only.",
        }.get(status, "")
        box = tk.Frame(self, bg="#fff1f0", highlightthickness=2,
                       highlightbackground=theme.BAD, padx=14, pady=10)
        box.pack(fill="x", pady=(0, 10))
        tk.Label(box, text=f"Account status: {status.upper()}",
                 bg="#fff1f0", fg=theme.BAD, font=theme.FONT_H2).pack(anchor="w")
        tk.Label(box, text=msg, bg="#fff1f0", fg=theme.TEXT,
                 font=theme.FONT, wraplength=900,
                 justify="left").pack(anchor="w")

    def _tutorial_banner(self):
        box = tk.Frame(self, bg="#fff8e1", highlightthickness=1,
                       highlightbackground="#f4d35e", padx=14, pady=10)
        box.pack(fill="x", pady=(0, 10))
        tk.Label(box, text="Welcome to College0!  (one-time tutorial)",
                 bg="#fff8e1", fg=theme.TEXT, font=theme.FONT_H2).pack(anchor="w")
        tk.Label(box,
                 text=("• Use the left sidebar to navigate.\n"
                       "• My Records – your transcript, GPA, honors, warnings.\n"
                       "• Register – pick 2–4 courses during the Registration phase.\n"
                       "• Reviews – rate classes you are currently taking (before grades are posted).\n"
                       "• Complaint – escalate issues to the registrar.\n"
                       "• Study Buddies – classmates with the closest course overlap.\n"
                       "• AI Chat – ask questions; if the answer isn't in our knowledge base, "
                       "you'll get a fallback marked as a possible hallucination."),
                 bg="#fff8e1", fg=theme.TEXT,
                 font=theme.FONT, justify="left", anchor="w").pack(anchor="w", pady=(4, 0))

    def _status_banner(self):
        msgs = []
        if self.app.user.get("warnings"):
            msgs.append(f"You have {self.app.user['warnings']} warning(s).")
        if self.app.user.get("fine_due"):
            msgs.append(f"Outstanding fine: ${self.app.user['fine_due']:.0f}.")
        if not msgs:
            return
        bar = tk.Frame(self, bg="#fff1f0", highlightthickness=1,
                       highlightbackground="#f0b3ad", padx=12, pady=6)
        bar.pack(fill="x", pady=(0, 8))
        tk.Label(bar, text=" · ".join(msgs), bg="#fff1f0", fg=theme.BAD,
                 font=theme.FONT_BOLD).pack(side="left")
        if self.app.user.get("fine_due"):
            theme.make_button(bar, text="Pay fine", command=self._pay_fine,
                              bg=theme.ACCENT, fg="white",
                              padx=8, pady=2).pack(side="right")
        with connect() as c:
            r = c.execute("SELECT honors FROM students WHERE user_id=?",
                          (self.app.user["id"],)).fetchone()
        if r and r["honors"] > 0 and self.app.user["warnings"]:
            theme.make_button(bar,
                              text=f"Use 1 honor → clear 1 warning ({r['honors']} avail)",
                              command=self._use_honor,
                              bg=theme.GOOD, fg="white",
                              padx=8, pady=2).pack(side="right", padx=4)

    def _special_reg_banner(self):
        box = tk.Frame(self, bg="#fff8e1", highlightthickness=1,
                       highlightbackground="#f4d35e", padx=14, pady=10)
        box.pack(fill="x", pady=(0, 8))
        tk.Label(box,
                 text="One of your courses was cancelled — special re-registration is open.",
                 bg="#fff8e1", fg=theme.WARN,
                 font=theme.FONT_BOLD).pack(side="left")
        theme.make_button(box, text="Pick another course",
                          command=lambda: self.app.show("student_register"),
                          bg=theme.ACCENT, fg="white",
                          padx=10, pady=2).pack(side="right")

    def _pay_fine(self):
        models.pay_fine(self.app.user["id"])
        self.app.refresh_user()
        self.app.toast_msg("Fine paid.")
        self.app.show(f"student_{self.section}")

    def _use_honor(self):
        ok = models.consume_honor_to_clear_warning(self.app.user["id"])
        if ok:
            self.app.refresh_user()
            self.app.toast_msg("1 warning cleared with 1 honor.", "ok")
        else:
            self.app.toast_msg("No honors / warnings available.", "warn")
        self.app.show(f"student_{self.section}")

    # ----- records -----

    def _render_records(self):
        with connect() as c:
            r = c.execute("SELECT * FROM students WHERE user_id=?",
                          (self.app.user["id"],)).fetchone()
        if not r:
            tk.Label(self, text="No academic record.", bg=theme.BG).pack()
            return

        stats = self._panel("Academic summary")
        stats.pack(fill="x", pady=(0, 10))
        row = tk.Frame(stats, bg=theme.PANEL)
        row.pack(fill="x")

        def stat(label, value, color=theme.TEXT):
            box = tk.Frame(row, bg=theme.PANEL)
            box.pack(side="left", padx=14)
            tk.Label(box, text=value, bg=theme.PANEL, fg=color,
                     font=("Segoe UI", 18, "bold")).pack(anchor="w")
            tk.Label(box, text=label, bg=theme.PANEL, fg=theme.MUTED,
                     font=theme.FONT_SMALL).pack(anchor="w")

        stat("Overall GPA", f"{r['gpa']:.2f}")
        stat("Semester GPA", f"{r['semester_gpa']:.2f}")
        stat("Courses done", str(r["courses_completed"]))
        stat("Honors", str(r["honors"]), color=theme.GOOD)
        stat("Warnings", str(self.app.user["warnings"]),
             color=theme.BAD if self.app.user["warnings"] else theme.TEXT)

        # Transcript.
        tr = self._panel("Transcript")
        tr.pack(fill="both", expand=True)
        cols = ("semester", "code", "title", "status", "grade")
        tree = ttk.Treeview(tr, columns=cols, show="headings", height=10)
        for c, w in zip(cols, (80, 80, 240, 100, 60)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True)
        history = models.student_history(self.app.user["id"])
        for h in history:
            tree.insert("", "end", values=(h["semester"], h["code"], h["title"],
                                            h["status"], h["grade"] or "—"))

        # Current enrollment.
        sem = models.get_semester_state()["semester"]
        cur_panel = self._panel(f"Current semester ({sem}) enrolment")
        cur_panel.pack(fill="x", pady=(10, 0))
        cur = models.student_enrollments(self.app.user["id"], semester=sem,
                                          statuses=["enrolled", "waitlist"])
        if not cur:
            tk.Label(cur_panel, text="(no current enrollments)", bg=theme.PANEL,
                     fg=theme.MUTED).pack(anchor="w")
        for e in cur:
            tk.Label(cur_panel,
                     text=f"  • {e['code']} {e['title']}  "
                          f"({e['day']} {e['start_hour']}-{e['end_hour']}) "
                          f"[{e['status']}]",
                     bg=theme.PANEL, fg=theme.TEXT,
                     font=theme.FONT, anchor="w").pack(fill="x", anchor="w")

    # ----- register -----

    def _render_register(self):
        state = models.get_semester_state()
        special = models.get_special_reg(self.app.user["id"])
        # Allow registration in REGISTRATION or in RUNNING with the
        # "one more chance" flag set. Block everywhere else.
        if state["phase"] == "registration":
            pass
        elif state["phase"] == "running" and special:
            box = tk.Frame(self, bg="#fff8e1", highlightthickness=1,
                           highlightbackground="#f4d35e", padx=14, pady=10)
            box.pack(fill="x", pady=(0, 10))
            tk.Label(box,
                     text="Special re-registration window is OPEN for you",
                     bg="#fff8e1", fg=theme.WARN, font=theme.FONT_H2).pack(anchor="w")
            tk.Label(box,
                     text=("One of your courses was cancelled. The spec gives you "
                           "one more chance to pick another course this semester. "
                           "This window closes when the registrar advances to the "
                           "GRADING phase."),
                     bg="#fff8e1", fg=theme.TEXT, font=theme.FONT,
                     wraplength=900, justify="left").pack(anchor="w", pady=(4, 0))
        else:
            tk.Label(self,
                     text=f"Course registration is only open during the REGISTRATION phase "
                          f"(current: {state['phase']}).",
                     bg=theme.BG, fg=theme.WARN,
                     font=theme.FONT_BOLD).pack(anchor="w", pady=8)
            return

        current = models.student_enrollments(self.app.user["id"],
                                              semester=state["semester"],
                                              statuses=["enrolled", "waitlist"])

        sched_panel = self._panel(
            f"My picks ({len([e for e in current if e['status']=='enrolled'])} "
            f"enrolled, {len([e for e in current if e['status']=='waitlist'])} waitlisted; need 2–4)")
        sched_panel.pack(fill="x")
        if not current:
            tk.Label(sched_panel, text="(empty)", bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w")
        for e in current:
            row = tk.Frame(sched_panel, bg=theme.PANEL)
            row.pack(fill="x")
            tk.Label(row,
                     text=f"  • {e['code']} {e['title']} "
                          f"({e['day']} {e['start_hour']}-{e['end_hour']}) [{e['status']}]",
                     bg=theme.PANEL, fg=theme.TEXT,
                     font=theme.FONT, anchor="w").pack(side="left")
            theme.make_button(row, text="Drop",
                              command=lambda eid=e["id"]: self._drop(eid),
                              bg=theme.BAD, fg="white",
                              padx=8, pady=2).pack(side="right", padx=4)

        # Available courses.
        avail = self._panel("Available courses")
        avail.pack(fill="both", expand=True, pady=(10, 0))
        for c in models.list_courses(semester=state["semester"], only_active=True):
            enrolled = len(models.course_enrollments(c["id"], statuses=["enrolled"]))
            row = tk.Frame(avail, bg=theme.PANEL)
            row.pack(fill="x", pady=2)
            label = (f"{c['code']} {c['title']}  ·  "
                     f"{c['day']} {c['start_hour']}-{c['end_hour']}  ·  "
                     f"{enrolled}/{c['capacity']} enrolled  ·  "
                     f"Instructor: {c['instructor_name'] or '—'}")
            tk.Label(row, text=label, bg=theme.PANEL, fg=theme.TEXT,
                     font=theme.FONT, anchor="w").pack(side="left")
            # Retake hint.
            if models.has_failed_course(self.app.user["id"], c["code"]):
                tk.Label(row, text="(retake eligible)", bg=theme.PANEL,
                         fg=theme.WARN, font=theme.FONT_SMALL).pack(side="left", padx=6)
            theme.make_button(row, text="Register",
                              command=lambda cid=c["id"]: self._register(cid),
                              bg=theme.ACCENT, fg="white",
                              padx=10, pady=2).pack(side="right", padx=4)

    def _register(self, course_id: int):
        r = rules.try_register(self.app.user["id"], course_id)
        if not r["ok"]:
            self.app.toast_msg(r["msg"], "bad")
            return
        tone = "warn" if r.get("waitlist") else "ok"
        self.app.toast_msg(r["msg"], tone)
        self.app.show("student_register")

    def _drop(self, enrollment_id: int):
        models.drop_enrollment(enrollment_id)
        self.app.toast_msg("Dropped.")
        self.app.show("student_register")

    # ----- reviews -----

    def _render_reviews(self):
        state = models.get_semester_state()
        # Courses the student is currently enrolled in (or has been in this semester),
        # with no grade yet posted.
        with connect() as c:
            rows = c.execute(
                """
                SELECT c.id, c.code, c.title, e.grade
                  FROM enrollments e JOIN courses c ON c.id = e.course_id
                 WHERE e.student_id=? AND e.semester=?
                   AND e.status IN ('enrolled','completed','failed')
                """,
                (self.app.user["id"], state["semester"]),
            ).fetchall()
        # Spec: can't rate after instructor posts grade.
        ratable = [r for r in rows if not r["grade"]]

        form = self._panel("Write a review (for a class you're currently in)")
        form.pack(fill="x")
        if not ratable:
            tk.Label(form, text=("No ratable class this semester (you can review a class "
                                 "only before the instructor posts your grade)."),
                     bg=theme.PANEL, fg=theme.MUTED, wraplength=900,
                     justify="left").pack(anchor="w")
        else:
            tk.Label(form, text="Course:", bg=theme.PANEL, fg=theme.TEXT,
                     font=theme.FONT).pack(anchor="w")
            course_names = [f"{r['code']} {r['title']}" for r in ratable]
            cvar = tk.StringVar(value=course_names[0])
            ttk.Combobox(form, textvariable=cvar, state="readonly",
                         values=course_names, width=40).pack(anchor="w", pady=(0, 6))

            tk.Label(form, text="Stars (1-5):", bg=theme.PANEL, fg=theme.TEXT,
                     font=theme.FONT).pack(anchor="w")
            stars_var = tk.IntVar(value=5)
            row = tk.Frame(form, bg=theme.PANEL)
            row.pack(anchor="w")
            # text="" because macOS native radiobuttons ignore fg; we render
            # the label separately so it stays visible on the white panel.
            for v in (1, 2, 3, 4, 5):
                cell = tk.Frame(row, bg=theme.PANEL)
                cell.pack(side="left")
                tk.Radiobutton(cell, text="", variable=stars_var, value=v,
                               bg=theme.PANEL).pack(side="left")
                tk.Label(cell, text=str(v), bg=theme.PANEL, fg=theme.TEXT,
                         font=theme.FONT).pack(side="left", padx=(0, 6))

            tk.Label(form, text="Review:", bg=theme.PANEL, fg=theme.TEXT,
                     font=theme.FONT).pack(anchor="w", pady=(8, 0))
            body = tk.Text(form, height=5, width=80, font=theme.FONT,
                           bg="white", fg=theme.TEXT, insertbackground=theme.TEXT)
            body.pack(anchor="w")

            def submit():
                code_title = cvar.get().split(" ", 1)[0]
                target = next((r for r in ratable if r["code"] == code_title), None)
                txt = body.get("1.0", "end").strip()
                if not target or not txt:
                    self.app.toast_msg("Pick a course and write a review.", "bad")
                    return
                res = rules.process_review(self.app.user["id"], target["id"],
                                           stars_var.get(), txt)
                self.app.refresh_user()
                tone = {"ok": "ok", "masked": "warn", "hidden": "bad"}[res["outcome"]]
                self.app.toast_msg(res["message"], tone)
                self.app.show("student_reviews")

            theme.make_button(form, text="Submit review", command=submit,
                              bg=theme.ACCENT, fg="white",
                              padx=14, pady=6).pack(anchor="w", pady=(8, 0))

        # Existing reviews.
        existing = self._panel("My reviews so far")
        existing.pack(fill="both", expand=True, pady=(10, 0))
        with connect() as c:
            mine = c.execute(
                """
                SELECT r.*, c.code, c.title FROM reviews r
                JOIN courses c ON c.id=r.course_id
                WHERE r.student_id=?
                ORDER BY r.id DESC
                """,
                (self.app.user["id"],),
            ).fetchall()
        if not mine:
            tk.Label(existing, text="(none)", bg=theme.PANEL,
                     fg=theme.MUTED).pack(anchor="w")
        for r in mine:
            tag = "hidden" if r["visible"] == 0 else "visible"
            tk.Label(existing,
                     text=f"  • {r['code']} {r['title']}  "
                          f"({r['stars']}/5)  [{tag}]  \"{r['body']}\"",
                     bg=theme.PANEL, fg=theme.TEXT, font=theme.FONT,
                     anchor="w", wraplength=900,
                     justify="left").pack(fill="x", anchor="w")

    # ----- complaint -----

    def _render_complaint(self):
        panel = self._panel("File a complaint")
        panel.pack(fill="x")

        tk.Label(panel, text="Against:", bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT).pack(anchor="w")
        # Build list of possible targets: other students + instructors.
        targets = [t for t in (models.list_students() + models.list_instructors())
                   if t["id"] != self.app.user["id"]]
        labels = [f"{t['full_name']} ({t['role']})" for t in targets]
        tvar = tk.StringVar(value=labels[0] if labels else "")
        ttk.Combobox(panel, textvariable=tvar, state="readonly",
                     values=labels, width=40).pack(anchor="w", pady=(0, 8))

        tk.Label(panel, text="Reason:", bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT).pack(anchor="w")
        body = tk.Text(panel, height=5, width=80, font=theme.FONT,
                       bg="white", fg=theme.TEXT, insertbackground=theme.TEXT)
        body.pack(anchor="w")

        def submit():
            target = next((t for t, lab in zip(targets, labels) if lab == tvar.get()),
                          None)
            txt = body.get("1.0", "end").strip()
            if not target or not txt:
                self.app.toast_msg("Pick a target and a reason.", "bad")
                return
            models.add_complaint(self.app.user["id"], target["id"],
                                 target["role"], txt)
            self.app.toast_msg("Complaint sent to the registrar.")
            body.delete("1.0", "end")

        theme.make_button(panel, text="Submit", command=submit,
                          bg=theme.ACCENT, fg="white",
                          padx=14, pady=6).pack(anchor="w", pady=(8, 0))

    # ----- graduation -----

    def _render_grad(self):
        check = rules.check_graduation(self.app.user["id"])

        panel = self._panel("Graduation requirement check")
        panel.pack(fill="x")
        tk.Label(panel,
                 text=f"Status: {'READY' if check['ok'] else 'NOT YET'}",
                 bg=theme.PANEL, fg=(theme.GOOD if check["ok"] else theme.BAD),
                 font=theme.FONT_BOLD).pack(anchor="w")
        tk.Label(panel, text=check["msg"], bg=theme.PANEL,
                 fg=theme.MUTED, font=theme.FONT,
                 wraplength=900, justify="left").pack(anchor="w", pady=(2, 6))

        tk.Label(panel,
                 text=("Reminder: a frivolous application earns a warning. "
                       "Make sure the requirements are met before submitting."),
                 bg=theme.PANEL, fg=theme.WARN, font=theme.FONT_SMALL,
                 wraplength=900, justify="left").pack(anchor="w")
        theme.make_button(panel, text="Submit graduation application",
                          command=self._submit_grad,
                          bg=theme.ACCENT, fg="white",
                          padx=14, pady=6).pack(anchor="w", pady=(10, 0))

        prior = self._panel("My past applications")
        prior.pack(fill="x", pady=(10, 0))
        with connect() as c:
            mine = c.execute(
                "SELECT * FROM graduation_apps WHERE student_id=? ORDER BY id DESC",
                (self.app.user["id"],),
            ).fetchall()
        if not mine:
            tk.Label(prior, text="(none yet)", bg=theme.PANEL,
                     fg=theme.MUTED).pack(anchor="w")
        for g in mine:
            tk.Label(prior, text=f"  • #{g['id']}: {g['status']} — {g['note'] or ''}",
                     bg=theme.PANEL, fg=theme.MUTED,
                     font=theme.FONT_SMALL, anchor="w").pack(fill="x", anchor="w")

    def _submit_grad(self):
        models.submit_graduation(self.app.user["id"])
        self.app.toast_msg("Graduation application submitted.")
        self.app.show("student_grad")

    # ----- creative: study buddies -----

    def _render_buddies(self):
        state = models.get_semester_state()
        me = self.app.user["id"]
        my_enrol = {e["course_id"] for e in models.student_enrollments(
            me, semester=state["semester"], statuses=["enrolled"])}

        panel = self._panel("Top study buddies (current-semester course overlap)")
        panel.pack(fill="both", expand=True)

        tk.Label(panel,
                 text=("How it works: we compare your currently-enrolled courses to "
                       "every other active student's, and rank by Jaccard similarity "
                       "(|shared| / |union|). Bigger overlap = better buddy."),
                 bg=theme.PANEL, fg=theme.MUTED, font=theme.FONT_SMALL,
                 wraplength=900, justify="left").pack(anchor="w", pady=(0, 8))

        if not my_enrol:
            tk.Label(panel,
                     text="You aren't enrolled in any current course yet, so we have "
                          "nothing to compare. Try the Register tab.",
                     bg=theme.PANEL, fg=theme.WARN).pack(anchor="w")
            return

        # Compute similarity for every other active student.
        results = []
        with connect() as c:
            rows = c.execute(
                """
                SELECT u.id, u.full_name FROM users u
                WHERE u.role='student' AND u.status='active' AND u.id<>?
                """,
                (me,),
            ).fetchall()
        for r in rows:
            their_enrol = {e["course_id"] for e in models.student_enrollments(
                r["id"], semester=state["semester"], statuses=["enrolled"])}
            if not their_enrol:
                continue
            shared = my_enrol & their_enrol
            if not shared:
                continue
            score = len(shared) / len(my_enrol | their_enrol)
            results.append((r["full_name"], score, shared))
        results.sort(key=lambda t: t[1], reverse=True)

        if not results:
            tk.Label(panel, text="No classmates share your current courses yet.",
                     bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w")
            return

        # Index course names.
        sem_courses = {c["id"]: c for c in models.list_courses(semester=state["semester"])}
        for name, score, shared in results[:5]:
            row = tk.Frame(panel, bg=theme.PANEL,
                           highlightthickness=1, highlightbackground=theme.BORDER,
                           padx=10, pady=6)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=f"{name}", bg=theme.PANEL, fg=theme.TEXT,
                     font=theme.FONT_BOLD).pack(anchor="w")
            tk.Label(row, text=f"Similarity: {score:.2f}",
                     bg=theme.PANEL, fg=theme.GOOD,
                     font=theme.FONT_BOLD).pack(anchor="w")
            codes = ", ".join(sem_courses[s]["code"] for s in shared if s in sem_courses)
            tk.Label(row, text=f"Shared courses: {codes}",
                     bg=theme.PANEL, fg=theme.MUTED,
                     font=theme.FONT_SMALL).pack(anchor="w")
