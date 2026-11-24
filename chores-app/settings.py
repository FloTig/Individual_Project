"""Loads chores-app/.env (one KEY=value per line) into os.environ when imported.

Real environment variables win, so a host's own settings still take priority.
Both app.py and db.py import this first, so the web app, the WSGI file and
`python db.py ...` in a console all see the same settings.
"""
import os

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def load(path: str = PATH) -> None:
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load()
