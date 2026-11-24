# Chores

A chores app for two people: Python Dash + dash-mantine-components, with SQLite storage. See [PLAN.md](PLAN.md) for the plan.

## Run locally

```bash
cd chores-app
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python db.py adduser YourName      # asks for a password; run once per person
python db.py adduser HerName
python app.py                      # http://127.0.0.1:8050
```

To try it on your phone on the same wifi, start it with `HOST=0.0.0.0 python app.py` (Windows: `set HOST=0.0.0.0` first), then open `http://<laptop-ip>:8050`.

Tests: `python test_schedule.py`

## Settings (environment variables)

| Name | What it does |
|---|---|
| `SECRET_KEY` | **Set this in production.** It signs the login cookie, so logins survive restarts, and it turns on HTTPS-only cookies. Generate one with `python -c "import secrets; print(secrets.token_hex())"`. |
| `APP_TZ` | Household timezone (IANA name such as `Europe/London`). It decides what "today" means. If unset, the machine's local time is used. |
| `CHORES_DB` | Path of the SQLite file. Default: `chores.db` next to the code. |
| `HOST` / `PORT` | Where the dev server listens. Defaults: `127.0.0.1:8050`. |

In production, run `app.server` with a WSGI server, e.g. `gunicorn app:server`, or point the host's WSGI config at it. Debug mode only runs through `python app.py`.

## Files

- `app.py`: login, the screens and the callbacks.
- `db.py`: the SQLite schema and queries, plus the `adduser` command.
- `schedule.py`: due-date calculations. `test_schedule.py` tests them.
