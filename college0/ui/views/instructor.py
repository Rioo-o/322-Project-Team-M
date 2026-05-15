"""Instructor dashboard."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from core import models, rules
from core.db import connect
from .. import theme

GRADE_CHOICES = ["", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "F"]


class InstructorView(tk.Frame):
    def __init__(self, parent, app, section: str):
        super().__init__(parent, bg=theme.BG, padx=20, pady=14)
        self.app = app
        self.section = section

        # Hard banner for suspended / fired instructors — they can still
        # log in (to track their reinstatement) but should know they
        # cannot teach.
        if app.user.get("status") in ("suspended", "fired"):
            self._hard_status_banner()

        header_map = {
            "classes":   ("My Classes & Roster",
                          "Only the courses you are assigned to show up here. "
                          "Each enrolled student shows their basic info + summary academic "
                          "record (GPA, courses done, honors). Admit waitlisted students with one click."),
            "records":   ("Student Records",
                          "Basic info and academic history for every student in your "
                          "classes this semester. Each row expands to the full transcript."),
            "grades":    ("Grade Entry",
                          "Available only during the GRADING phase. Pick a grade, click Save. GPAs recompute live."),
            "complaint": ("File a Complaint",
                          "Asks the registrar to act on a student. The registrar must either punish the student or you."),
        }
        title, subtitle = header_map.get(section, (section, ""))
        tk.Label(self, text=f"Instructor · {title}", bg=theme.BG,
                 fg=theme.TEXT, font=theme.FONT_H1).pack(anchor="w")
        if subtitle:
            tk.Label(self, text=subtitle, bg=theme.BG, fg=theme.MUTED,
                     font=theme.FONT, wraplength=950,
                     justify="left").pack(anchor="w", pady=(2, 6))

        getattr(self, f"_render_{section}", self._not_found)()

    def _not_found(self):
        tk.Label(self, text=f"Unknown section: {self.section}", bg=theme.BG).pack()

    def _hard_status_banner(self):
        status = self.app.user["status"]
        until = self.app.user.get("suspended_until_semester")
        if status == "suspended":
            msg = ("You are SUSPENDED for this semester and won't be assigned "
                   "any classes next semester either. You can still sign in to "
                   "monitor your record in the meantime. ")
            if until:
                msg += (f"You will be automatically reinstated when the "
                        f"registrar advances to semester {until}.")
        else:  # fired
            msg = ("You have been FIRED. Please contact the registrar — "
                   "your account is read-only.")
        box = tk.Frame(self, bg="#fff1f0", highlightthickness=2,
                       highlightbackground=theme.BAD, padx=14, pady=10)
        box.pack(fill="x", pady=(0, 10))
        tk.Label(box, text=f"Account status: {status.upper()}",
                 bg="#fff1f0", fg=theme.BAD, font=theme.FONT_H2).pack(anchor="w")
        tk.Label(box, text=msg, bg="#fff1f0", fg=theme.TEXT,
                 font=theme.FONT, wraplength=900,
                 justify="left").pack(anchor="w")

    def _panel(self, title=""):
        p = tk.Frame(self, bg=theme.PANEL, highlightthickness=1,
                     highlightbackground=theme.BORDER, padx=14, pady=10)
        if title:
            tk.Label(p, text=title, bg=theme.PANEL, fg=theme.TEXT,
                     font=theme.FONT_H2).pack(anchor="w", pady=(0, 4))
        return p

    # ----- classes / roster -----

    def _render_classes(self):
        sem = models.get_semester_state()["semester"]
        my_courses = [c for c in models.list_courses(semester=sem)
                      if c["instructor_id"] == self.app.user["id"]]

        if not my_courses:
            tk.Label(self, text="You aren't assigned to any class this semester.",
                     bg=theme.BG, fg=theme.MUTED, font=theme.FONT).pack(anchor="w",
                                                                          pady=10)
            return

        for c in my_courses:
            panel = self._panel(f"{c['code']} · {c['title']}  "
                                f"({c['day']} {c['start_hour']}-{c['end_hour']}, "
                                f"cap {c['capacity']}, status {c['status']})")
            panel.pack(fill="x", pady=(0, 10))

            enrolled = models.course_enrollments(c["id"], statuses=["enrolled"])
            waitlist = models.course_enrollments(c["id"], statuses=["waitlist"])

            tk.Label(panel, text=f"Enrolled ({len(enrolled)}):", bg=theme.PANEL,
                     fg=theme.TEXT, font=theme.FONT_BOLD).pack(anchor="w")
            if not enrolled:
                tk.Label(panel, text="  (no students yet)",
                         bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w")
            # Index academic info by student id so we can show it inline.
            records = {s["id"]: s for s in models.list_students()}
            for e in enrolled:
                line = tk.Frame(panel, bg=theme.PANEL)
                line.pack(fill="x", anchor="w")
                rec = records.get(e["student_user_id"]) or {}
                summary = (f"GPA {rec.get('gpa', 0):.2f} · "
                           f"{rec.get('courses_completed', 0)} done · "
                           f"{rec.get('honors', 0)} honors")
                tk.Label(line, text=f"  • {e['full_name']}  ({summary})  "
                                    f"grade: {e['grade'] or '—'}",
                         bg=theme.PANEL, fg=theme.TEXT,
                         font=theme.FONT).pack(side="left")

            tk.Label(panel, text=f"Waitlist ({len(waitlist)}):", bg=theme.PANEL,
                     fg=theme.TEXT, font=theme.FONT_BOLD).pack(anchor="w", pady=(8, 0))
            if not waitlist:
                tk.Label(panel, text="  (none)",
                         bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w")
            for e in waitlist:
                line = tk.Frame(panel, bg=theme.PANEL)
                line.pack(fill="x", anchor="w")
                tk.Label(line, text=f"  • {e['full_name']}",
                         bg=theme.PANEL, fg=theme.TEXT,
                         font=theme.FONT).pack(side="left")
                theme.make_button(line, text="Admit",
                                  command=lambda eid=e["id"]: self._admit(eid),
                                  bg=theme.ACCENT, fg="white",
                                  padx=8, pady=2).pack(side="left", padx=6)

    def _admit(self, enrollment_id: int):
        models.update_enrollment_status(enrollment_id, "enrolled")
        self.app.toast_msg("Student admitted from waitlist.")
        self.app.show("instr_classes")

    # ----- student records (basic info + full transcript) -----

    def _render_records(self):
        sem = models.get_semester_state()["semester"]
        my_courses = [c for c in models.list_courses(semester=sem)
                      if c["instructor_id"] == self.app.user["id"]]
        if not my_courses:
            tk.Label(self, text="You aren't assigned to any class this semester.",
                     bg=theme.BG, fg=theme.MUTED, font=theme.FONT).pack(anchor="w",
                                                                          pady=10)
            return

        # Collect the unique set of students across all the instructor's classes.
        seen: dict[int, dict] = {}
        for c in my_courses:
            for e in models.course_enrollments(c["id"],
                                                statuses=["enrolled", "completed",
                                                          "failed"]):
                seen.setdefault(e["student_user_id"], {"name": e["full_name"]})

        if not seen:
            tk.Label(self, text="No students enrolled in your classes yet.",
                     bg=theme.BG, fg=theme.MUTED).pack(anchor="w", pady=10)
            return

        # Per-student panel: basic info + summary + transcript.
        students_by_id = {s["id"]: s for s in models.list_students()}
        for sid, info in seen.items():
            rec = students_by_id.get(sid, {})
            user = models.get_user(sid) or {}

            panel = self._panel(info["name"])
            panel.pack(fill="x", pady=(0, 10))

            basic = (
                f"Username: {user.get('username', '?')}  ·  "
                f"Status: {user.get('status', '?')}  ·  "
                f"Warnings: {user.get('warnings', 0)}"
            )
            tk.Label(panel, text=basic, bg=theme.PANEL, fg=theme.MUTED,
                     font=theme.FONT_SMALL).pack(anchor="w")

            summary = (
                f"GPA {rec.get('gpa', 0):.2f}  ·  "
                f"Semester GPA {rec.get('semester_gpa', 0):.2f}  ·  "
                f"{rec.get('courses_completed', 0)} courses completed  ·  "
                f"{rec.get('honors', 0)} honors"
            )
            tk.Label(panel, text=summary, bg=theme.PANEL, fg=theme.TEXT,
                     font=theme.FONT_BOLD).pack(anchor="w", pady=(2, 6))

            # Transcript table.
            history = models.student_history(sid)
            if not history:
                tk.Label(panel, text="(no completed history yet)",
                         bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w")
                continue

            cols = ("semester", "code", "title", "status", "grade")
            tree = ttk.Treeview(panel, columns=cols, show="headings",
                                height=min(6, max(2, len(history))))
            for c, w in zip(cols, (80, 80, 240, 100, 60)):
                tree.heading(c, text=c.title())
                tree.column(c, width=w, anchor="w")
            tree.pack(fill="x")
            for h in history:
                tree.insert("", "end",
                            values=(h["semester"], h["code"], h["title"],
                                    h["status"], h["grade"] or "—"))

    # ----- grades -----

    def _render_grades(self):
        state = models.get_semester_state()
        if state["phase"] != "grading":
            tk.Label(self,
                     text=f"Grading is only allowed during the GRADING phase "
                          f"(current: {state['phase']}).",
                     bg=theme.BG, fg=theme.WARN, font=theme.FONT_BOLD).pack(anchor="w",
                                                                             pady=8)
            return

        my_courses = [c for c in models.list_courses(semester=state["semester"],
                                                     only_active=True)
                      if c["instructor_id"] == self.app.user["id"]]
        if not my_courses:
            tk.Label(self, text="No active classes to grade.",
                     bg=theme.BG, fg=theme.MUTED).pack(anchor="w")
            return

        for c in my_courses:
            panel = self._panel(f"{c['code']} · {c['title']}")
            panel.pack(fill="x", pady=6)

            for e in models.course_enrollments(c["id"], statuses=["enrolled", "completed", "failed"]):
                row = tk.Frame(panel, bg=theme.PANEL)
                row.pack(fill="x", anchor="w", pady=2)
                tk.Label(row, text=e["full_name"], bg=theme.PANEL,
                         fg=theme.TEXT,
                         font=theme.FONT, width=24,
                         anchor="w").pack(side="left")
                var = tk.StringVar(value=e["grade"] or "")
                cb = ttk.Combobox(row, textvariable=var, state="readonly",
                                  values=GRADE_CHOICES, width=6)
                cb.pack(side="left", padx=4)
                theme.make_button(row, text="Save",
                                  command=lambda eid=e["id"], v=var: self._save_grade(eid, v.get()),
                                  bg=theme.ACCENT, fg="white",
                                  padx=10, pady=2).pack(side="left", padx=4)

    def _save_grade(self, enrollment_id: int, grade: str):
        if not grade:
            self.app.toast_msg("Pick a grade first.", "warn")
            return
        models.set_grade(enrollment_id, grade)
        # Recompute the student's GPA on each save so it shows up live.
        with connect() as c:
            sid = c.execute("SELECT student_id FROM enrollments WHERE id=?",
                            (enrollment_id,)).fetchone()[0]
        rules.recompute_student_gpa(sid)
        self.app.toast_msg(f"Grade {grade} saved.")

    # ----- complaint -----

    def _render_complaint(self):
        panel = self._panel("File a complaint about a student")
        panel.pack(fill="x")

        # Spec scoping: an instructor can only complain about a student in
        # one of their current classes (i.e., they share a course).
        sem = models.get_semester_state()["semester"]
        my_courses = [c for c in models.list_courses(semester=sem)
                      if c["instructor_id"] == self.app.user["id"]]
        student_ids: set[int] = set()
        for c in my_courses:
            for e in models.course_enrollments(
                    c["id"], statuses=["enrolled", "waitlist"]):
                student_ids.add(e["student_user_id"])
        students = [s for s in models.list_students() if s["id"] in student_ids]
        if not students:
            tk.Label(panel,
                     text="You can only complain about students currently in "
                          "one of your classes — your roster is empty right now.",
                     bg=theme.PANEL, fg=theme.MUTED, wraplength=900,
                     justify="left").pack(anchor="w")
            return
        var = tk.StringVar(value=students[0]["full_name"])
        tk.Label(panel, text="Student:", bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT).pack(anchor="w")
        ttk.Combobox(panel, textvariable=var, state="readonly",
                     values=[s["full_name"] for s in students],
                     width=30).pack(anchor="w", pady=(0, 8))
        tk.Label(panel, text="Reason:", bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT).pack(anchor="w")
        body = tk.Text(panel, font=theme.FONT, height=5, width=80,
                       bg="white", fg=theme.TEXT, insertbackground=theme.TEXT)
        body.pack(anchor="w", pady=(0, 8))

        def submit():
            target = next((s for s in students if s["full_name"] == var.get()), None)
            text = body.get("1.0", "end").strip()
            if not target or not text:
                self.app.toast_msg("Pick a student and write a reason.", "bad")
                return
            models.add_complaint(self.app.user["id"], target["id"],
                                 "student", text)
            self.app.toast_msg("Complaint filed. The registrar must take action.")
            body.delete("1.0", "end")

        theme.make_button(panel, text="Submit complaint", command=submit,
                          bg=theme.ACCENT, fg="white",
                          padx=14, pady=6).pack(anchor="w")
