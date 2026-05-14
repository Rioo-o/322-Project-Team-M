"""Authentication: very thin wrapper around the users table.

Passwords are plaintext for this toy demo.
"""
from __future__ import annotations

from typing import Optional

from . import models


def login(username: str, password: str) -> tuple[Optional[dict], Optional[str]]:
    """Return (user_dict, error_message)."""
    u = models.find_user(username.strip())
    if not u:
        return None, "Unknown username."
    if u["password"] != password:
        return None, "Incorrect password."
    if u["status"] == "terminated":
        return None, "This account has been terminated."
    if u["status"] == "fired":
        return None, "This account has been fired and cannot log in."
    if u["status"] == "suspended":
        return None, ("This account is suspended"
                      f" until semester {u['suspended_until_semester'] or '?'}."
                      f" Fine due: ${u['fine_due']:.0f}.")
    if u["status"] == "graduated":
        return None, "This student has already graduated."
    return u, None


def change_password(user_id: int, old_password: str, new_password: str) -> Optional[str]:
    u = models.get_user(user_id)
    if not u:
        return "User not found."
    if u["password"] != old_password:
        return "Old password is incorrect."
    if len(new_password) < 4:
        return "New password must be at least 4 characters."
    if new_password == old_password:
        return "Pick a new password different from the temporary one."
    models.update_password(user_id, new_password)
    return None
