# Chores

A chores app for two people: Python Dash + dash-mantine-components, with SQLite storage. It runs on Railway and is used from the iPhone home screen, with a widget and nightly backups to iCloud Drive. See [PLAN.md](PLAN.md) for the plan.

## Run it on your Mac

```zsh
cd chores-app
python3 -m venv .venv              # first time only
source .venv/bin/activate          # every new terminal; the prompt then starts with (.venv)
pip install -r requirements.txt    # first time only
python db.py adduser Florian       # asks for a password; run once per person
python db.py adduser Rebekka
python app.py                      # http://127.0.0.1:8050
```

To try it on your phones over home wifi, run `HOST=0.0.0.0 python app.py`, find the Mac's address with `ipconfig getifaddr en0`, and open `http://<that address>:8050`. Don't put `SECRET_KEY` in your local `.env`: it makes the login cookie HTTPS-only, so logging in over plain `http://` would fail.

Tests: `python test_schedule.py` and `python test_login.py`

## Settings

Settings go in a `.env` file next to the code. Copy [.env.example](.env.example) to `.env` and fill it in. `.env` is gitignored, so it never gets committed. Real environment variables take priority over it; on Railway they're service variables (see below).

| Name | What it does |
|---|---|
| `SECRET_KEY` | **Set this on the server.** It signs the login cookie and the widget and backup links, and turns on HTTPS-only cookies. Generate one with `python -c "import secrets; print(secrets.token_hex())"`. Changing it logs you both out and breaks existing widget scripts and backup links. Copy new ones from the app afterwards. |
| `APP_TZ` | Your timezone (an IANA name such as `Europe/Berlin`). It decides what "today" means; servers usually run on UTC. If unset, the machine's local time is used. |
| `CHORES_DB` | Path of the SQLite file. Default: `chores.db` next to the code. |
| `HOST` / `PORT` | Where `python app.py` listens. Defaults: `127.0.0.1:8050`. |

## Deploy on Railway

Live at **https://individualproject-production-223ccbdd.up.railway.app**, on [Railway](https://railway.com): project *peaceful-prosperity*, service *Individual_Project*, region EU West (Amsterdam). Railway's builder (Railpack) installs `requirements.txt` on Python 3.13.

How the service is set up (service → **Settings** and **Variables**):

| Setting | Value | Why |
|---|---|---|
| Source | this repo, branch `claude/chores-webapp-planning-s28xvt`, root directory `/chores-app` | Every push to the branch redeploys. |
| Start command | `python -c "from app import app; app.run()"` | **Not** `python app.py`: that runs with `debug=True`, and the debugger lets anyone run code on the server. Dash reads `HOST` and `PORT` from the environment; debug stays off. |
| Healthcheck path | `/login` | A new deploy only goes live once this page answers. |
| Volume | mounted at `/data` | Holds the database, so it survives redeploys. |
| Variables | `HOST=0.0.0.0`, `APP_TZ=Europe/Amsterdam`, `CHORES_DB=/data/chores.db`, `SECRET_KEY` | Railway sets `PORT` itself (8080); the public domain points at that port. |

The web server is Werkzeug's built-in one: a single process with threads, which is plenty for two people. Switching to gunicorn would be a new dependency; only worth it if the app ever gets slow.

**Logins:** service → **Console** (a shell on the server), then `/app/.venv/bin/python db.py adduser NAME`. It asks for the password. Running it again for an existing name resets that password. Plain `python` isn't on the Console's PATH.

**Updating:** push to the branch. Railway builds, waits for the healthcheck, then switches over; follow it under **Deployments**. Changing a variable also needs **Deploy** on the staged-changes bar.

**Backups:** the iPhone Shortcuts automation below saves a copy into iCloud Drive every night. Restoring means putting that file at `/data/chores.db` and restarting the service; this hasn't been tried on Railway yet (see PLAN.md).

**Cost:** a trial (30 days or $5 of usage), then the Hobby plan: $5/month including $5 of usage, which this app should stay within.

## On your iPhones

Everything below is also explained inside the app: tap your name at the top right.

### Install it as an app

Open the app's address in **Safari** and log in. Tap **Share → Add to Home Screen**. On iOS 26 it opens as its own full-screen app with the Smudge icon. The home-screen app keeps its own login, separate from Safari, so log in once more inside it. The login then lasts a year.

