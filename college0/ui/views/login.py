"""Login and first-login password-change views."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from core import auth, models
from .. import theme


class LoginView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG, padx=24, pady=18)
        self.app = app

        card = tk.Frame(self, bg=theme.PANEL, highlightthickness=1,
                        highlightbackground=theme.BORDER, padx=28, pady=22)
        card.place(relx=0.5, rely=0.45, anchor="center", width=420)

        tk.Label(card, text="Sign in", bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT_H1).pack(anchor="w")
        tk.Label(card, text="Try registrar / admin or alice / password",
                 bg=theme.PANEL, fg=theme.MUTED, font=theme.FONT_SMALL).pack(anchor="w",
                                                                              pady=(2, 16))

        tk.Label(card, text="Username", bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT).pack(anchor="w")
        self.user_entry = tk.Entry(card, font=theme.FONT,
                                   bg="white", fg=theme.TEXT, insertbackground=theme.TEXT)
        self.user_entry.pack(fill="x", pady=(2, 10))
        self.user_entry.focus_set()

        tk.Label(card, text="Password", bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT).pack(anchor="w")
        self.pw_entry = tk.Entry(card, font=theme.FONT, show="•",
                                 bg="white", fg=theme.TEXT, insertbackground=theme.TEXT)
        self.pw_entry.pack(fill="x", pady=(2, 18))

        theme.make_button(card, text="Login", command=self._do_login,
                          bg=theme.ACCENT, fg="white",
                          padx=14, pady=8).pack(fill="x")

        self.msg = tk.Label(card, text="", bg=theme.PANEL, fg=theme.BAD,
                            font=theme.FONT)
        self.msg.pack(anchor="w", pady=(10, 0))

        # Convenience: Enter triggers login.
        self.user_entry.bind("<Return>", lambda *_: self._do_login())
        self.pw_entry.bind("<Return>", lambda *_: self._do_login())

    def _do_login(self):
        u, err = auth.login(self.user_entry.get(), self.pw_entry.get())
        if err:
            self.msg.config(text=err)
            return
        self.app.login_as(u)


class FirstLoginPWView(tk.Frame):
    """Forced password change on first login."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG, padx=24, pady=18)
        self.app = app

        card = tk.Frame(self, bg=theme.PANEL, highlightthickness=1,
                        highlightbackground=theme.BORDER, padx=28, pady=22)
        card.place(relx=0.5, rely=0.45, anchor="center", width=480)

        tk.Label(card, text="Set a new password", bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT_H1).pack(anchor="w")
        tk.Label(card, text="You're using a temporary password. Please choose a new one.",
                 bg=theme.PANEL, fg=theme.MUTED, font=theme.FONT,
                 wraplength=420, justify="left").pack(anchor="w", pady=(4, 14))

        tk.Label(card, text="Temporary password", bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT).pack(anchor="w")
        self.old_entry = tk.Entry(card, show="•", font=theme.FONT,
                                  bg="white", fg=theme.TEXT, insertbackground=theme.TEXT)
        self.old_entry.pack(fill="x", pady=(2, 10))

        tk.Label(card, text="New password", bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT).pack(anchor="w")
        self.new_entry = tk.Entry(card, show="•", font=theme.FONT,
                                  bg="white", fg=theme.TEXT, insertbackground=theme.TEXT)
        self.new_entry.pack(fill="x", pady=(2, 16))

        theme.make_button(card, text="Save", command=self._save,
                          bg=theme.ACCENT, fg="white",
                          padx=14, pady=8).pack(fill="x")
        self.msg = tk.Label(card, text="", bg=theme.PANEL, fg=theme.BAD,
                            font=theme.FONT)
        self.msg.pack(anchor="w", pady=(10, 0))

    def _save(self):
        err = auth.change_password(self.app.user["id"],
                                   self.old_entry.get(),
                                   self.new_entry.get())
        if err:
            self.msg.config(text=err)
            return
        self.app.toast_msg("Password updated. Welcome to College0!")
        # Refresh user (must_change_pw flag is cleared).
        self.app.refresh_user()
        role = self.app.user["role"]
        if role == "student":
            self.app.show("student_records")
        elif role == "instructor":
            self.app.show("instr_classes")
        else:
            self.app.show("registrar_apps")
