"""Centralized colors / fonts for a consistent look."""
import tkinter as tk

# Colors
BG = "#f4f6fb"
PANEL = "#ffffff"
ACCENT = "#1f4cdb"
ACCENT_DARK = "#163aa2"
TEXT = "#1c1f2b"
MUTED = "#5b6075"
GOOD = "#2e8b57"
BAD = "#c0392b"
WARN = "#d97706"
BORDER = "#dde1ee"

# Darker shades for button hover/active states
GOOD_DARK = "#267a4b"
BAD_DARK = "#a52f23"
WARN_DARK = "#c26305"
MUTED_DARK = "#4a4f60"

# Fonts
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_H1 = ("Segoe UI", 18, "bold")
FONT_H2 = ("Segoe UI", 13, "bold")
FONT_SMALL = ("Segoe UI", 9)


# Default hover color for a given base color.
_HOVER_MAP = {
    ACCENT: ACCENT_DARK,
    GOOD: GOOD_DARK,
    BAD: BAD_DARK,
    WARN: WARN_DARK,
    MUTED: MUTED_DARK,
}


def make_button(parent, text, command=None, bg=ACCENT, fg="white",
                hover_bg=None, font=None, padx=12, pady=6,
                bordercolor=None, **pack_kwargs):
    """Cross-platform colored button.

    On macOS, tk.Button ignores the bg/fg attributes and falls back to the
    native gray button chrome — which made every colored button in this app
    render as white-text-on-light-gray. This helper builds a button out of a
    tk.Label with click bindings, so the colors actually take effect.

    Returns the widget. Callers still apply layout (pack/grid) themselves.
    pack_kwargs is accepted but unused so existing call sites don't break.
    """
    if font is None:
        font = FONT_BOLD
    if hover_bg is None:
        hover_bg = _HOVER_MAP.get(bg, bg)

    border = bordercolor or bg
    # Outer frame gives us a thin colored border that matches the button.
    outer = tk.Frame(parent, bg=border, highlightthickness=0, bd=0)
    btn = tk.Label(outer, text=text, bg=bg, fg=fg,
                   padx=padx, pady=pady, font=font)
    btn.pack(padx=1, pady=1)

    state = {"enabled": True, "bg": bg, "hover_bg": hover_bg}

    def on_enter(_e):
        if state["enabled"]:
            btn.config(bg=state["hover_bg"])

    def on_leave(_e):
        if state["enabled"]:
            btn.config(bg=state["bg"])

    def on_click(_e):
        if state["enabled"] and command:
            command()

    for w in (outer, btn):
        w.bind("<Enter>", on_enter)
        w.bind("<Leave>", on_leave)
        w.bind("<Button-1>", on_click)

    # Expose so callers can swap colors or disable later if needed.
    outer._btn_label = btn
    outer._btn_state = state
    return outer
