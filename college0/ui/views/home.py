"""Public landing page."""
from __future__ import annotations

import tkinter as tk

from core import models
from .. import theme


class HomeView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG, padx=24, pady=18)
        self.app = app

        tk.Label(self, text="Welcome to College0", bg=theme.BG, fg=theme.TEXT,
                 font=theme.FONT_H1).pack(anchor="w")
        tk.Label(self,
                 text=("College0 is a small AI-enabled graduate program management system. "
                       "Public stats below are visible to everyone."),
                 bg=theme.BG, fg=theme.MUTED, font=theme.FONT, wraplength=900,
                 justify="left").pack(anchor="w", pady=(4, 18))

        grid = tk.Frame(self, bg=theme.BG)
        grid.pack(fill="both", expand=True)

        # Three cards side-by-side.
        self._make_card(grid, "Highest-rated classes",
                        models.top_rated_courses(3),
                        formatter=self._fmt_course).grid(row=0, column=0,
                                                         sticky="nsew", padx=(0, 12))
        self._make_card(grid, "Lowest-rated classes",
                        models.bottom_rated_courses(3),
                        formatter=self._fmt_course).grid(row=0, column=1,
                                                         sticky="nsew", padx=(0, 12))
        self._make_card(grid, "Top GPA students",
                        models.top_gpa_students(5),
                        formatter=self._fmt_student).grid(row=0, column=2,
                                                          sticky="nsew")

        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)
        grid.grid_columnconfigure(2, weight=1)
        grid.grid_rowconfigure(0, weight=1)

        if not app.user:
            tip = tk.Frame(self, bg=theme.BG)
            tip.pack(fill="x", pady=(20, 0))
            tk.Label(tip, text="Visitors:", bg=theme.BG, fg=theme.MUTED,
                     font=theme.FONT_BOLD).pack(side="left")
            theme.make_button(tip, text="Apply to join",
                              command=lambda: app.show("apply"),
                              bg=theme.ACCENT, fg="white",
                              padx=14, pady=6).pack(side="left", padx=8)
            theme.make_button(tip, text="Ask the AI",
                              command=lambda: app.show("ai_visitor"),
                              bg="white", fg=theme.ACCENT, hover_bg="#e6ecff",
                              padx=14, pady=6,
                              bordercolor=theme.BORDER).pack(side="left", padx=4)
            theme.make_button(tip, text="Login",
                              command=lambda: app.show("login"),
                              bg="white", fg=theme.TEXT, hover_bg="#f0f0f0",
                              padx=14, pady=6,
                              bordercolor=theme.BORDER).pack(side="left", padx=4)

    # ----- helpers -----

    def _make_card(self, parent, title: str, items: list, formatter) -> tk.Frame:
        card = tk.Frame(parent, bg=theme.PANEL, highlightthickness=1,
                        highlightbackground=theme.BORDER)
        tk.Label(card, text=title, bg=theme.PANEL, fg=theme.TEXT,
                 font=theme.FONT_H2, padx=14, pady=10).pack(anchor="w")
        if not items:
            tk.Label(card, text="(no data yet)", bg=theme.PANEL, fg=theme.MUTED,
                     padx=14, pady=4).pack(anchor="w")
        else:
            for it in items:
                row = tk.Frame(card, bg=theme.PANEL)
                row.pack(fill="x", padx=14, pady=3)
                formatter(row, it)
        # Spacer.
        tk.Frame(card, bg=theme.PANEL, height=10).pack()
        return card

    def _fmt_course(self, row, item):
        tk.Label(row, text=f"{item['code']}  {item['title']}", bg=theme.PANEL,
                 fg=theme.TEXT, font=theme.FONT).pack(side="left", anchor="w")
        tk.Label(row, text=f"{item['avg_stars']} / 5",
                 bg=theme.PANEL, fg=theme.WARN, font=theme.FONT).pack(side="right")

    def _fmt_student(self, row, item):
        tk.Label(row, text=item["full_name"], bg=theme.PANEL,
                 fg=theme.TEXT, font=theme.FONT).pack(side="left", anchor="w")
        tk.Label(row, text=f"GPA {item['gpa']:.2f}", bg=theme.PANEL,
                 fg=theme.GOOD, font=theme.FONT_BOLD).pack(side="right")
