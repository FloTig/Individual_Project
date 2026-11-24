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
- **Double-tap / both-phones guard:** Done/Skip buttons carry the `due` date they showed (`data-due`). `db.complete` only updates `where next_due = <that date>`, so an occurrence counts once.
- **Look (Nov 2026, the owners' call):** calm iOS-style "Liquid Glass" (pastel mist, frosted cards, rim highlights, floating tab bar, SF Pro Rounded via `ui-rounded`) plus loud internet memes: meme cat stickers in `assets/cats/` (FrankerFaceZ emotes; the owners want real downloaded memes, not drawn ones), a marquee, Impact captions, cat GIFs from cataas.com. Users are Florian and Rebekka; avatars match by name. The README has the cat table.
- **Done/Skip flow:** `assets/fx.js` catches the tap, plays the card's exit animation, then `dash_clientside.set_props("pending", …)` triggers the server `act` callback, batching overlapping taps. Cards have ids that include the due date; Dash uses ids as React keys, so cards mount and unmount cleanly.
- **Streak (to build in M3):** consecutive days with none of *your* chores overdue.
- **Sync between phones:** re-render after every action plus a 60-second `dcc.Interval`. No websockets.
- **Login cookie:** signed and lasts 365 days. `SESSION_COOKIE_SECURE` is turned on when `SECRET_KEY` is set (production).
- **Timezone:** `APP_TZ` env var. If unset, the machine's local time is used. Must be set on the server, since hosts usually run on UTC.
- **iCloud:** not usable as a web-app database.

## Gotchas found while building

- Dash calls the layout function once at startup, outside any request, so **don't read `flask.session` in `layout()`**. Per-user bits, like the avatar on the log-out chip, are filled by the `render` callback.
- **Glass:** don't animate `opacity` on a parent of a `backdrop-filter` element (Chrome then blurs nothing). The dock slides in with transform only for this reason. `body` must stay transparent so the mist layer (`.app::before`) shows.
- Pattern-matching button callbacks also fire when buttons are re-rendered. The `clicked()` helper in `app.py` checks `ctx.triggered[0]["value"]` to tell a real tap apart.
- In debug mode Dash pings `dash-version.plotly.com`. That causes a harmless console error when offline.

## Status

- **M1 (core chores) is done** and was tested end to end in a headless iPhone-sized browser:
  - login and wrong-password message;
  - add/edit/archive with validation;
  - turn-taking passes to the other person;
  - a double tap counts once;
  - an overdue skip moves to the next date.
- **M0 (go live) is built, not yet deployed.** Tested locally with the Flask test client and headless Chrome:
  - `/manifest.json` and `assets/icons/` (Smudge on the mist), so it installs as a home-screen app;
  - settings in `chores-app/.env` (`settings.py` loads it);
  - backups: `python db.py backup FOLDER` (PythonAnywhere daily task) and `/api/backup?key=…` (iPhone Shortcuts automation into iCloud Drive);
  - a Scriptable widget: `/api/widget?key=…` plus `scriptable/chores-widget.js`, which the app copies with the address and key filled in;
  - tap your name in the app for the settings sheet: install tips, copy buttons, log out.
  - The deploy steps are in `chores-app/README.md`. Still to do by the owners: create the PythonAnywhere account and follow them.
- Not built yet:
  - **M2** push notifications;
  - **M3** points, streaks and Scores screen;
  - **M4** meals.
- **Widget and backup keys** are HMACs of `SECRET_KEY` + kind + user id (`link_key` in app.py). Nothing is stored; changing `SECRET_KEY` revokes them all. `PUBLIC_PATHS`/`PUBLIC_PREFIXES` in app.py list everything reachable without a login.
- **iCloud:** ruled out as the live database (web apps can't use it; CloudKit needs a paid developer account and a rewrite). It's used for nightly backups only.

## Open decisions (ask the owner)

- **D6 Default notification time:** suggested 09:00.

## Suggested next steps

1. Deploy: follow "Deploy on PythonAnywhere" in `chores-app/README.md` (D4 chose PythonAnywhere, Nov 2026). Free tier first; its restricted outbound internet may block web push (M2), and the paid plan (~$5/mo) fixes that.
2. M2 notifications:
   - `sw.js` served from the site root (the manifest exists);
   - VAPID keys;
   - `pywebpush`;
   - a `push_subscriptions` table;
   - a protected `/cron/notify?key=…` route hit every ~5 min.
   iOS only allows web push from the home-screen-installed app (iOS 16.4+), after a tap inside the app. Details are in PLAN.md section 7.
