"""Login + password change.

Just a thin wrapper around the ``users`` table. Passwords are stored
in plaintext here — fine for a class demo, obviously not for anything
real.
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
    # Note: suspended and graduated users can still sign in.
    # - Suspended folks need access to pay their fine and to redeem
    #   honor tokens. Their dashboard shows a hard red banner and the
    #   business-rule layer (try_register, etc.) blocks anything that
    #   matters while they're inactive.
    # - Graduated students keep read-only access to their transcript.
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
