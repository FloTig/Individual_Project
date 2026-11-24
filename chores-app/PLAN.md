# Chores app plan

A web app for two people to define household chores, see what's due and tick chores off. It runs mainly on two iPhones, installed to the home screen.

**Status:** the core app (milestone M1) is built and runs locally. Next is hosting (M0's deploy step), then notifications (M2). See section 11.

---

## 1. What you asked for

| Topic | Answer |
|---|---|
| Devices | Phones first (both iPhone). Installable web app. Laptops work too. |
| Scheduling | Two types: **fixed schedule** (bins every Tuesday, the 1st of the month) and **after last done** (N days/weeks/months after it was last done). |
| Assignment | Per chore: **one person** (always mine / always hers), **take turns**, or **either of us**. |
| Data | Shared between both phones through the app's own server. |
| Reminders | A push notification **per chore when it's due**. |
| Overdue | Shows as overdue (red) until done, with a **skip** button that moves it to the next date. |
| Tracking | **History**, plus **points and streaks** as a **friendly competition** with a weekly winner. |
| Cooking | A special daily chore. Logging what you made feeds a **meal history**, and the app **suggests meals** you like but haven't had in a while. Seasonal products and other ideas come later. |
| Login | Own account each. |
| Stack | **Python Dash + dash-mantine-components**, SQLite. English UI. Code in `chores-app/` on this branch for now. |
| Your role | Claude builds it; you review and decide on design, features and packages. |

**Why not iCloud:** a web app can't use iCloud Drive as a database. The only Apple option is CloudKit JS, which needs a paid developer account (€99/yr), and sharing data between two Apple IDs is fiddly to set up.

**Why not Apple Reminders:** shared lists can do calendar repeats and assignees, but not "N days after last done", taking turns, points or meal suggestions.

---

## 2. Not in v1

- Multiple households, inviting other people, roles. There are exactly two users.
- Offline mode.
- A native iOS app or App Store release.
- Recipes, shopping lists and ingredients (see the backlog).

---

## 3. Architecture

```
iPhone (home-screen web app)
   │  HTTPS
   ▼
One Python process (Dash on Flask)
   ├── app.py       login page, screens, callbacks
   ├── db.py        SQLite file (chores.db)
   └── schedule.py  due-date maths (tested)

M2: a scheduler calls /cron/notify every ~5 min → pywebpush → Apple push service → iPhone
```

- **No separate database service.** One SQLite file holds everything. Backing up means copying that file.
- **Security:**
  - Every page and callback requires login (a Flask `before_request` check).
  - Passwords are stored hashed (werkzeug, which ships with Dash).
  - The login cookie is signed and lasts a year, so you stay logged in on your phone.
  - There's no sign-up page: logins are created on the server with `python db.py adduser NAME`.
- **Sync between phones:** the screen refreshes after every action and every 60 seconds. That's plenty for two people.

---

## 4. Data model

The tables that exist now (see `db.py`):

```
users        id, name (unique), pw_hash

chores       id, title, notes
             mode          'calendar' | 'after_done'
             every, unit   e.g. 2 + 'week'   (unit: day | week | month)
             assign        'fixed' | 'rotate' | 'anyone'
             assignee_id   fixed owner, or whose turn it is (null for 'anyone')
             points        effort, default 1
             next_due      ISO date
             anchor_day    day of month that monthly fixed-schedule chores land on
             archived

completions  id, chore_id, user_id, done_on, skipped,
             points (copied, so editing a chore doesn't rewrite history), created_at
```

Added in later milestones:

- `chores.notify_time`, `chores.last_notified` (M2)
- `push_subscriptions(user_id, endpoint, p256dh, auth)` (M2)
- `chores.kind = 'meal'`, `meals(id, name, liked, notes)`, `completions.meal_id` (M4)

Scores, streaks, history and "last eaten" are all computed from `completions`, never stored separately.

---

## 5. Core logic (`schedule.py`)

**A schedule is "every N days/weeks/months" plus the next due date.** "Bins every Tuesday" is every 1 week with the next due date on a Tuesday. "The 1st of the month" is every 1 month with the next due date on the 1st.

**Next due date after a chore is done or skipped:**
- *Fixed schedule:* keep adding the period to the current due date until it's after today.
  - Put the bins out a day early and they're due again next Tuesday.
  - Three weeks late lands on the next Tuesday, so missed weeks don't pile up.
  - Monthly chores use `anchor_day`, so the 31st becomes Feb 28 and then goes back to Mar 31.
- *After last done:* today plus the period.

**Assignment after done:**
- `fixed`: no change.
- `rotate`: passes to the other person.
- `anyone`: whoever ticks it off gets the points.

**Skip:** moves the date the same way, awards 0 points, and **does not** pass the turn.

**Double taps, or both phones at once:** a Done button carries the due date it was showing, and the database update only applies if that date is still current, so one occurrence can't count twice.

Chores can also be ticked off early from *Upcoming*.

---

## 6. Screens

Built:
1. **Today**: overdue and due today, grouped as *Mine / Hers / Either of us*, with Done and Skip buttons.
2. **Upcoming**: the next 14 days, with Done and Skip buttons.
3. **Chores**: all chores, with add, edit and archive.
4. **History**: who did what and when.

Later:
5. **Scores** (M3): this week's points per person, last week's winner and streaks.
6. **Settings** (M2): a notifications on/off button and the default notification time.

**Cooking flow (M4):** ticking off the daily *Cooking* chore asks *"What did you make?"* (autocomplete from past meals) and a 👍/😐/👎 rating. The Cooking card shows 3 suggestions.

---

## 7. Notifications (M2)

- iOS supports web push only for **apps added to the home screen** (iOS 16.4 and newer). Notifications must be enabled by tapping a button inside the installed app.
- Needs:
  - a `manifest.json` and a small service worker (`sw.js`), served from the root so they cover the whole app;
  - VAPID keys;
  - `pywebpush` on the server.
- **Trigger:** a protected `/cron/notify?key=…` route that the host's scheduler (or a free external cron service) calls every ~5 minutes. It finds chores where the due date plus `notify_time` (or the default time) has passed and `last_notified` isn't today's due date, sends the push, then records it.
- **Who gets the notification:** the assignee for `fixed` and `rotate` chores; both of you for `anyone` chores.
- **Login inside the installed app:** the password form works there. (Magic links wouldn't, because they open in Safari, which has separate storage.)

---

## 8. Points and streaks (M3, friendly competition)

- Each chore has a point value (effort): 1 = quick, 2 = normal, 3 = big job.
- **Weekly score:** the sum of points from Monday to Sunday per person. Last week's winner is shown on the *Scores* screen.
- **Streak:** consecutive days with none of *your* chores overdue.
- Skipped chores earn 0 points.

---

## 9. Cooking and meals (M4)

**v1:**
- Cooking is a daily chore with `kind = 'meal'`, assigned with any of the three modes.
- Completing it logs a meal and its rating.
- **Suggestions:** meals rated 👍, not eaten in the last 7 days, sorted by longest since last eaten, top 3. This is one SQL query.

**Later, in rough order:**
1. Tags such as *quick / weekend / veggie*, with quick meals suggested on weekdays.
2. Season months per meal, or a seasonal-produce list per month, to boost meals that are in season.
3. Ingredients per meal → a shopping list for the week.
4. A planned meal for the week instead of picking on the day.

---

## 10. Decisions

**Decided**

| # | Decision | Choice |
|---|---|---|
| D1 | Framework | **Python Dash 4.5 + dash-mantine-components 2.8** (Mantine 8). DMC 3.x needs React 19, which Dash 4.5 only loads behind an experimental flag. Upgrade when Dash makes React 19 the default. |
| D2 | UI | **Mantine components**, with automatic light/dark mode |
| D3 | Schedule format | **every N + unit, anchored on the due date** (see section 5) |
| D5 | Login | **Name + password**, stay logged in for a year |
| D7 | Streak | **Consecutive days with none of *your* chores overdue** |
| D8 | Skip passes the turn? | **No** |
| D9 | Language | **English** |
| D10 | Code location | **`chores-app/` on this branch**, to move to its own repo later (self-contained, so it's a plain copy) |
| D11 | Tests | **`test_schedule.py`** (plain asserts; also runs under pytest) |

**Packages:** `dash`, `dash-mantine-components`, and `pywebpush` from M2. Everything else is the standard library: `sqlite3`, `zoneinfo`, `calendar`.

**Still open**

| # | Decision | Notes |
|---|---|---|
| D4 | **Hosting** | Dash needs a Python process that's always running and a disk that keeps `chores.db`. Options (check current pricing and terms): <br>• **PythonAnywhere**: made for Python web apps and keeps files. The free tier is likely enough to start, but it restricts outbound internet, which may block push (M2); the paid tier is about $5/mo. **My pick.** <br>• **Small VPS** (about €4–5/mo): full control, but you maintain it. <br>• **Raspberry Pi at home + Cloudflare Tunnel**: free if you have a Pi. <br>• Render, Railway, Koyeb free tiers: usually sleep when idle (slow first open) and lose local files, so not a good fit for SQLite. |
| D6 | Default notification time | 09:00? |

---

## 11. Milestones

**M1 – Core chores ✅ (built, runs locally)**
- Login, chores add/edit/archive, both schedule types, all three assignment modes.
- Today, Upcoming and History screens; done and skip with double-tap protection.
- Tests for the schedule logic.

**M0 – Go live (next)**
- Pick hosting (D4), set `SECRET_KEY` and `APP_TZ`, create both logins.
- Set up a daily backup of `chores.db`.
- Add a manifest and icon so it opens full-screen from the home screen on both iPhones.

**M2 – Notifications**
- Service worker, saving push subscriptions, the `/cron/notify` route, the scheduler.
- Test on both iPhones.

**M3 – Points and streaks**
- Scores screen, weekly winner, streaks.

**M4 – Cooking**
- Meals table, the "what did you make?" step, suggestions on the Cooking card.

**Backlog / ideas**
- Repeat reminders for overdue chores (e.g. an evening nudge).
- Vacation mode that pauses everything and shifts due dates.
- Rooms or categories, with a filter.
- Swap request ("can you do mine today?").
- Monthly stats and charts (DMC has charts built in).
- Upgrade to DMC 3 / React 19.
- The meal features from section 9.

---

## 12. Risks and gotchas

- **Backups:** everything is in one SQLite file. Copy it daily (M0).
- **iOS push only works from the installed home-screen app.** It won't work from a Safari tab.
- **Timezone:** set `APP_TZ` on the server. Hosts usually run on UTC, which would shift "today" at night.
- **Editing a chore's due date** moves `anchor_day` for monthly chores. Past completions are never changed.
- **Every tap goes to the server.** That's fine for this app, but it would feel slow on a very bad connection.
