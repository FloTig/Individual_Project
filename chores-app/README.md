# Chores

A chores app for two people: Python Dash + dash-mantine-components, with SQLite storage. It runs on a small server and is used from the iPhone home screen, with a widget and nightly backups to iCloud Drive. See [PLAN.md](PLAN.md) for the plan.

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

Tests: `python test_schedule.py`

## Settings

Settings go in a `.env` file next to the code. Copy [.env.example](.env.example) to `.env` and fill it in. `.env` is gitignored, so it never gets committed. Real environment variables take priority over it.

| Name | What it does |
|---|---|
| `SECRET_KEY` | **Set this on the server.** It signs the login cookie and the widget and backup links, and turns on HTTPS-only cookies. Generate one with `python -c "import secrets; print(secrets.token_hex())"`. Changing it logs you both out and breaks existing widget scripts and backup links. Copy new ones from the app afterwards. |
| `APP_TZ` | Your timezone (an IANA name such as `Europe/Berlin`). It decides what "today" means; servers usually run on UTC. If unset, the machine's local time is used. |
| `CHORES_DB` | Path of the SQLite file. Default: `chores.db` next to the code. |
| `HOST` / `PORT` | Where `python app.py` listens. Defaults: `127.0.0.1:8050`. |

## Deploy on PythonAnywhere

The free account is enough to start: one web app at `<username>.pythonanywhere.com`, with HTTPS. Its servers can only reach an allowlist of websites. That doesn't matter yet: the cat GIFs load on your phones, not on the server. Push notifications (M2) may need the paid plan later. Free web apps also have to be renewed every few months with a button on the Web tab; PythonAnywhere emails a reminder.

1. **Get the code there.** Create an account, open a **Bash console** (Consoles tab) and run:
   ```bash
   git clone -b claude/chores-webapp-planning-s28xvt https://github.com/FloTig/Individual_Project.git
   cd Individual_Project/chores-app
   python3.12 -m venv ~/.virtualenvs/chores      # or the newest Python 3 offered (3.10+)
   source ~/.virtualenvs/chores/bin/activate
   pip install -r requirements.txt
   ```
   If the GitHub repo is private, git asks for a password: use a GitHub personal access token.
2. **Settings and logins.** In the same console:
   ```bash
   cp .env.example .env
   python -c "import secrets; print(secrets.token_hex())"   # copy the output
   nano .env                                                # paste it after SECRET_KEY=, check APP_TZ; Ctrl+O, Enter, Ctrl+X
   python db.py adduser Florian
   python db.py adduser Rebekka
   ```
3. **Create the web app.** On the **Web** tab: Add a new web app → Manual configuration (not "Flask") → the same Python version. Then on that page:
   - **Source code:** `/home/<username>/Individual_Project/chores-app`
   - **Virtualenv:** `/home/<username>/.virtualenvs/chores`
   - **WSGI configuration file:** open it, delete everything, and paste:
     ```python
     import sys
     sys.path.insert(0, "/home/<username>/Individual_Project/chores-app")
     from app import server as application  # settings come from chores-app/.env
     ```
   - **Force HTTPS:** on.
   - Press **Reload**, then open `https://<username>.pythonanywhere.com`.
4. **Server-side backups.** On the **Tasks** tab, add a daily task (the free plan allows one). It keeps the newest 30 copies:
   ```bash
   /home/<username>/.virtualenvs/chores/bin/python /home/<username>/Individual_Project/chores-app/db.py backup /home/<username>/backups
   ```

**Updating later:** open a Bash console, run `cd ~/Individual_Project && git pull`, then press **Reload** on the Web tab. If `requirements.txt` changed, run `pip install -r chores-app/requirements.txt` first, with the virtualenv active.

**Restoring a backup:** on the Files tab, upload the backup file over `chores-app/chores.db` (or wherever `CHORES_DB` points), then press Reload.

## On your iPhones

Everything below is also explained inside the app: tap your name at the top right.

### Install it as an app

Open your PythonAnywhere address in **Safari** and log in. Tap **Share → Add to Home Screen**. On iOS 26 it opens as its own full-screen app with the Smudge icon. The home-screen app keeps its own login, separate from Safari, so log in once more inside it. The login then lasts a year.

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

Each copy is a complete SQLite file, so it can be restored as described in "Restoring a backup".

**Keep the widget script and backup link private.** They work without a password. Changing `SECRET_KEY` revokes all of them.

## Files

- `app.py`: login, the screens, the callbacks, `/manifest.json`, `/api/widget` and `/api/backup`.
- `db.py`: the SQLite schema and queries, plus the `adduser` and `backup` commands.
- `schedule.py`: due-date calculations. `test_schedule.py` tests them.
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
