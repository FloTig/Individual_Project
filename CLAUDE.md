# Context for Claude Code

This branch (`claude/chores-webapp-planning-s28xvt`) contains only the chores app in `chores-app/`. `main` still holds an unrelated older project (notebooks), so don't merge this branch into `main` without asking. The plan is to move `chores-app/` to its own repo later; take this file with it.

The full product plan, with decisions and milestones, is in **`chores-app/PLAN.md`**. Run instructions are in `chores-app/README.md`. This file is the handover between sessions; keep it current.

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
- `chores-app/test_login.py`: the login brute-force brake.
- Pinned versions: `dash==4.5.1`, `dash-mantine-components==2.8.1` (Mantine 8).

## Decisions made, and why

- **Dash + DMC + SQLite, a single Python process.** Supabase/React was considered and dropped in favour of a stack the owner can maintain themselves.
- **DMC 2.8, not 3.0.** DMC 3 requires React 19; Dash 4.5 still defaults to React 18 and only offers React 19 through an "EXPERIMENTAL" `REACT_VERSION` env var. With DMC 3 the page crashed. Revisit when Dash makes React 19 the default.
- **Schedule model:** `every` + `unit` (day/week/month) + `mode` (`calendar` | `after_done`), anchored on `next_due`. "Every Tuesday" means every 1 week with `next_due` on a Tuesday. `anchor_day` keeps monthly chores on e.g. the 31st despite clamping to shorter months.
- **Calendar chores** step forward from the current due date until it's after today, so missed weeks don't pile up and doing a chore early keeps the rhythm. **after_done** chores are due today + the period.
- **Skip:** moves the date, awards 0 points, and doesn't pass the turn.
- **Rotate:** passes to the other user when done.
- **Double-tap / both-phones guard:** Done/Skip buttons carry the `due` date they showed (`data-due`). `db.complete` only updates `where next_due = <that date>`, so an occurrence counts once.
- **Look (Nov 2026, the owners' call):** calm iOS-style "Liquid Glass" (pastel mist, frosted cards, rim highlights, floating tab bar, SF Pro Rounded via `ui-rounded`) plus loud internet memes: meme cat stickers in `assets/cats/` (FrankerFaceZ emotes; the owners want real downloaded memes, not drawn ones), a marquee, Impact captions, cat GIFs from cataas.com. Users are Florian and Rebekka; avatars match by name. The README has the cat table.
- **Done/Skip flow:** `assets/fx.js` catches the tap, plays the card's exit animation, then `dash_clientside.set_props("pending", …)` triggers the server `act` callback, batching overlapping taps. Cards have ids that include the due date; Dash uses ids as React keys, so cards mount and unmount cleanly.
- **Streak (to build in M3):** consecutive days with none of *your* chores overdue.
- **Sync between phones:** re-render after every action plus a 60-second `dcc.Interval`. No websockets.
- **Login cookie:** signed and lasts 365 days. `SESSION_COOKIE_SECURE` is turned on when `SECRET_KEY` is set (production).
- **Timezone:** `APP_TZ` env var. If unset, the machine's local time is used. Must be set on the server, since hosts usually run on UTC.
- **iCloud:** not usable as a web-app database.
- **Hosting (D4, 24 Nov 2026): Railway**, EU West, project *peaceful-prosperity*, service *Individual_Project*, https://individualproject-production-223ccbdd.up.railway.app. Source: this branch, root `/chores-app`, auto-deploy on push. Start command `python -c "from app import app; app.run()"`, healthcheck `/login`, volume at `/data`, variables `HOST`, `APP_TZ=Europe/Amsterdam`, `CHORES_DB=/data/chores.db`, `SECRET_KEY`. PythonAnywhere was dropped: its free plan lost scheduled tasks for new accounts in Jan 2026 and restricts outbound internet; its paid plan is $10/mo against Railway Hobby's $5.
- **Login brake:** 10 wrong passwords in 15 minutes locks the login form for everyone (global count, since Railway's proxy hides client IPs). Phones stay logged in through their cookie.

## Gotchas found while building

- Dash calls the layout function once at startup, outside any request, so **don't read `flask.session` in `layout()`**. Per-user bits, like the avatar on the log-out chip, are filled by the `render` callback.
- **Glass:** don't animate `opacity` on a parent of a `backdrop-filter` element (Chrome then blurs nothing). The dock slides in with transform only for this reason. `body` must stay transparent so the mist layer (`.app::before`) shows.
- Pattern-matching button callbacks also fire when buttons are re-rendered. The `clicked()` helper in `app.py` checks `ctx.triggered[0]["value"]` to tell a real tap apart.
- In debug mode Dash pings `dash-version.plotly.com`. That causes a harmless console error when offline.
- **Never deploy with `python app.py`:** its `__main__` runs `debug=True`, and Werkzeug's debugger allows remote code execution. Production uses the start command above.
- **Railway Console:** plain `python` isn't on its PATH; use `/app/.venv/bin/python db.py adduser NAME`.
- **Railway volumes are tied to a region.** Create or attach a volume only after the service is in its final region.
- `CHORES_DB` must point at the volume (`/data/...`). Without the volume mounted, the app crashes at start with `unable to open database file`.

## Status (24 Nov 2026)

- **M1 (core chores) is done** and was tested end to end in a headless iPhone-sized browser: login and wrong-password message, add/edit/archive with validation, turn-taking, double-tap protection, overdue skip.
- **M0 (go live) is live on Railway.** Both logins exist (Florian, Rebekka; names are case-sensitive). Left for the owners, on their phones: Add to Home Screen, the Scriptable widgets, the Shortcuts backup automation. Also pick Railway's Hobby plan before the trial ends.
- **Security review (24 Nov 2026):** no secrets in git history; pip-audit clean; SQL parameterised; callbacks take the user from the session; every route except `PUBLIC_PATHS`/`PUBLIC_PREFIXES` requires login; debug off. Added the login brake. Open items: PLAN.md section 12.
- **Widget and backup keys** are HMACs of `SECRET_KEY` + kind + user id (`link_key` in app.py). Nothing is stored; changing `SECRET_KEY` revokes them all.
- Not built yet: **M2** notifications, **M3** points, streaks and Scores screen, **M4** meals.

## Open decisions (ask the owner)

- **D6 Default notification time:** suggested 09:00.
- **D14 Notification route:** Shortcuts automation reading `/api/widget` (no code) or web push (`pywebpush`, a new dependency). Suggested: Shortcuts first.
- **D15 Own repo:** move `chores-app/` with its history to a private repo; then switch Railway's source (root `/`).

## Suggested next steps

1. Owners: finish M0 on both iPhones (README "On your iPhones") and pick the Railway Hobby plan.
2. Housekeeping: D15 own repo, two-factor login on GitHub and Railway, limit Railway's GitHub App to the chores repo, try one restore.
3. A week or two of real use; ask what's annoying before choosing the order of M2–M4.
4. M2 after D14/D6. For web push on Railway, a background thread in the single app process can do the 5-minute check; no cron service needed. iOS only allows web push from the home-screen app (iOS 16.4+), after a tap inside the app. Details: PLAN.md section 7.
