# Chores app plan

A web app for two people to define household chores, see what's due and tick chores off. It runs mainly on two iPhones, installed to the home screen.

---

## 1. What you asked for

| Topic | Answer |
|---|---|
| Devices | Phones first (both iPhone). Installable web app (PWA). Laptops work too. |
| Scheduling | Two types: **calendar** (bins every Tuesday, 1st of the month) and **interval** (N days after it was last done). |
| Assignment | Per chore: **fixed** (always mine / always hers), **take turns**, or **either of us**. |
| Data | Shared and synced between both phones. Free hosted service. |
| Reminders | A push notification **per chore when it's due**. |
| Overdue | Shows as overdue (red) until done, with a **skip** button that moves it to the next date. |
| Tracking | **History**, plus **points and streaks** as a **friendly competition** with a weekly winner. |
| Cooking | A special daily chore. Logging what you made feeds a **meal history**, and the app **suggests meals** you like but haven't had in a while. Seasonal products and other ideas come later. |
| Login | Own account each. |
| Your role | Claude builds it; you decide on design, features and packages (see section 10). |

**Why not iCloud:** a web app can't use iCloud Drive as a database. The only Apple option is CloudKit JS, which needs a paid developer account (€99/yr), and sharing data between two Apple IDs is fiddly to set up. Supabase's free tier gives a database, login and live sync for €0.

**Why not Apple Reminders:** shared lists can do calendar repeats and assignees, but not "N days after last done", taking turns, points or meal suggestions.

---

## 2. Not in v1

- Multiple households, inviting other people, roles. There are exactly two users.
- Offline mode. The app needs a connection; caching can come later.
- A native iOS app or App Store release.
- Recipes, shopping lists and ingredients (see the backlog).

---

## 3. Architecture

```
iPhone (home-screen PWA)
   │  supabase-js (HTTPS, realtime websocket)
   ▼
Supabase (free tier)
   ├── Postgres: tables + Row Level Security
   ├── Auth: 2 accounts, sign-ups disabled afterwards
   ├── pg_cron: every 5 min → calls Edge Function
   └── Edge Function "notify": finds due chores → sends Web Push
                                      │
                                      ▼
                           Apple Push service → iPhone
Static frontend hosting (free): Netlify / Vercel / Cloudflare Pages
```

- **There's no backend server of our own.** The frontend talks to Supabase directly, and the database rules (RLS) handle security.
- **Security model:** create the two accounts, then **turn off sign-ups** in Supabase. Each table gets one RLS policy: any logged-in user may read and write. With only two accounts that's enough, and it's the main security boundary, so it has to be in place before the app goes online.
- **Live sync:** Supabase Realtime, so a chore she ticks off disappears from your screen too.

---

## 4. Data model (first draft)

```
profiles        id (= auth user id), name

chores          id, title, notes
                kind            'normal' | 'meal'
                schedule_type   'calendar' | 'interval'
                every           int      -- e.g. 1, 2
                unit            'day' | 'week' | 'month'   (calendar only)
                weekday         0-6      (calendar + week, optional)
                month_day       1-31     (calendar + month, optional; clamps to month end)
                interval_days   int      (interval only)
                assign_mode     'fixed' | 'rotate' | 'anyone'
                assignee_id     -> profiles  (fixed owner, or whose turn it is)
                points          int default 1
                notify_time     time, nullable (null = default time)
                next_due        date
                last_notified   date, nullable  (so each due date notifies once)
                archived        bool

completions     id, chore_id, user_id, done_on (date), created_at
                skipped         bool
                points          int     -- copied at completion; editing a chore doesn't rewrite history
                meal_id         -> meals, nullable

meals           id, name, liked ('yes' | 'meh' | 'no'), notes
                -- later: tags, season months, ingredients

push_subscriptions  id, user_id, endpoint, p256dh, auth
```

Scores, streaks, history and "last eaten" are all **computed from `completions`** with SQL views, never stored separately.

---

## 5. Core logic

All of this goes in **one pure module** (`schedule.ts`) with a small test file, because it's the only tricky logic in the app.

**Next due date after a chore is done or skipped:**
- *Calendar:* keep adding the period (N days, weeks or months) to the current due date until it's after today. If you put the bins out a day early, they're due again next Tuesday. If you're three weeks late, it lands on the next Tuesday rather than piling up missed weeks.
- *Interval:* done → `done date + interval_days`. Skipped → `today + interval_days`.

**Assignment after done:**
- `fixed`: no change.
- `rotate`: `assignee_id` switches to the other person.
- `anyone`: no assignee. Whoever ticks it off gets the points.

**Overdue:** `next_due < today` shows it in red at the top of the list.

**Skip:** works like "done" for the next due date but records `skipped = true`, awards 0 points and **does not** pass the turn (decision D8).

**Timezone:** one household timezone constant. Dates are stored as plain `date` values (no time) to avoid off-by-one-day bugs.

---

## 6. Screens

1. **Today** (home): overdue and due today, grouped as *Mine / Hers / Either*. Tap to mark done; swipe or long-press to skip.
2. **Upcoming**: the next 14 days.
3. **Chores**: all chores, with add and edit. The form shows only the fields that apply to the chosen schedule and assignment types.
4. **History**: who did what and when, newest first.
5. **Scores**: this week's points per person, last week's winner and current streaks.
6. **Settings**: your name, a notifications on/off button, the default notification time.

