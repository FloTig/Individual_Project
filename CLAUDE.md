# Context for Claude Code

This branch (`claude/chores-webapp-planning-s28xvt`) contains only the chores app in `chores-app/`. `main` still holds an unrelated older project (notebooks), so don't merge this branch into `main` without asking. The plan is to move `chores-app/` to its own repo later; take this file with it.

The full product plan, with decisions and milestones, is in **`chores-app/PLAN.md`**. Run instructions are in `chores-app/README.md`. This file is the short handover from the first (cloud) session.

## What this is

A chores web app for a couple (two users, both on iPhone). It's used mainly from the phone home screen.
- Chores repeat either **on a fixed schedule** (bins every Tuesday) or **N days/weeks/months after last done**.
- Each chore belongs to **one person**, **takes turns**, or is for **either of us**.
- Overdue chores show in red, with a **Skip** button.
- **History** is built. **Points and streaks** (friendly competition, weekly winner) come later.
- **Cooking** will be a special daily chore that logs meals and suggests ones you like but haven't had in a while.

## Working with the owner

- They're comfortable with code and know **Python Dash + dash-mantine-components**, which is why that's the stack.
- **They want to decide on design choices, features and packages.** Propose with a recommendation and ask before adding a dependency or making a product decision. Small implementation details are fine to just do.
- English UI. Keep dependencies minimal: standard library first.

## Stack and layout

- `chores-app/app.py`: Dash app. Flask login (`/login`, `/logout`, `before_request` guard), Mantine layout, callbacks.
- `chores-app/db.py`: SQLite via `sqlite3`. Schema, queries, and the `python db.py adduser NAME` command (the only way to create logins; there's no sign-up page).
- `chores-app/schedule.py`: pure due-date maths. `test_schedule.py` tests it (`python test_schedule.py` or pytest).
- Pinned versions: `dash==4.5.1`, `dash-mantine-components==2.8.1` (Mantine 8).

## Decisions made, and why

- **Dash + DMC + SQLite, a single Python process.** Supabase/React was considered and dropped in favour of a stack the owner can maintain themselves.
- **DMC 2.8, not 3.0.** DMC 3 requires React 19; Dash 4.5 still defaults to React 18 and only offers React 19 through an "EXPERIMENTAL" `REACT_VERSION` env var. With DMC 3 the page crashed. Revisit when Dash makes React 19 the default.
- **Schedule model:** `every` + `unit` (day/week/month) + `mode` (`calendar` | `after_done`), anchored on `next_due`. "Every Tuesday" means every 1 week with `next_due` on a Tuesday. `anchor_day` keeps monthly chores on e.g. the 31st despite clamping to shorter months.
- **Calendar chores** step forward from the current due date until it's after today, so missed weeks don't pile up and doing a chore early keeps the rhythm. **after_done** chores are due today + the period.
- **Skip:** moves the date, awards 0 points, and doesn't pass the turn.
- **Rotate:** passes to the other user when done.
- **Double-tap / both-phones guard:** Done/Skip button ids carry the `due` date they showed. `db.complete` only updates `where next_due = <that date>`, so an occurrence counts once.
- **Streak (to build in M3):** consecutive days with none of *your* chores overdue.
- **Sync between phones:** re-render after every action plus a 60-second `dcc.Interval`. No websockets.
- **Login cookie:** signed and lasts 365 days. `SESSION_COOKIE_SECURE` is turned on when `SECRET_KEY` is set (production).
- **Timezone:** `APP_TZ` env var. If unset, the machine's local time is used. Must be set on the server, since hosts usually run on UTC.
- **iCloud:** not usable as a web-app database.

## Gotchas found while building

- Dash calls the layout function once at startup, outside any request, so **don't read `flask.session` in `layout()`**. Per-user bits, like the "name · log out" link, are filled by the `render` callback.
- Pattern-matching button callbacks also fire when buttons are re-rendered. The `clicked()` helper in `app.py` checks `ctx.triggered[0]["value"]` to tell a real tap apart.
- In debug mode Dash pings `dash-version.plotly.com`. That causes a harmless console error when offline.

## Status

- **M1 (core chores) is done** and was tested end to end in a headless iPhone-sized browser:
  - login and wrong-password message;
  - add/edit/archive with validation;
  - turn-taking passes to the other person;
  - a double tap counts once;
  - an overdue skip moves to the next date.
- Not built yet:
  - **M0** go live: hosting, `SECRET_KEY`, `APP_TZ`, daily backup of `chores.db`, manifest and icon for the home screen;
  - **M2** push notifications;
  - **M3** points, streaks and Scores screen;
  - **M4** meals.

## Open decisions (ask the owner)

- **D4 Hosting:** the suggestion is **PythonAnywhere**. It's built for Python web apps and keeps the SQLite file. Start on the free tier; its restricted outbound internet may block web push (M2), in which case the paid plan (~$5/mo) fixes that. A Raspberry Pi was discussed and rejected: ~€100–130 upfront plus sysadmin work. Render, Railway and Koyeb free tiers sleep and lose local files.
- **D6 Default notification time:** suggested 09:00.

## Suggested next steps

1. Run it locally:
   - `cd chores-app && python -m venv .venv && pip install -r requirements.txt`
   - `python db.py adduser <name>` once per person
   - `python app.py`
2. Deploy (M0) once hosting is chosen. Offer to write the PythonAnywhere steps into the README.
3. M2 notifications:
   - `manifest.json` and `sw.js` served from the site root;
   - VAPID keys;
   - `pywebpush`;
   - a `push_subscriptions` table;
   - a protected `/cron/notify?key=…` route hit every ~5 min.
   iOS only allows web push from the home-screen-installed app (iOS 16.4+), after a tap inside the app. Details are in PLAN.md section 7.
