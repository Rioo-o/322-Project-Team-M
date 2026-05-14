"""Single-window Tkinter app.

Layout:
  +-------------------------------------------------------------+
  | College0   [phase: ...]                user / logout         |  topbar
  +-------------+-----------------------------------------------+
  |  sidebar    |                content frame                  |
  |             |                                               |
  +-------------+-----------------------------------------------+

We swap the *content frame* by destroying it and re-mounting the
chosen view. We never spawn new top-level windows.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from core import models
from . import theme
from .views import home, login, apply as apply_view
from .views import registrar as registrar_view
from .views import instructor as instructor_view
from .views import student as student_view


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("College0")
        self.geometry("1180x740")
        self.minsize(1000, 640)
        self.configure(bg=theme.BG)

        self.user: Optional[dict] = None    # logged-in user dict, or None for visitor
        self.toast_label: Optional[tk.Label] = None

        self._build_topbar()
        self._build_body()

        self.show("home")

    # ---------- chrome ----------

    def _build_topbar(self) -> None:
        bar = tk.Frame(self, bg=theme.ACCENT, height=54)
        bar.pack(side="top", fill="x")
        bar.pack_propagate(False)

        title = tk.Label(bar, text="College0", fg="white",
                         bg=theme.ACCENT, font=("Segoe UI", 16, "bold"),
                         padx=18)
        title.pack(side="left")

        self.phase_lbl = tk.Label(bar, text="", fg="white", bg=theme.ACCENT,
                                  font=theme.FONT, padx=14)
        self.phase_lbl.pack(side="left")

        right = tk.Frame(bar, bg=theme.ACCENT)
        right.pack(side="right", padx=14)

        self.user_lbl = tk.Label(right, text="", fg="white", bg=theme.ACCENT,
                                 font=theme.FONT_BOLD)
        self.user_lbl.pack(side="left", padx=(0, 10))

        self.login_btn = theme.make_button(
            right, text="Login", command=lambda: self.show("login"),
            bg="white", fg=theme.ACCENT_DARK, hover_bg="#e6ecff",
            padx=14, pady=4, bordercolor="white")
        self.login_btn.pack(side="left", padx=4)

        self.logout_btn = theme.make_button(
            right, text="Logout", command=self.logout,
            bg="white", fg=theme.BAD, hover_bg="#fde4e0",
            padx=14, pady=4, bordercolor="white")
        # not packed by default

    def _build_body(self) -> None:
        body = tk.Frame(self, bg=theme.BG)
        body.pack(side="top", fill="both", expand=True)
        self.body = body

        self.sidebar = tk.Frame(body, bg="#0f1530", width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.content = tk.Frame(body, bg=theme.BG)
        self.content.pack(side="left", fill="both", expand=True)

        # Toast area (over content, bottom right).
        self.toast = tk.Label(self, text="", bg=theme.GOOD, fg="white",
                              font=theme.FONT_BOLD, padx=14, pady=8)

    # ---------- topbar refresh ----------

    def refresh_chrome(self) -> None:
        state = models.get_semester_state()
        self.phase_lbl.config(text=f"Semester {state['semester']} · {state['phase']}")

        if self.user:
            warn = (f"  · {self.user['warnings']} warning(s)"
                    if self.user.get("warnings") else "")
            label = f"{self.user['full_name']} ({self.user['role']}){warn}"
            self.user_lbl.config(text=label)
            self.login_btn.pack_forget()
            self.logout_btn.pack(side="left", padx=4)
        else:
            self.user_lbl.config(text="Visitor")
            self.logout_btn.pack_forget()
            self.login_btn.pack(side="left", padx=4)

        self._rebuild_sidebar()

    # ---------- sidebar ----------

    def _rebuild_sidebar(self) -> None:
        for w in self.sidebar.winfo_children():
            w.destroy()

        sidebar_bg = "#0f1530"
        sidebar_hover = "#2c3768"

        # Branding banner.
        title = tk.Label(self.sidebar, text="NAVIGATION",
                         bg=sidebar_bg, fg="white",
                         font=theme.FONT_BOLD, padx=18, pady=14, anchor="w")
        title.pack(fill="x")

        def add(label: str, key: str) -> None:
            # Using tk.Label (not tk.Button) because on macOS tk.Button does not
            # honor bg/fg reliably — it falls back to the native gray button
            # chrome, which produces near-white-on-light-gray contrast.
            lbl = tk.Label(self.sidebar, text=label, anchor="w",
                           bg=sidebar_bg, fg="white",
                           padx=18, pady=10,
                           font=theme.FONT)
            lbl.pack(fill="x")

            def on_enter(_e, w=lbl):
                w.config(bg=sidebar_hover)

            def on_leave(_e, w=lbl):
                w.config(bg=sidebar_bg)

            def on_click(_e, k=key):
                self.show(k)

            lbl.bind("<Enter>", on_enter)
            lbl.bind("<Leave>", on_leave)
            lbl.bind("<Button-1>", on_click)

        add("Home", "home")
        if not self.user:
            add("Apply", "apply")
            add("Login", "login")
            add("AI Chat", "ai_visitor")
        else:
            role = self.user["role"]
            if role == "registrar":
                add("Applications", "registrar_apps")
                add("Courses", "registrar_courses")
                add("Phase / Rules", "registrar_phase")
                add("Taboo Words", "registrar_taboo")
                add("Complaints", "registrar_complaints")
                add("Graduations", "registrar_grads")
                add("People", "registrar_people")
                add("AI Chat", "ai_registrar")
            elif role == "instructor":
                add("My Classes", "instr_classes")
                add("Grades", "instr_grades")
                add("File Complaint", "instr_complaint")
                add("AI Chat", "ai_instructor")
            elif role == "student":
                add("My Records", "student_records")
                add("Register", "student_register")
                add("Reviews", "student_reviews")
                add("Complaint", "student_complaint")
                add("Graduation", "student_grad")
                add("Study Buddies", "student_buddies")
                add("AI Chat", "ai_student")

    # ---------- routing ----------

    def show(self, key: str) -> None:
        """Replace content frame with a view keyed by `key`."""
        for w in self.content.winfo_children():
            w.destroy()
        self.refresh_chrome()

        if key == "home":
            home.HomeView(self.content, self).pack(fill="both", expand=True)
        elif key == "login":
            login.LoginView(self.content, self).pack(fill="both", expand=True)
        elif key == "apply":
            apply_view.ApplyView(self.content, self).pack(fill="both", expand=True)
        elif key.startswith("ai_"):
            from .views.ai_chat import AIChatView
            AIChatView(self.content, self).pack(fill="both", expand=True)
        elif key.startswith("registrar_"):
            registrar_view.RegistrarView(self.content, self,
                                         section=key[len("registrar_"):]
                                         ).pack(fill="both", expand=True)
        elif key.startswith("instr_"):
            instructor_view.InstructorView(self.content, self,
                                           section=key[len("instr_"):]
                                           ).pack(fill="both", expand=True)
        elif key.startswith("student_"):
            student_view.StudentView(self.content, self,
                                     section=key[len("student_"):]
                                     ).pack(fill="both", expand=True)
        elif key == "first_login_pw":
            login.FirstLoginPWView(self.content, self).pack(fill="both", expand=True)
        else:
            tk.Label(self.content, text=f"Unknown view: {key}").pack()

    # ---------- session ----------

    def login_as(self, user: dict) -> None:
        self.user = user
        # If they must change password, force that view.
        if user.get("must_change_pw"):
            self.show("first_login_pw")
            return
        # Tutorial banner is handled by student dashboard.
        if user["role"] == "registrar":
            self.show("registrar_apps")
        elif user["role"] == "instructor":
            self.show("instr_classes")
        else:
            self.show("student_records")

    def logout(self) -> None:
        self.user = None
        self.show("home")

    # ---------- toast ----------

    def toast_msg(self, text: str, kind: str = "ok") -> None:
        color = {"ok": theme.GOOD, "bad": theme.BAD, "warn": theme.WARN}.get(kind, theme.GOOD)
        self.toast.config(text=text, bg=color)
        self.toast.place(relx=0.99, rely=0.97, anchor="se")
        self.after(3500, self.toast.place_forget)

    # ---------- reload from db ----------

    def refresh_user(self) -> None:
        """Re-fetch the logged in user (warnings/status may have changed)."""
        if self.user:
            fresh = models.get_user(self.user["id"])
            if fresh:
                self.user = fresh
        self.refresh_chrome()
