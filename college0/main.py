"""College0 launcher.

Run with:  python main.py

On first run the SQLite database is created and seeded with demo data.
Delete college0.db to reset.
"""
from __future__ import annotations

import os
import sys

# Ensure imports work no matter where the user runs `python main.py` from.
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from core import db, seed
from ui.app import App


def main() -> None:
    fresh = not os.path.exists(db.DB_PATH)
    db.init_schema()
    if fresh:
        seed.seed_all()
        print(f"[College0] Seeded demo database at {db.DB_PATH}")
    App().mainloop()


if __name__ == "__main__":
    main()