### Widget (home screen or lock screen)

iPhone widgets need a native app, so the widget runs in [Scriptable](https://apps.apple.com/app/scriptable/id1405459188), a free app that runs small JavaScript widgets.

1. Install Scriptable.
2. In Chores, tap your name, then **Copy widget script**. The copy has the address and your personal key filled in.
3. In Scriptable, tap **+**, paste, and name the script **Chores**.
4. Long-press the home screen → **Edit → Add Widget → Scriptable**, then pick a size: small, medium or large. Tap the new widget while it jiggles and set **Script** to Chores. It works on the lock screen too, in the rectangular, inline and circular slots.

It shows the same headline and mood cat as the app, and lists what's due: overdue first, then yours, then shared, then the other person's. It refreshes about every 15 minutes, whenever iOS allows. Tapping it opens Chores in Safari, which can't open the home-screen app directly. The script's source is [scriptable/chores-widget.js](scriptable/chores-widget.js).

### Nightly backup to iCloud Drive

A web app can't use iCloud as its database, so the data lives on the server. A Shortcuts automation on one of your phones saves a copy into iCloud Drive every night.

1. In Chores, tap your name, then **Copy backup link**.
2. Open **Shortcuts → Automation → + → Time of Day**. Pick a time, such as 03:00, set it to **Daily** and **Run Immediately**, then tap Next → New Blank Automation.
3. Add **Get Contents of URL** and paste the link.
4. Add **Save File**. Turn **Ask Where to Save** off, choose a folder in iCloud Drive, and set the subpath to `Chores/chores-` + the **Current Date** variable + `.db`. Tap the date variable and set its format to Custom `yyyy-MM-dd`. Turn **Overwrite If File Exists** on.

Each copy is a complete SQLite file, so it can be restored as described under "Backups" in the Railway section.

**Keep the widget script and backup link private.** They work without a password. Changing `SECRET_KEY` revokes all of them.

## Files

- `app.py`: login, the screens, the callbacks, `/manifest.json`, `/api/widget` and `/api/backup`.
- `db.py`: the SQLite schema and queries, plus the `adduser` and `backup` commands.
- `schedule.py`: due-date calculations. `test_schedule.py` tests them.
- `test_login.py`: checks the brake on wrong passwords (10 misses in 15 minutes locks the login form).
- `settings.py`: reads `.env`.
- `scriptable/chores-widget.js`: the widget. The app fills in `__ORIGIN__` and `__KEY__` when you copy it.
- `assets/`: Dash serves everything here, and loads the CSS and JS into every page automatically.
  - `style.css`: the look (calm iOS-style glass; colours are tokens at the top).
  - `fx.js`: the motion. Done/Skip play the card's exit animation before telling the server, then confetti and a cat GIF. Also the copy buttons.
  - `icons/`: the home-screen icon.
  - `cats/`: the meme cat stickers. To recast one, drop in another image with the same file name.

Without a login, only these respond: `/login`, `/manifest.json`, `assets/icons/`, `assets/cats/`, and the two key-protected `/api/` links.

## The cats

| File | Where it shows up |
|---|---|
| `florian.png`, `rebekka.png` | Your avatars. Matched by login name; otherwise the first login gets `florian.png`. |
| `smudge.png` / `scream.png` / `hearts.png` | The header cat, also in the widget: something's due / something's overdue / all clear. Smudge also guards the login page and is the app icon. |
| `scream.png` | Sticker on overdue cards. |
| `thumbs.png` | The Skip toast ("Skipped. It's fine."). |
| `dance.webp` | Dances next to the cat GIF when you tap Done. |
| `cozy.png`, `campfire.webp`, `box.png`, `hmm.png` | Empty screens: Today, Upcoming, Chores, History. |
| `nerd.png` | Next to the hit counter on History. |
| `pixel.png` | Between the items in the marquee. |

They're Twitch emotes from FrankerFaceZ. The reward GIFs come from [cataas.com](https://cataas.com) at runtime. If that site is down, the app falls back to a 😹 sticker. If you swap `smudge.png`, the app icon in `assets/icons/` stays the same until it's regenerated.
