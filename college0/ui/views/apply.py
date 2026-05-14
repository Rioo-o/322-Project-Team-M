"""Visitor application form (student or instructor)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from core import models
from .. import theme


class ApplyView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG, padx=24, pady=18)
        self.app = app

        tk.Label(self, text="Apply to College0", bg=theme.BG, fg=theme.TEXT,
                 font=theme.FONT_H1).pack(anchor="w")
        tk.Label(self,
                 text=("Submit an application as a Student or an Instructor. "
                       "Student applicants with GPA ≥ 3.0 are auto-accepted if the quota allows."),
                 bg=theme.BG, fg=theme.MUTED, font=theme.FONT,
                 wraplength=900, justify="left").pack(anchor="w", pady=(4, 14))

        card = tk.Frame(self, bg=theme.PANEL, highlightthickness=1,
                        highlightbackground=theme.BORDER, padx=24, pady=20)
        card.pack(fill="x")

        # Type
        tk.Label(card, text="I want to apply as a:", bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT_BOLD).grid(row=0, column=0, sticky="w")
        self.type_var = tk.StringVar(value="student")
        # tk.Radiobutton's `text` argument is rendered by the native widget on
        # macOS and inherits the system text color, which can disappear against
        # a white panel. We pass text="" and place a separate Label next to it
        # so we can control fg explicitly.
        stu_row = tk.Frame(card, bg=theme.PANEL)
        stu_row.grid(row=0, column=1, sticky="w", padx=10)
        tk.Radiobutton(stu_row, text="", variable=self.type_var, value="student",
                       bg=theme.PANEL, command=self._toggle_gpa).pack(side="left")
        tk.Label(stu_row, text="Student", bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT).pack(side="left")

        ins_row = tk.Frame(card, bg=theme.PANEL)
        ins_row.grid(row=0, column=2, sticky="w")
        tk.Radiobutton(ins_row, text="", variable=self.type_var, value="instructor",
                       bg=theme.PANEL, command=self._toggle_gpa).pack(side="left")
        tk.Label(ins_row, text="Instructor", bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT).pack(side="left")

        tk.Label(card, text="Full name", bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT).grid(row=1, column=0, sticky="w", pady=(14, 2))
        self.name_entry = tk.Entry(card, font=theme.FONT, width=42,
                                   bg="white", fg=theme.TEXT, insertbackground=theme.TEXT)
        self.name_entry.grid(row=2, column=0, columnspan=3, sticky="we")

        self.gpa_lbl = tk.Label(card, text="Undergraduate GPA (0.0 - 4.0)",
                                bg=theme.PANEL, fg=theme.TEXT, font=theme.FONT)
        self.gpa_lbl.grid(row=3, column=0, sticky="w", pady=(12, 2))
        self.gpa_entry = tk.Entry(card, font=theme.FONT, width=10,
                                  bg="white", fg=theme.TEXT, insertbackground=theme.TEXT)
        self.gpa_entry.grid(row=4, column=0, sticky="w")

        tk.Label(card, text="Note (optional)", bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT).grid(row=5, column=0, sticky="w", pady=(12, 2))
        self.note_entry = tk.Text(card, font=theme.FONT, height=4, width=60,
                                  bg="white", fg=theme.TEXT, insertbackground=theme.TEXT)
        self.note_entry.grid(row=6, column=0, columnspan=3, sticky="we")

        theme.make_button(card, text="Submit application",
                          command=self._submit,
                          bg=theme.ACCENT, fg="white",
                          padx=14, pady=8).grid(row=7, column=0,
                                                sticky="w", pady=(16, 0))

        self.msg = tk.Label(self, text="", bg=theme.BG, fg=theme.GOOD,
                            font=theme.FONT, wraplength=900, justify="left")
        self.msg.pack(anchor="w", pady=12)

    def _toggle_gpa(self):
        if self.type_var.get() == "instructor":
            self.gpa_entry.configure(state="disabled")
            self.gpa_lbl.configure(fg=theme.MUTED, text="(GPA not required for instructors)")
        else:
            self.gpa_entry.configure(state="normal")
            self.gpa_lbl.configure(fg=theme.TEXT, text="Undergraduate GPA (0.0 - 4.0)")

    def _submit(self):
        name = self.name_entry.get().strip()
        if not name:
            self.msg.config(text="Please enter your name.", fg=theme.BAD)
            return
        gpa = None
        if self.type_var.get() == "student":
            try:
                gpa = float(self.gpa_entry.get())
                if gpa < 0 or gpa > 4:
                    raise ValueError
            except ValueError:
                self.msg.config(text="Enter a GPA between 0.0 and 4.0.", fg=theme.BAD)
                return
        note = self.note_entry.get("1.0", "end").strip()
        models.create_application(self.type_var.get(), name, gpa, note)
        self.msg.config(
            text=("Application submitted. The registrar will review it. "
                  "If accepted, your student ID and a temporary password will be issued."),
            fg=theme.GOOD,
        )
        self.name_entry.delete(0, "end")
        self.gpa_entry.delete(0, "end")
        self.note_entry.delete("1.0", "end")
