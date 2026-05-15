"""Registrar dashboard (single window, section-based)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox

from core import models, rules
from core.db import connect
from .. import theme


class RegistrarView(tk.Frame):
    def __init__(self, parent, app, section: str):
        super().__init__(parent, bg=theme.BG, padx=20, pady=14)
        self.app = app
        self.section = section

        header_map = {
            "apps":        ("Applications",
                            "Review applications. The auto-rule for students is GPA ≥ 3.0 + quota. "
                            "Overriding the rule for a student requires a written justification."),
            "courses":     ("Course Set-up",
                            "Create new courses during the SETUP phase, and see every course in this semester."),
            "phase":       ("Phase / Rules",
                            "Move the semester forward. Each transition can auto-cancel courses, warn instructors, "
                            "issue student warnings, and trigger end-of-grading consequences. "
                            "(Simulated: phases advance on click; in a real system they would be on a calendar.)"),
            "taboo":       ("Taboo Words",
                            "Words on this list are masked or hidden in student reviews and earn warnings."),
            "reviews":     ("Reviews (authors visible)",
                            "Authors are only revealed here — everywhere else in the app, "
                            "reviews appear anonymously. Hidden reviews (those that tripped "
                            "the ≥3 taboo-word rule) show up too, tagged [hidden]."),
            "complaints":  ("Complaints",
                            "Each complaint must be acted on: warn the target, warn the filer, or dismiss."),
            "grads":       ("Graduation Applications",
                            "Approve or reject graduation requests. Rejections issue a 'reckless application' warning."),
            "people":      ("People",
                            "Everyone in College0 at a glance: status, warnings, fines, GPA."),
        }
        header, subtitle = header_map.get(section, (section, ""))

        tk.Label(self, text=f"Registrar · {header}", bg=theme.BG, fg=theme.TEXT,
                 font=theme.FONT_H1).pack(anchor="w")
        if subtitle:
            tk.Label(self, text=subtitle, bg=theme.BG, fg=theme.MUTED,
                     font=theme.FONT, wraplength=950,
                     justify="left").pack(anchor="w", pady=(2, 6))

        body = tk.Frame(self, bg=theme.BG)
        body.pack(fill="both", expand=True, pady=(10, 0))
        self.body = body

        renderer = getattr(self, f"_render_{section}", self._not_found)
        renderer()

    # ----- helpers -----

    def _not_found(self):
        tk.Label(self.body, text=f"Unknown section: {self.section}",
                 bg=theme.BG).pack()

    def _panel(self, title: str = ""):
        p = tk.Frame(self.body, bg=theme.PANEL, highlightthickness=1,
                     highlightbackground=theme.BORDER, padx=14, pady=10)
        if title:
            tk.Label(p, text=title, bg=theme.PANEL, fg=theme.TEXT,
                     font=theme.FONT_H2).pack(anchor="w", pady=(0, 6))
        return p

    # ===== Applications =====

    def _render_apps(self):
        pending = models.list_applications("pending")
        decided = [a for a in models.list_applications() if a["status"] != "pending"][:8]

        top = self._panel("Pending applications")
        top.pack(fill="x")

        if not pending:
            tk.Label(top, text="(none)", bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w")
        for a in pending:
            row = tk.Frame(top, bg=theme.PANEL)
            row.pack(fill="x", pady=4)
            text = (f"[{a['apply_type'].upper()}] {a['full_name']} "
                    f"· GPA {a['gpa'] if a['gpa'] is not None else '–'}")
            if a["note"]:
                text += f" · “{a['note']}”"
            tk.Label(row, text=text, bg=theme.PANEL, fg=theme.TEXT,
                     font=theme.FONT, anchor="w").pack(side="left", padx=(0, 8))
            theme.make_button(row, text="Approve",
                              command=lambda a=a: self._decide(a, "accepted"),
                              bg=theme.GOOD, fg="white",
                              padx=10, pady=3).pack(side="right", padx=2)
            theme.make_button(row, text="Reject",
                              command=lambda a=a: self._decide(a, "rejected"),
                              bg=theme.BAD, fg="white",
                              padx=10, pady=3).pack(side="right", padx=2)

        # Recent.
        bot = self._panel("Recent decisions")
        bot.pack(fill="x", pady=(12, 0))
        if not decided:
            tk.Label(bot, text="(none yet)", bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w")
        for a in decided:
            tk.Label(bot,
                     text=f"#{a['id']} {a['full_name']} ({a['apply_type']}) "
                          f"→ {a['status']} · {a['decision_note'] or ''}",
                     bg=theme.PANEL, fg=theme.MUTED, anchor="w",
                     font=theme.FONT_SMALL).pack(fill="x", anchor="w")

    def _decide(self, app_row: dict, status: str):
        if app_row["apply_type"] == "student":
            auto_status, auto_note = rules.auto_decision_for_student_app(
                app_row["gpa"] or 0.0)
        else:
            auto_status, auto_note = "accepted", "Instructor application."

        # If the registrar's decision contradicts the auto rule for students, demand justification.
        decision_note = auto_note
        if app_row["apply_type"] == "student" and status != auto_status:
            j = simpledialog.askstring(
                "Justification required",
                f"The auto rule would {auto_status} this student "
                f"({auto_note}). Please justify the override:",
                parent=self,
            )
            if not j or not j.strip():
                self.app.toast_msg("Decision cancelled (no justification).", "warn")
                return
            decision_note = f"Registrar override: {j.strip()}"

        if status == "accepted":
            if app_row["apply_type"] == "student":
                uid, uname, pw = models.create_student_user(app_row["full_name"])
            else:
                uid, uname, pw = models.create_instructor_user(app_row["full_name"])
            decision_note += f" | username={uname} temp_password={pw}"
            self._show_credentials(app_row["full_name"], uname, pw)

        models.update_application(app_row["id"], status, decision_note)
        self.app.toast_msg(f"Application #{app_row['id']} {status}.")
        self.app.show("registrar_apps")

    def _show_credentials(self, name, uname, pw):
        messagebox.showinfo(
            "Credentials issued",
            f"Account created for {name}.\n\n"
            f"Username: {uname}\nTemporary password: {pw}\n\n"
            "They will be asked to change the password on first login.",
            parent=self,
        )

    # ===== Courses =====

    def _render_courses(self):
        sem = models.get_semester_state()
        if sem["phase"] != "setup":
            warn = tk.Label(self.body,
                            text=f"Editing courses is intended for the SETUP phase "
                                 f"(current: {sem['phase']}).",
                            bg=theme.BG, fg=theme.WARN, font=theme.FONT_BOLD)
            warn.pack(anchor="w", pady=(0, 8))

        # New course form.
        form = self._panel("Create a new course (current semester)")
        form.pack(fill="x")
        # _panel packs a title Label into `form`. The fields below use grid(),
        # and Tk forbids mixing pack/grid in the same parent — so nest a Frame
        # to be the grid container.
        grid_host = tk.Frame(form, bg=theme.PANEL)
        grid_host.pack(fill="x")

        labels = ["Code", "Title", "Day", "Start hr", "End hr", "Capacity"]
        entries = []
        for i, lab in enumerate(labels):
            tk.Label(grid_host, text=lab, bg=theme.PANEL, fg=theme.TEXT,
                     font=theme.FONT_SMALL).grid(row=0, column=i, sticky="w", padx=4)
            e = tk.Entry(grid_host, font=theme.FONT, width=12,
                         bg="white", fg=theme.TEXT, insertbackground=theme.TEXT)
            e.grid(row=1, column=i, padx=4, sticky="we")
            entries.append(e)

        # Instructor dropdown.
        instructors = [i for i in models.list_instructors() if i["status"] == "active"]
        tk.Label(grid_host, text="Instructor", bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT_SMALL).grid(row=0, column=6, sticky="w", padx=4)
        inst_var = tk.StringVar(value=(instructors[0]["full_name"] if instructors else ""))
        inst_menu = ttk.Combobox(grid_host, textvariable=inst_var, state="readonly",
                                 values=[i["full_name"] for i in instructors],
                                 width=18)
        inst_menu.grid(row=1, column=6, padx=4, sticky="we")

        def create():
            try:
                code, title, day, sh, eh, cap = (e.get().strip() for e in entries)
                sh_i, eh_i, cap_i = int(sh), int(eh), int(cap)
                if day not in ("Mon", "Tue", "Wed", "Thu", "Fri"):
                    raise ValueError("Day must be Mon-Fri.")
                if not (sh_i < eh_i):
                    raise ValueError("Start hour must be before end hour.")
                inst_id = next((i["id"] for i in instructors if i["full_name"] == inst_var.get()), None)
                models.create_course(code, title, inst_id, day, sh_i, eh_i, cap_i,
                                     sem["semester"])
                self.app.toast_msg(f"Course {code} created.")
                self.app.show("registrar_courses")
            except Exception as ex:
                self.app.toast_msg(f"Could not create course: {ex}", "bad")

        theme.make_button(grid_host, text="Create", command=create,
                          bg=theme.ACCENT, fg="white",
                          padx=14, pady=6).grid(row=1, column=7, padx=8)

        # Existing courses.
        list_panel = self._panel("Active courses this semester")
        list_panel.pack(fill="both", expand=True, pady=(10, 0))

        cols = ("code", "title", "instructor", "schedule", "cap", "enrolled", "status")
        tree = ttk.Treeview(list_panel, columns=cols, show="headings", height=10)
        for c, w in zip(cols, (70, 220, 140, 120, 60, 80, 90)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True)
        for c in models.list_courses(semester=sem["semester"]):
            enrolled = len(models.course_enrollments(c["id"], statuses=["enrolled"]))
            tree.insert("", "end",
                        values=(c["code"], c["title"], c["instructor_name"] or "—",
                                f"{c['day']} {c['start_hour']}-{c['end_hour']}",
                                c["capacity"], enrolled, c["status"]))

    # ===== Phase =====

    def _render_phase(self):
        state = models.get_semester_state()
        panel = self._panel("Semester phase control")
        panel.pack(fill="x")

        order = ["setup", "registration", "running", "grading"]
        order_label = "  →  ".join(
            f"[{p.upper()}]" if p == state["phase"] else p for p in order
        )
        tk.Label(panel, text=order_label, bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT_BOLD).pack(anchor="w", pady=(0, 8))

        info = (
            "• SETUP → Registration: opens registration\n"
            "• Registration → Running: auto-cancels courses with <3 students, "
            "warns instructors, students with <2 courses receive warnings.\n"
            "• Running → Grading: instructors may now post grades.\n"
            "• Grading → Setup (next semester): end-of-grading sweep "
            "(missing grades, class GPA flags, student GPA outcomes, honor roll, "
            "course rating warnings)."
        )
        tk.Label(panel, text=info, bg=theme.PANEL, fg=theme.MUTED,
                 font=theme.FONT_SMALL, justify="left", anchor="w").pack(anchor="w")

        row = tk.Frame(panel, bg=theme.PANEL)
        row.pack(anchor="w", pady=(10, 0))

        # Compute the next target phase.
        if state["phase"] == "grading":
            theme.make_button(row, text="Run end-of-grading sweep → next semester",
                              command=self._sweep_and_advance,
                              bg=theme.ACCENT, fg="white",
                              padx=14, pady=6).pack(side="left")
        else:
            idx = order.index(state["phase"])
            nxt = order[idx + 1] if idx + 1 < len(order) else None
            if nxt:
                theme.make_button(row, text=f"Advance to: {nxt.upper()}",
                                  command=lambda n=nxt: self._advance(n),
                                  bg=theme.ACCENT, fg="white",
                                  padx=14, pady=6).pack(side="left")

        # Show last event log (stored in setting).
        events_text = models.get_setting("last_phase_events", "")
        if events_text:
            log = self._panel("Latest rule events")
            log.pack(fill="both", expand=True, pady=(10, 0))
            tk.Label(log, text=events_text, bg=theme.PANEL, fg=theme.TEXT,
                     font=theme.FONT, justify="left", anchor="w",
                     wraplength=900).pack(anchor="w")

        # Instructor review flags.
        flags = models.get_setting("instructor_review_flags", "")
        if flags:
            flag_panel = self._panel("Instructor class-GPA review flags")
            flag_panel.pack(fill="x", pady=(10, 0))
            tk.Label(flag_panel, text=flags, bg=theme.PANEL, fg=theme.WARN,
                     font=theme.FONT, justify="left", wraplength=900).pack(anchor="w")
            self._add_inst_warn_buttons(flag_panel)

    def _add_inst_warn_buttons(self, parent):
        bar = tk.Frame(parent, bg=theme.PANEL)
        bar.pack(anchor="w", pady=(6, 0))
        instructors = models.list_instructors()
        var = tk.StringVar(value=instructors[0]["full_name"] if instructors else "")
        ttk.Combobox(bar, textvariable=var, state="readonly",
                     values=[i["full_name"] for i in instructors],
                     width=22).pack(side="left", padx=(0, 6))

        def warn():
            target = next((i for i in instructors if i["full_name"] == var.get()), None)
            if target:
                rules.warn_count_increment(target["id"],
                                           "Class-GPA out of band (registrar review).")
                self.app.toast_msg(f"{target['full_name']} warned.", "warn")
                self.app.show("registrar_phase")

        def fire():
            target = next((i for i in instructors if i["full_name"] == var.get()), None)
            if target:
                models.set_status(target["id"], "fired")
                self.app.toast_msg(f"{target['full_name']} fired.", "bad")
                self.app.show("registrar_phase")

        theme.make_button(bar, text="Warn", command=warn,
                          bg=theme.WARN, fg="white",
                          padx=10, pady=3).pack(side="left", padx=2)
        theme.make_button(bar, text="Fire", command=fire,
                          bg=theme.BAD, fg="white",
                          padx=10, pady=3).pack(side="left", padx=2)

    def _advance(self, target: str):
        r = rules.advance_phase(target)
        if r.get("error"):
            self.app.toast_msg(r["error"], "bad")
            return
        events = "\n".join(r.get("events", [])) or "(no automatic events fired)"
        models.set_setting("last_phase_events", events)
        self.app.toast_msg(f"Phase → {target}")
        self.app.show("registrar_phase")

    def _sweep_and_advance(self):
        events = rules.end_of_grading_sweep()
        # advance_semester now returns its own events (reinstated suspensions).
        events += models.advance_semester()
        models.set_setting("last_phase_events", "\n".join(events) or "(no events)")
        self.app.toast_msg("Sweep complete · new semester begun.")
        self.app.show("registrar_phase")

    # ===== Taboo words =====

    def _render_taboo(self):
        panel = self._panel("Taboo word list")
        panel.pack(fill="both", expand=True)
        words = models.list_taboo_words()
        list_box = tk.Listbox(panel, font=theme.FONT, height=10,
                              bg="white", fg=theme.TEXT,
                              selectbackground=theme.ACCENT, selectforeground="white")
        for w in words:
            list_box.insert("end", w)
        list_box.pack(fill="both", expand=True, pady=(0, 8))

        row = tk.Frame(panel, bg=theme.PANEL)
        row.pack(fill="x")
        new_entry = tk.Entry(row, font=theme.FONT, width=24,
                             bg="white", fg=theme.TEXT, insertbackground=theme.TEXT)
        new_entry.pack(side="left", padx=(0, 6))

        def add():
            w = new_entry.get().strip()
            if not w:
                self.app.toast_msg("Enter a word first.", "warn")
                return
            models.add_taboo_word(w)
            self.app.toast_msg(f"Added '{w}' to taboo list.")
            self.app.show("registrar_taboo")

        def remove():
            try:
                w = list_box.get(list_box.curselection()[0])
            except Exception:
                self.app.toast_msg("Select a word to remove.", "warn")
                return
            models.remove_taboo_word(w)
            self.app.toast_msg(f"Removed '{w}'.")
            self.app.show("registrar_taboo")

        theme.make_button(row, text="Add", command=add,
                          bg=theme.ACCENT, fg="white",
                          padx=12, pady=4).pack(side="left", padx=2)
        theme.make_button(row, text="Remove selected", command=remove,
                          bg=theme.BAD, fg="white",
                          padx=12, pady=4).pack(side="left", padx=2)

    # ===== Reviews (authorship visible to registrar only) =====

    def _render_reviews(self):
        # Group every review (including the hidden ones) by course and
        # show the author's name. This is the only view in the whole app
        # that does that — everywhere else, ratings are anonymous.
        courses = models.list_courses()
        # Sort: current-semester active first, then everything else.
        state = models.get_semester_state()
        courses.sort(key=lambda c: (c["semester"] != state["semester"], c["code"]))

        any_reviews = False
        for c in courses:
            reviews = models.reviews_for_course(c["id"], include_hidden=True)
            if not reviews:
                continue
            any_reviews = True
            avg = models.avg_rating(c["id"]) or 0
            panel = self._panel(
                f"{c['code']} · {c['title']}  (sem {c['semester']}, "
                f"avg {avg:.2f}/5, {len(reviews)} review(s))"
            )
            panel.pack(fill="x", pady=(0, 8))
            for r in reviews:
                row = tk.Frame(panel, bg=theme.PANEL,
                               highlightthickness=1, highlightbackground=theme.BORDER,
                               padx=10, pady=6)
                row.pack(fill="x", pady=3)
                tag = "[HIDDEN]" if r["visible"] == 0 else ""
                head = (f"{r['full_name']}  ·  {r['stars']}/5  ·  "
                        f"{r['created_at']}  {tag}")
                tk.Label(row, text=head, bg=theme.PANEL,
                         fg=(theme.BAD if r["visible"] == 0 else theme.TEXT),
                         font=theme.FONT_BOLD).pack(anchor="w")
                tk.Label(row, text=r["body"], bg=theme.PANEL, fg=theme.MUTED,
                         font=theme.FONT, wraplength=900,
                         justify="left").pack(anchor="w", pady=(2, 0))

        if not any_reviews:
            tk.Label(self.body, text="(no reviews yet)", bg=theme.BG,
                     fg=theme.MUTED).pack(anchor="w")

    # ===== Complaints =====

    def _render_complaints(self):
        panel = self._panel("Open complaints")
        panel.pack(fill="x")
        opens = models.list_complaints("open")
        if not opens:
            tk.Label(panel, text="(none)", bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w")
        for cmp_ in opens:
            row = tk.Frame(panel, bg=theme.PANEL,
                           highlightthickness=1, highlightbackground=theme.BORDER,
                           padx=10, pady=6)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=f"From {cmp_['from_name']} against "
                              f"{cmp_['against_name'] or '?'} ({cmp_['against_role']})",
                     bg=theme.PANEL, fg=theme.TEXT, font=theme.FONT_BOLD,
                     anchor="w").pack(fill="x", anchor="w")
            tk.Label(row, text=cmp_["body"], bg=theme.PANEL, fg=theme.MUTED,
                     font=theme.FONT, wraplength=900,
                     justify="left").pack(anchor="w", pady=(2, 6))

            btn_row = tk.Frame(row, bg=theme.PANEL)
            btn_row.pack(anchor="w")
            theme.make_button(btn_row, text="Warn target",
                              command=lambda c=cmp_: self._cmp_act(c, "warn_target"),
                              bg=theme.WARN, fg="white",
                              padx=10, pady=3).pack(side="left", padx=2)
            theme.make_button(btn_row, text="Warn filer",
                              command=lambda c=cmp_: self._cmp_act(c, "warn_filer"),
                              bg=theme.WARN, fg="white",
                              padx=10, pady=3).pack(side="left", padx=2)
            theme.make_button(btn_row, text="Dismiss",
                              command=lambda c=cmp_: self._cmp_act(c, "dismissed"),
                              bg=theme.MUTED, fg="white",
                              padx=10, pady=3).pack(side="left", padx=2)

        # History.
        hist = self._panel("Resolved (recent)")
        hist.pack(fill="x", pady=(12, 0))
        resolved = [c for c in models.list_complaints() if c["status"] == "resolved"][:6]
        if not resolved:
            tk.Label(hist, text="(none)", bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w")
        for c in resolved:
            tk.Label(hist,
                     text=f"#{c['id']} {c['from_name']} → {c['against_name']} "
                          f"· action: {c['action']}",
                     bg=theme.PANEL, fg=theme.MUTED,
                     font=theme.FONT_SMALL, anchor="w").pack(fill="x", anchor="w")

    def _cmp_act(self, c: dict, action: str):
        if action == "warn_target" and c["against_user_id"]:
            rules.warn_count_increment(c["against_user_id"],
                                       f"Complaint #{c['id']} upheld.")
        elif action == "warn_filer":
            rules.warn_count_increment(c["from_user_id"],
                                       f"Complaint #{c['id']} unfounded.")
        models.resolve_complaint(c["id"], action)
        self.app.toast_msg(f"Complaint #{c['id']} → {action}.")
        self.app.show("registrar_complaints")

    # ===== Graduations =====

    def _render_grads(self):
        panel = self._panel("Pending graduation applications")
        panel.pack(fill="x")
        pending = models.list_graduation_apps("pending")
        if not pending:
            tk.Label(panel, text="(none)", bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w")
        for g in pending:
            row = tk.Frame(panel, bg=theme.PANEL)
            row.pack(fill="x", pady=3)
            req = rules.check_graduation(g["student_id"])
            tag = "OK" if req["ok"] else "MISSING"
            tk.Label(row,
                     text=f"#{g['id']}  {g['full_name']}   [{tag}: {req['msg']}]",
                     bg=theme.PANEL, fg=theme.TEXT,
                     font=theme.FONT, anchor="w").pack(side="left")
            theme.make_button(row, text="Approve",
                              command=lambda g=g, m=req["msg"]: self._grad_decide(g, "approved", m),
                              bg=theme.GOOD, fg="white",
                              padx=10, pady=3).pack(side="right", padx=2)
            theme.make_button(row, text="Reject",
                              command=lambda g=g, m=req["msg"]: self._grad_decide(g, "rejected", m),
                              bg=theme.BAD, fg="white",
                              padx=10, pady=3).pack(side="right", padx=2)

        recent = self._panel("Recent graduation decisions")
        recent.pack(fill="x", pady=(10, 0))
        all_g = [g for g in models.list_graduation_apps() if g["status"] != "pending"][:5]
        if not all_g:
            tk.Label(recent, text="(none yet)", bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w")
        for g in all_g:
            tk.Label(recent, text=f"#{g['id']} {g['full_name']} → {g['status']} ({g['note']})",
                     bg=theme.PANEL, fg=theme.MUTED, font=theme.FONT_SMALL,
                     anchor="w").pack(fill="x", anchor="w")

    def _grad_decide(self, g: dict, status: str, msg: str):
        models.decide_graduation(g["id"], status, msg)
        if status == "approved":
            models.set_status(g["student_id"], "graduated")
            self.app.toast_msg(f"{g['full_name']} graduated.")
        else:
            rules.warn_count_increment(g["student_id"], "Reckless graduation application.")
            self.app.toast_msg(f"{g['full_name']} rejected + 1 warning.", "warn")
        self.app.show("registrar_grads")

    # ===== People =====

    def _render_people(self):
        panel = self._panel("Everyone in the system")
        panel.pack(fill="both", expand=True)

        tk.Label(panel,
                 text="As the registrar you have full visibility into every account. "
                      "Select a student row and click \"View transcript\" (or "
                      "double-click) to drill into their full record.",
                 bg=theme.PANEL, fg=theme.MUTED, font=theme.FONT_SMALL,
                 wraplength=900, justify="left").pack(anchor="w", pady=(0, 6))

        cols = ("role", "name", "username", "warnings", "status", "extra")
        tree = ttk.Treeview(panel, columns=cols, show="headings", height=18)
        for c, w in zip(cols, (90, 180, 120, 80, 110, 220)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True)

        # Map row iid -> user dict so we can open a detail popup later.
        row_to_user: dict[str, dict] = {}
        for u in models.list_users():
            extra = ""
            if u["role"] == "student":
                with connect() as c:
                    r = c.execute("SELECT gpa, courses_completed, honors FROM students WHERE user_id=?",
                                  (u["id"],)).fetchone()
                if r:
                    extra = f"GPA {r['gpa']} · {r['courses_completed']} done · {r['honors']} honors"
            if u["fine_due"]:
                extra += f" · fine ${u['fine_due']:.0f}"
            iid = tree.insert("", "end",
                              values=(u["role"], u["full_name"], u["username"],
                                      u["warnings"], u["status"], extra))
            row_to_user[iid] = u

        def open_selected(_evt=None):
            sel = tree.selection()
            if not sel:
                self.app.toast_msg("Select a row first.", "warn")
                return
            u = row_to_user.get(sel[0])
            if not u:
                return
            self._open_user_detail(u)

        tree.bind("<Double-1>", open_selected)

        btn_row = tk.Frame(panel, bg=theme.PANEL)
        btn_row.pack(fill="x", pady=(8, 0))
        theme.make_button(btn_row, text="View transcript",
                          command=open_selected,
                          bg=theme.ACCENT, fg="white",
                          padx=14, pady=4).pack(side="left")

    def _open_user_detail(self, user: dict):
        """Popup window with the user's full record.

        For students this is their transcript + summary; for instructors it
        is the list of courses they have taught.
        """
        win = tk.Toplevel(self)
        win.title(f"{user['full_name']} — {user['role']}")
        win.configure(bg=theme.BG)
        win.geometry("760x520")

        # Header.
        head = tk.Frame(win, bg=theme.BG, padx=16, pady=12)
        head.pack(fill="x")
        tk.Label(head, text=user["full_name"], bg=theme.BG, fg=theme.TEXT,
                 font=theme.FONT_H1).pack(anchor="w")
        sub = (f"{user['role']} · username {user['username']} · "
               f"status {user['status']} · warnings {user['warnings']}")
        if user.get("fine_due"):
            sub += f" · fine ${user['fine_due']:.0f}"
        tk.Label(head, text=sub, bg=theme.BG, fg=theme.MUTED,
                 font=theme.FONT).pack(anchor="w")

        body = tk.Frame(win, bg=theme.BG, padx=16, pady=8)
        body.pack(fill="both", expand=True)

        if user["role"] == "student":
            with connect() as c:
                r = c.execute(
                    "SELECT gpa, semester_gpa, courses_completed, honors, "
                    "semesters_completed FROM students WHERE user_id=?",
                    (user["id"],),
                ).fetchone()
            if r:
                tk.Label(body,
                         text=(f"Overall GPA {r['gpa']:.2f}  ·  "
                               f"Semester GPA {r['semester_gpa']:.2f}  ·  "
                               f"{r['courses_completed']} courses completed  ·  "
                               f"{r['honors']} honors  ·  "
                               f"{r['semesters_completed']} semester(s) on record"),
                         bg=theme.BG, fg=theme.TEXT,
                         font=theme.FONT_BOLD).pack(anchor="w", pady=(0, 8))

            tk.Label(body, text="Transcript", bg=theme.BG, fg=theme.TEXT,
                     font=theme.FONT_H2).pack(anchor="w")
            cols = ("semester", "code", "title", "status", "grade")
            tree = ttk.Treeview(body, columns=cols, show="headings", height=10)
            for c, w in zip(cols, (80, 80, 280, 100, 60)):
                tree.heading(c, text=c.title())
                tree.column(c, width=w, anchor="w")
            tree.pack(fill="both", expand=True)
            history = models.student_history(user["id"])
            if not history:
                tk.Label(body, text="(no completed history yet)",
                         bg=theme.BG, fg=theme.MUTED).pack(anchor="w")
            for h in history:
                tree.insert("", "end",
                            values=(h["semester"], h["code"], h["title"],
                                    h["status"], h["grade"] or "—"))

            # Current-semester enrollment.
            sem = models.get_semester_state()["semester"]
            cur = models.student_enrollments(user["id"], semester=sem,
                                              statuses=["enrolled", "waitlist"])
            tk.Label(body, text=f"Current semester ({sem}) enrolments",
                     bg=theme.BG, fg=theme.TEXT,
                     font=theme.FONT_H2).pack(anchor="w", pady=(10, 2))
            if not cur:
                tk.Label(body, text="  (none)", bg=theme.BG,
                         fg=theme.MUTED).pack(anchor="w")
            for e in cur:
                tk.Label(body,
                         text=f"  • {e['code']} {e['title']} "
                              f"({e['day']} {e['start_hour']}-{e['end_hour']}) "
                              f"[{e['status']}]",
                         bg=theme.BG, fg=theme.TEXT,
                         font=theme.FONT).pack(anchor="w")
        elif user["role"] == "instructor":
            tk.Label(body, text="Courses taught", bg=theme.BG, fg=theme.TEXT,
                     font=theme.FONT_H2).pack(anchor="w")
            cols = ("semester", "code", "title", "status", "enrolled")
            tree = ttk.Treeview(body, columns=cols, show="headings", height=10)
            for c, w in zip(cols, (80, 80, 280, 100, 80)):
                tree.heading(c, text=c.title())
                tree.column(c, width=w, anchor="w")
            tree.pack(fill="both", expand=True)
            taught = [c for c in models.list_courses()
                      if c["instructor_id"] == user["id"]]
            if not taught:
                tk.Label(body, text="(no courses on record)",
                         bg=theme.BG, fg=theme.MUTED).pack(anchor="w")
            for c in taught:
                n = len(models.course_enrollments(c["id"],
                                                   statuses=["enrolled"]))
                tree.insert("", "end",
                            values=(c["semester"], c["code"], c["title"],
                                    c["status"], n))
        else:
            tk.Label(body,
                     text="Registrar account — no transcript or roster.",
                     bg=theme.BG, fg=theme.MUTED).pack(anchor="w")

        # Warning history is useful for any role.
        warns = models.list_warnings(user["id"])
        if warns:
            tk.Label(body, text="Warning history", bg=theme.BG, fg=theme.TEXT,
                     font=theme.FONT_H2).pack(anchor="w", pady=(10, 2))
            for w in warns:
                tk.Label(body, text=f"  • {w['created_at']} — {w['reason']}",
                         bg=theme.BG, fg=theme.MUTED,
                         font=theme.FONT_SMALL, anchor="w",
                         wraplength=700, justify="left").pack(fill="x", anchor="w")

        theme.make_button(win, text="Close", command=win.destroy,
                          bg=theme.MUTED, fg="white",
                          padx=14, pady=4).pack(pady=10)