**Cooking flow:** ticking off the daily *Cooking* chore opens a sheet with *"What did you make?"* (autocomplete from past meals, or type a new one) and a 👍/😐/👎 rating. The *Today* card for Cooking shows **3 suggestions** before it's done.

---

## 7. Notifications (iPhone specifics)

- iOS supports web push only for **apps added to the home screen** (iOS 16.4 and newer). Notifications must be enabled by tapping a button inside the installed app; the app can't ask for permission on its own.
- **Login inside the installed app:** the home-screen app keeps its storage separate from Safari, so magic links (which open in Safari) won't log the app in. Use **email + password** or a **6-digit email code** instead (D5).
- **Flow:** every 5 minutes pg_cron calls the `notify` Edge Function. It finds chores where `next_due + (notify_time or default) <= now` and `last_notified <> next_due`, sends a push, then sets `last_notified = next_due`.
- **Who gets the notification:** the assignee for `fixed` and `rotate` chores; both of you for `anyone` chores.
- v1 sends one notification per due date. Repeat reminders for overdue chores are in the backlog.

---

## 8. Points and streaks (friendly competition)

- Each chore has a point value (effort), e.g. 1 = quick, 2 = normal, 3 = big job.
- **Weekly score:** the sum of points from Monday to Sunday per person. Last week's winner is shown on the *Scores* screen.
- **Streak:** see D7 for the definition.
- Skipped chores earn 0 points.

---

## 9. Cooking and meals

**v1:**
- Cooking is a daily chore with `kind = 'meal'`, assigned with any of the three modes (taking turns probably makes sense).
- Completing it logs a meal and its rating.
- **Suggestions:** meals rated 👍, not eaten in the last 7 days, sorted by longest since last eaten, top 3. This is one SQL query.

**Later (backlog), in rough order:**
1. Tags such as *quick / weekend / veggie*, with quick meals suggested on weekdays.
2. Season months per meal, or a seasonal-produce list per month, to boost meals that are in season.
3. Ingredients per meal → a shopping list for the week.
4. A planned meal for the week instead of picking on the day.

---

## 10. Decisions for you

The defaults are what I'd pick. Change any of them.

| # | Decision | Default | Alternatives |
|---|---|---|---|
| D1 | Frontend framework | **SvelteKit** (static build, least boilerplate) | React + Vite, Vue + Vite. Pick one you already know if you prefer. |
| D2 | Styling | **Plain CSS** with variables and automatic dark mode | Tailwind, or a component library (e.g. shadcn/ui) |
| D3 | Calendar schedule format | **Simple fields** (every / unit / weekday / month_day) | RFC 5545 RRULE strings with the `rrule` package: more flexible (e.g. "last Friday of the month"), but adds a dependency and is harder to edit |
| D4 | Frontend hosting | **Netlify** or **Cloudflare Pages** | Vercel, GitHub Pages |
| D5 | Login method | **Email + password** (stay logged in) | 6-digit email code |
| D6 | Default notification time | **09:00** | Any time you like |
| D7 | Streak definition | **Consecutive days with none of *your* chores overdue** | Consecutive days you completed at least one chore (simpler, but easier to game) |
| D8 | Does skip pass the turn? | **No** | Yes |
| D9 | App language | **English** | Dutch, or both |
| D10 | Where the code lives | **Its own new repo**, `chores` (this repo is an unrelated project) | `chores-app/` folder in this repo |
| D11 | Tests | **Only `schedule.ts`**, with Vitest (comes with Vite/SvelteKit) | More coverage |

**Planned packages (the whole list):** the framework, `@supabase/supabase-js`, and `web-push` (inside the Edge Function). No date library, state manager, UI kit or PWA plugin: the service worker is about 30 lines written by hand.

---

## 11. Milestones

**M0 – Setup (about 1 evening)**
- Create the Supabase project and the frontend repo, and deploy a hello-world to the hosting.
- Create both accounts and **turn off sign-ups**.
- Add the manifest and icon so the app can be added to the home screen on both iPhones.

**M1 – Core chores (MVP)**
- Tables, RLS, `schedule.ts` and its tests.
- Chores add/edit, the *Today* and *Upcoming* screens, done and skip, live sync.
- *History* screen.
- ✅ You can actually use it daily from here on.

**M2 – Notifications**
- Service worker, saving the push subscription, the `notify` Edge Function and pg_cron.
- Test on both iPhones.

**M3 – Points and streaks**
- Point values per chore, SQL views, the *Scores* screen.

**M4 – Cooking**
- Meals table, the completion sheet, suggestions on the Cooking card.

**Backlog / ideas**
- Repeat reminders for overdue chores (e.g. an evening nudge).
- Vacation mode that pauses everything and shifts due dates.
- Rooms or categories, with a filter.
- Swap request ("can you do mine today?").
- Monthly stats and charts.
- Offline support and a home-screen badge with the count due.
- The meal features from section 9.

---

## 12. Risks and gotchas

- **The Supabase free tier pauses a project after about 1 week without activity.** Daily use prevents this. If you're away for a long time (holiday), open the app once or unpause it from the dashboard.
- **iOS push only works from the installed home-screen app.** Notifications won't work when the app is opened in a Safari tab.
- **Timezones / DST:** keep "today" calculated in the household timezone in one place.
- **Editing a chore's schedule** recalculates `next_due` from today. Past completions stay as they are.
