"""Chores app: Dash + Mantine UI, SQLite storage, simple session login.

Look and motion live in assets/: style.css (calm iOS-style glass), fx.js (card exits, confetti,
the cat GIF reward) and cats/ (meme cat stickers). Dash loads assets/ automatically.
Phone extras: /manifest.json + assets/icons/ (home-screen app), /api/widget (Scriptable widget,
script in scriptable/), /api/backup (nightly copy to iCloud Drive via Shortcuts).
"""
import base64
import hashlib
import hmac
import os
import secrets
import zlib
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import dash_mantine_components as dmc
from dash import ALL, Dash, Input, Output, State, callback, clientside_callback, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate
from flask import Response, jsonify, redirect, request, session

import settings  # noqa: F401  (loads .env first)
import db

# "Today" in the household's timezone. Unset = this machine's local time (fine on a laptop).
TZ = ZoneInfo(os.environ["APP_TZ"]) if os.environ.get("APP_TZ") else None


def today() -> date:
    return datetime.now(TZ).date()


# iPhones use SF Pro Rounded (ui-rounded); Nunito is the stand-in elsewhere. Anton = Impact, for meme captions.
FONTS = "https://fonts.googleapis.com/css2?family=Anton&family=Nunito:wght@400;600;700;800;900&display=swap"
CAT_GIF = "https://cataas.com/cat/gif?width=320"  # a random cat GIF per URL; fx.js retries if one fails
HERE = os.path.dirname(os.path.abspath(__file__))
CATS_DIR = os.path.join(HERE, "assets", "cats")
# What iOS needs to install the site as a home-screen app. Also in LOGIN_PAGE, since that's the first page.
APP_LINKS = ('<link rel="manifest" href="/manifest.json">'
             '<link rel="apple-touch-icon" href="/assets/icons/apple-touch-icon.png">'
             '<link rel="icon" type="image/png" href="/assets/icons/icon-192.png">')

db.init()
app = Dash(__name__, title="Chores", update_title=None, external_stylesheets=[FONTS], meta_tags=[
    {"name": "viewport", "content": "width=device-width, initial-scale=1, viewport-fit=cover"},
    {"name": "apple-mobile-web-app-capable", "content": "yes"},
    {"name": "apple-mobile-web-app-title", "content": "Chores"},
    {"name": "theme-color", "content": "#e9edf1", "media": "(prefers-color-scheme: light)"},
    {"name": "theme-color", "content": "#0f1317", "media": "(prefers-color-scheme: dark)"},
])
app.index_string = f"""<!DOCTYPE html>
<html lang="en"><head>{{%metas%}}<title>{{%title%}}</title>{APP_LINKS}{{%css%}}</head>
<body>{{%app_entry%}}<footer>{{%config%}}{{%scripts%}}{{%renderer%}}</footer></body></html>"""
server = app.server

# --- Login -------------------------------------------------------------------
secret = os.environ.get("SECRET_KEY")
server.secret_key = secret or secrets.token_hex()  # dev: random key, so logins reset on restart
server.config.update(
    SESSION_COOKIE_SECURE=bool(secret),  # production sets SECRET_KEY and runs on HTTPS
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=365),  # stay logged in on the phone
)

# Plain HTML (assets/ is behind the login), so its styles are inline and Smudge is a data URI.
# Same tokens as assets/style.css.
with open(os.path.join(CATS_DIR, "smudge.png"), "rb") as f:
    SMUDGE = "data:image/png;base64," + base64.b64encode(f.read()).decode()

LOGIN_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Chores">
<meta name="theme-color" content="#e9edf1"><title>Chores</title>{app_links}
<link rel="stylesheet" href="{fonts}">
<style>
:root{--bg:#e9edf1;--m1:#b7d7c4;--m2:#cbc2ec;--m3:#f5cfbd;--m4:#b9d4ee;--glass:rgba(255,255,255,.55);--field:rgba(255,255,255,.6);--hair:rgba(255,255,255,.6);--ink:#1d2430;--sage:#2f7a66;--sage-hi:#3d8c76;--spring:cubic-bezier(.34,1.56,.64,1);--pop:cubic-bezier(.2,.9,.3,1.25);--round:ui-rounded,"SF Pro Rounded",Nunito,system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root{--bg:#0f1317;--m1:#1d4a42;--m2:#392d5c;--m3:#4a302d;--m4:#1b3558;--glass:rgba(255,255,255,.08);--field:rgba(255,255,255,.08);--hair:rgba(255,255,255,.12);--ink:#eef2f5}}
*{box-sizing:border-box}
body{margin:0;min-height:100dvh;display:grid;place-items:center;padding:calc(28px + env(safe-area-inset-top)) 16px 28px;background:var(--bg);color:var(--ink);font-family:var(--round);overflow-x:hidden;-webkit-tap-highlight-color:transparent}
body::before{content:"";position:fixed;inset:-25%;z-index:-1;background:radial-gradient(38% 32% at 18% 16%,var(--m1),transparent 70%),radial-gradient(36% 30% at 86% 28%,var(--m2),transparent 70%),radial-gradient(40% 32% at 22% 82%,var(--m3),transparent 70%),radial-gradient(38% 34% at 84% 86%,var(--m4),transparent 70%)}
main{width:100%;max-width:360px}
.gif{position:relative;z-index:1;width:200px;margin:0 auto -30px;padding:8px;border-radius:22px;background:#fff;transform:rotate(-6deg);box-shadow:0 26px 44px -20px rgba(20,28,40,.5);animation:slap .9s var(--pop) both}
.gif img{display:block;width:100%;aspect-ratio:1;object-fit:cover;border-radius:15px;background:#d9dee5}
.meme{position:absolute;left:10px;right:10px;text-align:center;font:26px/1 Anton,Impact,sans-serif;color:#fff;text-transform:uppercase;text-shadow:2px 2px 0 #000,-2px 2px 0 #000,2px -2px 0 #000,-2px -2px 0 #000,0 2px 0 #000,0 -2px 0 #000,2px 0 0 #000,-2px 0 0 #000}
.meme.t{top:18px}.meme.b{bottom:18px}
form{position:relative;padding:48px 20px 20px;border-radius:32px;background:var(--glass);-webkit-backdrop-filter:blur(22px) saturate(170%);backdrop-filter:blur(22px) saturate(170%);box-shadow:inset 0 1px 0 var(--hair),0 20px 44px -20px rgba(20,28,40,.4);animation:rise .7s var(--spring) .12s both}
.smudge{position:absolute;right:-14px;bottom:-26px;width:96px;transform:rotate(8deg);filter:drop-shadow(2px 0 0 #fff) drop-shadow(-2px 0 0 #fff) drop-shadow(0 2px 0 #fff) drop-shadow(0 -2px 0 #fff) drop-shadow(0 6px 8px rgba(20,28,40,.3));animation:slap .8s var(--pop) .5s both}
h1{margin:0 0 14px;text-align:center;font:900 32px/1 var(--round);letter-spacing:-.035em}
label{display:block;margin:14px 4px 6px;font-weight:800;font-size:14px}
input{display:block;width:100%;height:54px;padding:0 18px;border:1.5px solid var(--hair);border-radius:18px;background:var(--field);color:var(--ink);font:600 17px var(--round);outline:none;transition:border-color .15s,box-shadow .2s}
input:focus{border-color:var(--sage);box-shadow:0 0 0 4px rgba(47,122,102,.2)}
button{display:block;width:100%;height:58px;margin-top:24px;border:0;border-radius:999px;background:linear-gradient(180deg,var(--sage-hi),var(--sage));color:#fff;font:800 18px var(--round);box-shadow:inset 0 1px 0 rgba(255,255,255,.45),0 10px 22px -10px rgba(47,122,102,.8);cursor:pointer;touch-action:manipulation;transition:transform .3s var(--spring),filter .2s}
button:active{transform:scale(.95);filter:brightness(1.12);transition-duration:.08s}
button:focus-visible{outline:3px solid var(--sage);outline-offset:4px}
.err{margin:16px 0 0;padding:11px 14px;border-radius:16px;background:#c2415a;color:#fff;font-weight:800;text-align:center;animation:shake .45s both}
@keyframes slap{from{opacity:0;transform:scale(2.3) rotate(-32deg)}}
@keyframes rise{from{opacity:0;transform:translateY(30px) scale(.96)}to{opacity:1;transform:none}}
@keyframes shake{0%,100%{transform:none}20%,60%{transform:translateX(-8px)}40%,80%{transform:translateX(8px)}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style></head><body><main>
<figure class="gif" aria-hidden="true"><img src="{cat}" alt=""
 onerror="if(!this.dataset.retry){this.dataset.retry=1;this.src+='&amp;n='+Date.now()}else{this.closest('figure').remove()}">
<span class="meme t">Who goes</span><span class="meme b">there</span></figure>
<form method="post"><h1>Chores</h1>
<label for="name">Name</label><input id="name" name="name" autocomplete="username" autocapitalize="none" required>
<label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" required>
<button>Log in</button>{error}<img class="smudge" src="{smudge}" alt=""></form></main></body></html>"""


# Open without a login: the login page, what iOS fetches to install the app (it sends no cookies),
# the cat stickers (the widget draws them), and the two links that carry their own secret key.
PUBLIC_PATHS = {"/login", "/manifest.json", "/api/widget", "/api/backup"}
PUBLIC_PREFIXES = ("/assets/icons/", "/assets/cats/")


@server.before_request
def require_login():
    path = request.path
    if "user_id" in session or path in PUBLIC_PATHS or (path.startswith(PUBLIC_PREFIXES) and ".." not in path):
        return None
    return redirect("/login")


@server.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        user_id = db.login(request.form.get("name", ""), request.form.get("password", ""))
        if user_id:
            session.clear()
            session.permanent = True
            session["user_id"] = user_id
            return redirect("/")
        error = '<p class="err" role="alert">Wrong name or password.</p>'
    return (LOGIN_PAGE.replace("{app_links}", APP_LINKS).replace("{fonts}", FONTS).replace("{cat}", CAT_GIF)
            .replace("{smudge}", SMUDGE).replace("{error}", error))


@server.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@server.route("/manifest.json")
def manifest():
    resp = jsonify(
        name="Chores", short_name="Chores", id="/", start_url="/", scope="/", display="standalone",
        background_color="#e9edf1", theme_color="#e9edf1",
        icons=[{"src": "/assets/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
               {"src": "/assets/icons/icon-512.png", "sizes": "512x512", "type": "image/png"}],
    )
    resp.mimetype = "application/manifest+json"
    return resp


# --- Widget and backup links --------------------------------------------------
# Each person gets their own key per link, derived from SECRET_KEY: nothing to store, and
# changing SECRET_KEY revokes every widget script and backup link at once.
def link_key(kind: str, user_id: int) -> str:
    return hmac.new(server.secret_key.encode(), f"{kind}:{user_id}".encode(), hashlib.sha256).hexdigest()[:32]


def user_for_link(kind: str):
    key = request.args.get("key", "").encode()
    return next((uid for uid in db.users() if hmac.compare_digest(link_key(kind, uid).encode(), key)), None)


@server.route("/api/widget")
def widget_api():
    """Today's chores as JSON for the Scriptable widget (scriptable/chores-widget.js)."""
    uid = user_for_link("widget")
    if uid is None:
        return jsonify(error="This widget script is out of date. Copy a new one from the app."), 403
    users, chores, t = db.users(), db.chores(), today()
    due = due_now(chores, t)
    owner_rank = lambda c: 1 if c["assign"] == "anyone" else 0 if c["assignee_id"] == uid else 2  # noqa: E731
    later = [c for c in chores if c["next_due"] > t.isoformat()]  # chores come sorted by due date
    item = lambda c: {  # noqa: E731
        "title": c["title"], "sticker": sticker_for(c["title"]),
        "when": due_text(date.fromisoformat(c["next_due"]), t), "late": c["next_due"] < t.isoformat(),
        "who": "Either" if c["assign"] == "anyone" else users.get(c["assignee_id"], "?"), "mine": owner_rank(c) == 0,
    }
    resp = jsonify(
        user=users[uid], date=t.isoformat(), headline=today_title(len(due)),
        due=len(due), overdue=sum(c["next_due"] < t.isoformat() for c in due), mine=sum(owner_rank(c) == 0 for c in due),
        mood_image=f"/assets/cats/{mood_file(chores, t)}",
        items=[item(c) for c in sorted(due, key=lambda c: (c["next_due"] >= t.isoformat(), owner_rank(c), c["next_due"]))],
        next=item(later[0]) if later else None,
    )
    resp.headers["Cache-Control"] = "no-store"
    return resp


@server.route("/api/backup")
def backup_api():
    """The whole database as a file, for a Shortcuts automation to save into iCloud Drive."""
    if user_for_link("backup") is None:
        return jsonify(error="This backup link is out of date. Copy a new one from the app."), 403
    return Response(db.snapshot(), mimetype="application/vnd.sqlite3", headers={
        "Content-Disposition": f'attachment; filename="chores-{today().isoformat()}.db"',
        "Cache-Control": "no-store",
    })


# --- Theme -------------------------------------------------------------------
SAGE = ["#eaf5f1", "#d3ebe2", "#a6d6c5", "#77c0a7", "#51ad8f", "#3d9f80", "#348f74", "#2f7a66", "#256656", "#195244"]
ROUNDED = 'ui-rounded, "SF Pro Rounded", Nunito, system-ui, -apple-system, sans-serif'
THEME = {
    "colors": {"sage": SAGE},
    "primaryColor": "sage",
    "primaryShade": {"light": 7, "dark": 6},
    "fontFamily": ROUNDED,
    "headings": {"fontFamily": ROUNDED},
    "defaultRadius": "lg",
    # 16px inputs also stop iOS from zooming in when a field gets focus.
    "components": {name: {"defaultProps": {"size": "md", "radius": "lg"}}
                   for name in ["TextInput", "NumberInput", "Select", "DatePickerInput", "Textarea", "SegmentedControl"]},
}

# --- Views -------------------------------------------------------------------
UNITS = [{"value": "day", "label": "day(s)"}, {"value": "week", "label": "week(s)"}, {"value": "month", "label": "month(s)"}]
MODES = [{"value": "calendar", "label": "Fixed schedule"}, {"value": "after_done", "label": "After last done"}]
ASSIGN = [{"value": "fixed", "label": "One person"}, {"value": "rotate", "label": "Take turns"}, {"value": "anyone", "label": "Either"}]
TABS = [("today", "Today"), ("upcoming", "Upcoming"), ("chores", "Chores"), ("history", "History")]

# The first keyword found in a chore's title picks its sticker; otherwise a stable random one.
STICKERS = [
    ("bin", "🗑️"), ("trash", "🗑️"), ("rubbish", "🗑️"), ("garbage", "🗑️"), ("recycl", "♻️"), ("dish", "🍽️"),
    ("laundry", "🧺"), ("wash", "🫧"), ("cloth", "👕"), ("towel", "🧺"), ("bed", "🛏️"), ("sheet", "🛏️"),
    ("vacuum", "🧹"), ("hoover", "🧹"), ("sweep", "🧹"), ("mop", "🪣"), ("floor", "🧹"), ("dust", "🪶"),
    ("window", "🪟"), ("plant", "🪴"), ("garden", "🌱"), ("lawn", "🌱"), ("cook", "🍳"), ("dinner", "🍝"),
    ("meal", "🍝"), ("shop", "🛒"), ("grocer", "🛒"), ("bath", "🛁"), ("shower", "🚿"), ("toilet", "🚽"),
    ("kitchen", "🧽"), ("fridge", "🧊"), ("litter", "💩"), ("cat", "🐈"), ("dog", "🐕"), ("bill", "💸"),
]
SPARE_STICKERS = ["✨", "🧽", "🫧", "🦆", "🐸", "🍄", "🪩", "🧃", "🐌", "🦄"]
HIDDEN = {"aria-hidden": "true"}


def sticker_for(title: str) -> str:
    t = title.lower()
    return next((s for key, s in STICKERS if key in t), SPARE_STICKERS[zlib.crc32(t.encode()) % len(SPARE_STICKERS)])


def nice_date(d: date) -> str:
    return f"{d:%a} {d.day} {d:%b}"


def due_text(due: date, t: date) -> str:
    days = (due - t).days
    if days < 0:
        return f"{-days} day{'s' if days < -1 else ''} overdue"
    return {0: "Today", 1: "Tomorrow"}.get(days) or nice_date(due)


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def due_now(chores, t: date) -> list:
    """Due today or overdue."""
    return [c for c in chores if c["next_due"] <= t.isoformat()]


def today_title(n: int) -> str:
    return f"{plural(n, 'thing')} to do today" if n else "All clear today"


def mood_file(chores, t: date) -> str:
    """The header cat: screaming if anything is overdue, Smudge if something's due, heart eyes if all clear."""
    dues = [c["next_due"] for c in chores]
    return "scream.png" if any(d < t.isoformat() for d in dues) else "smudge.png" if t.isoformat() in dues else "hearts.png"


def cat(name: str, className: str = ""):
    """A meme cat sticker from assets/cats/. Swap a file for another PNG with the same name to recast it."""
    return html.Img(src=app.get_asset_url(f"cats/{name}"), alt="", className=f"cat {className}".strip())


FACES = ["florian", "rebekka"]  # assets/cats/florian.png and rebekka.png


def avatar(user_id, users: dict):
    """Each person's cat. Matched by name, otherwise by login order (first user gets florian.png)."""
    ids = list(users)
    if user_id not in ids:
        return html.Span("?", className="avatar")
    name = users[user_id]
    face = name.strip().lower() if name.strip().lower() in FACES else FACES[ids.index(user_id) % 2]
    return html.Span(html.Img(src=app.get_asset_url(f"cats/{face}.png"), alt=""),
                     className=f"avatar tone-{FACES.index(face)}", title=name)


def who(c: dict, users: dict, prefix: str = ""):
    if c["assign"] == "anyone":
        return html.Span([html.Span([avatar(i, users) for i in users], className="avatars"), "Either"], className="who")
    return html.Span([avatar(c["assignee_id"], users), prefix + users.get(c["assignee_id"], "?")], className="who")


def chip(text: str, kind: str = ""):
    return html.Span(text, className=f"chip {kind}".strip())


def burst(points: int):
    label = plural(points, "point")
    return html.Span(f"+{points}", className="burst", title=label, role="img", **{"aria-label": label})


def tile(title: str, points: int | None = None):
    """The chore's emoji sticker, with its points starburst slapped on the corner."""
    children = [html.Span(sticker_for(title), className="sticker", **HIDDEN)]
    if points:
        children.append(burst(points))
    return html.Span(children, className="tile")


def headline(text: str, *extra, id=None):
    props = {"id": id} if id else {}
    return html.Div([html.H1(text, className="headline"), *extra], className="hero", **props)


def empty(cat_file: str, text: str, kind: str = ""):
    return html.Div([cat(cat_file, kind), html.P(text)], className="empty")


def chore_card(c: dict, t: date, tab: str, users: dict, i: int, show_owner: bool = False):
    due = date.fromisoformat(c["next_due"])
    late = due < t
    meta = [chip(due_text(due, t), "late" if late else "now" if due == t else "")]
    if show_owner:
        meta.append(who(c, users))
    # fx.js reads these, plays the exit animation, then sends the action to the server.
    target = {"data-chore": str(c["id"]), "data-due": c["next_due"]}
    children = [
        tile(c["title"], c["points"]),
        html.Div([html.Div(c["title"], className="chore__title"), html.Div(meta, className="chore__meta")],
                 className="chore__body"),
        html.Div([
            html.Button("Done", className="btn btn-done", **{"data-act": "done"}, **target),
            html.Button("Skip", className="btn btn-skip", **{"data-act": "skip"}, **target),
        ], className="chore__actions"),
    ]
    if late:
        children.append(cat("scream.png", "corner"))
    # Dash uses the id as React's key, so a card for a new due date mounts fresh (and animates in),
    # while cards that didn't change keep their DOM node through the 60-second refresh.
    return html.Div(children, id=f"{tab}-{c['id']}-{c['next_due']}", className="chore is-late" if late else "chore",
                    style={"--i": i}, **{"data-points": str(c["points"])})


def group(key: str, label: str, count: int, people: list, users: dict):
    faces = html.Span([avatar(p, users) for p in people if p in users], className="avatars")
    return html.Div([faces, html.Span(label), html.Span(str(count), className="count")], id=f"group-{key}", className="group")


def cat_of_the_day(t: date):
    return html.Figure([
        html.Img(src=f"{CAT_GIF}&day={t.isoformat()}", alt="A cat GIF", className="catframe__img"),
        html.Span("No chores", className="meme meme--top", **HIDDEN),
        html.Span("Only nap", className="meme meme--bottom", **HIDDEN),
        cat("cozy.png"),
    ], id="cat-of-the-day", className="catframe")


def today_view(chores, me, users, t):
    due = due_now(chores, t)
    if not due:
        return [headline(today_title(0), id="today-hero"), cat_of_the_day(t)]
    late = sum(date.fromisoformat(c["next_due"]) < t for c in due)
    other = next((i for i in users if i != me), None)
    groups = [
        ("mine", "Mine", [me], [c for c in due if c["assign"] != "anyone" and c["assignee_id"] == me]),
        ("other", users.get(other, "Other"), [other], [c for c in due if c["assign"] != "anyone" and c["assignee_id"] != me]),
        ("either", "Either of us", list(users), [c for c in due if c["assign"] == "anyone"]),
    ]
    out = [headline(today_title(len(due)), *([chip(f"{late} overdue", "late big")] if late else []), id="today-hero")]
    i = 0
    for key, label, people, cs in groups:
        if cs:
            out.append(group(key, label, len(cs), people, users))
            for c in cs:
                out.append(chore_card(c, t, "today", users, i))
                i += 1
    return out


def upcoming_view(chores, users, t):
    soon = [c for c in chores if t < date.fromisoformat(c["next_due"]) <= t + timedelta(days=14)]
    if not soon:
        return empty("campfire.webp", "Nothing in the next two weeks.", "wide")
    return [chore_card(c, t, "upcoming", users, i, show_owner=True) for i, c in enumerate(soon)]


def chore_row(c: dict, users: dict, i: int):
    every = f"Every {c['unit']}" if c["every"] == 1 else f"Every {c['every']} {c['unit']}s"
    when = "on schedule" if c["mode"] == "calendar" else "after last done"
    meta = [chip(f"{every} {when}"), who(c, users, prefix="Next: " if c["assign"] == "rotate" else "")]
    return html.Div([
        tile(c["title"], c["points"]),
        html.Div([html.Div(c["title"], className="chore__title"), html.Div(meta, className="chore__meta")],
                 className="chore__body"),
        html.Button("Edit", id={"edit": c["id"]}, className="btn btn-soft"),
    ], id=f"row-{c['id']}", className="chore", style={"--i": i})


def chores_view(chores, users):
    rows = sorted(chores, key=lambda c: c["title"].lower())
    if not rows:
        return empty("box.png", "No chores yet. Add the first one above.")
    return [chore_row(c, users, i) for i, c in enumerate(rows)]


def history_view(rows, users, total):
    # A 90s hit counter, except it counts chores. The nerd cat would like to point something out.
    counter = html.Div([
        html.Div("Chores done since day one", className="counter__label"),
        html.Div([
            cat("nerd.png"),
            html.Div([html.Span(d, style={"--d": n}) for n, d in enumerate(f"{total:06d}")], className="counter__digits"),
        ], className="counter__row"),
    ], id="counter", className="counter")
    if not rows:
        return [empty("hmm.png", "Nothing done yet.", "photo"), counter]
    ids = {name: i for i, name in users.items()}
    items = [html.Li([
        avatar(ids.get(r["name"]), users),
        html.Div([
            html.Div([f"{r['name']} {'skipped' if r['skipped'] else 'did'} ", html.B(r["title"])]),
            html.Div(nice_date(date.fromisoformat(r["done_on"])), className="log__date"),
        ], className="log__text"),
        html.Span("Skipped", className="stamp") if r["skipped"] else burst(r["points"]),
    ], className="log__row") for r in rows]
    return [html.Ol(items, id="log", className="log"), counter]


def ticker(chores, t, total):
    """The marquee at the top: live numbers plus nonsense, in the grand tradition of 1999."""
    due = due_now(chores, t)
    late = sum(date.fromisoformat(c["next_due"]) < t for c in due)
    later = [c for c in chores if date.fromisoformat(c["next_due"]) > t]  # already sorted by due date
    bits = [f"{len(due)} due today" if due else "nothing due today",
            f"{late} overdue" if late else "0 overdue (wow)"]
    if later:
        bits.append(f"next up: {later[0]['title']}, {due_text(date.fromisoformat(later[0]['next_due']), t)}")
    bits += [f"{total} chores done all time", "cat tax: paid", "best viewed on iPhone", "no cats were harmed"]
    run = lambda: html.Div([x for b in bits for x in (html.Span(b), cat("pixel.png"))], className="ticker__run")  # noqa: E731
    return [run(), run()]  # two copies, so the loop is seamless


WIDGET_SCRIPT = open(os.path.join(HERE, "scriptable", "chores-widget.js")).read()


def setup_sheet(uid: int):
    """The sheet behind your name: install, widget, backup, log out.
    Links carry __ORIGIN__, which fx.js swaps for the address the app is open on when copying."""
    widget = WIDGET_SCRIPT.replace("__KEY__", link_key("widget", uid))
    backup = f"__ORIGIN__/api/backup?key={link_key('backup', uid)}"
    return html.Div(className="setup", children=[
        html.Section(className="setup__item setup__install", children=[
            cat("hearts.png", "setup__cat"),
            html.H3("Put Chores on your home screen"),
            html.P("Open this site in Safari, tap Share, then Add to Home Screen. Log in once more inside the new app."),
        ]),
        html.Section(className="setup__item", children=[
            cat("nerd.png", "setup__cat"),
            html.H3("Widget"),
            html.Ol([
                html.Li("Install Scriptable from the App Store."),
                html.Li("Copy the script, open Scriptable, tap +, paste it and name it Chores."),
                html.Li("Add a Scriptable widget to your home or lock screen, edit it and pick Chores."),
            ]),
            html.Button("Copy widget script", className="btn btn-done btn-wide",
                        **{"data-copy": widget, "data-copied": "Widget script copied"}),
        ]),
        html.Section(className="setup__item", children=[
            cat("box.png", "setup__cat"),
            html.H3("Nightly backup to iCloud Drive"),
            html.Ol([
                html.Li("Copy the backup link."),
                html.Li("In Shortcuts, go to Automation, add a daily Time of Day automation and set it to Run Immediately."),
                html.Li("Give it two actions: Get Contents of URL with the link, then Save File to iCloud Drive "
                        "with Ask Where to Save turned off."),
            ]),
            html.Button("Copy backup link", className="btn btn-soft btn-wide",
                        **{"data-copy": backup, "data-copied": "Backup link copied"}),
        ]),
        html.P("Anyone with these links can see your chores without logging in, so keep them to yourselves.",
               className="setup__note"),
        html.A("Log out", href="/logout", className="btn btn-danger btn-wide btn-logout"),
    ])


def chore_form(users):
    return dmc.Stack(gap="md", children=[
        dmc.TextInput(id="f-title", label="Chore", placeholder="Take out the bins"),
        dmc.Group(grow=True, children=[
            dmc.NumberInput(id="f-every", label="Every", min=1, allowDecimal=False, allowNegative=False),
            dmc.Select(id="f-unit", label="Unit", data=UNITS, allowDeselect=False),
        ]),
        dmc.SegmentedControl(id="f-mode", data=MODES, fullWidth=True, color="sage", withItemsBorders=False),
        dmc.DatePickerInput(id="f-due", label="Next due", valueFormat="ddd D MMM YYYY", dropdownType="modal",
                            modalProps={"radius": 28, "centered": True}),
        dmc.SegmentedControl(id="f-assign", data=ASSIGN, fullWidth=True, color="sage", withItemsBorders=False),
        dmc.Select(id="f-assignee", label="Who", data=[{"value": str(i), "label": n} for i, n in users.items()], allowDeselect=False),
        dmc.NumberInput(id="f-points", label="Points", description="Effort: 1 quick, 2 normal, 3 big job", min=1, max=5, allowDecimal=False),
        dmc.Textarea(id="f-notes", label="Notes", autosize=True, minRows=1),
        html.Div(id="f-error", className="form-error", role="alert"),
        html.Div(className="form-actions", children=[
            html.Button("Archive", id="f-archive", className="btn btn-danger"),
            html.Button("Save", id="f-save", className="btn btn-done btn-save"),
        ]),
    ])


def panel(tab: str, *children):
    return html.Div(list(children), id=f"{tab}-panel", className="panel is-on" if tab == "today" else "panel")


def layout():
    users = db.users()
    return dmc.MantineProvider(theme=THEME, defaultColorScheme="auto", children=html.Div(className="app", children=[
        dcc.Store(id="version", data=0),
        dcc.Store(id="editing"),
        dcc.Store(id="pending"),  # fx.js puts Done/Skip taps here once their exit animation has played
        dcc.Interval(id="tick", interval=60_000),  # picks up changes made on the other phone
        html.Div(html.Div(html.Div(id="ticker", className="ticker__track"), className="ticker", **HIDDEN),
                 className="shell-top"),
        html.Main(className="shell", children=[
            html.Header(className="top", children=[
                html.Div([html.Span("Chores", className="wordmark"), html.Span(id="mood", className="mood", **HIDDEN)],
                         className="brand"),
                html.Button(id="me", className="btn me", title="Settings"),
            ]),
            panel("today", html.Div(id="today-list")),
            panel("upcoming", headline("Next two weeks"), html.Div(id="upcoming-list")),
            panel("chores", headline("All chores"),
                  html.Button([html.Span("+", className="plus", **HIDDEN), "Add chore"], id="add", className="btn btn-add"),
                  html.Div(id="chores-list")),
            panel("history", headline("Done lately"), html.Div(id="history-list")),
        ]),
        html.Nav(className="dock", children=dmc.SegmentedControl(
            id="tab", data=[{"value": v, "label": label} for v, label in TABS], value="today",
            persistence=True, persistence_type="local", fullWidth=True, radius="xl", withItemsBorders=False,
            transitionDuration=450, transitionTimingFunction="cubic-bezier(.3,1.45,.5,1)",
            classNames={"root": "dock__root", "indicator": "dock__indicator", "control": "dock__control", "label": "dock__label"},
        )),
        dmc.Modal(id="modal", title="Chore", children=chore_form(users), **SHEET),
        dmc.Modal(id="me-sheet", children=html.Div(id="me-sheet-body"), **SHEET),
    ]))


SHEET = dict(  # shared look for the bottom sheets
    radius=32,
    transitionProps={"transition": "slide-up", "duration": 420, "timingFunction": "cubic-bezier(.22,1.2,.36,1)"},
    overlayProps={"backgroundOpacity": 0.5, "blur": 6},
    classNames={"inner": "sheet-inner", "content": "sheet", "header": "sheet__header", "title": "sheet__title",
                "body": "sheet__body", "close": "sheet__close"},
)


app.layout = layout


# --- Callbacks ---------------------------------------------------------------
@callback(
    Output("today-list", "children"), Output("upcoming-list", "children"), Output("chores-list", "children"),
    Output("history-list", "children"), Output("me", "children"), Output("ticker", "children"), Output("mood", "children"),
    Input("version", "data"), Input("tick", "n_intervals"),
)
def render(*_):
    me, users, chores, t = session["user_id"], db.users(), db.chores(), today()
    total = db.done_count()
    return (today_view(chores, me, users, t), upcoming_view(chores, users, t), chores_view(chores, users),
            history_view(db.history(), users, total), [avatar(me, users), html.Span(users.get(me, ""))],
            ticker(chores, t, total), cat(mood_file(chores, t)))


@callback(
    Output("me-sheet", "opened"), Output("me-sheet", "title"), Output("me-sheet-body", "children"),
    Input("me", "n_clicks"),
    prevent_initial_call=True,
)
def open_setup(n):
    if not n:
        raise PreventUpdate
    uid = session["user_id"]
    return True, f"Hi {db.users().get(uid, '')}", setup_sheet(uid)


# Tabs: the dock's sliding pill picks which panel shows. Showing a panel replays its entrance animations.
clientside_callback(
    """function (tab) {
        const tabs = ["today", "upcoming", "chores", "history"];
        if (!tabs.includes(tab)) tab = "today";
        window.scrollTo({top: 0});
        return tabs.map(v => v === tab ? "panel is-on" : "panel");
    }""",
    *[Output(f"{v}-panel", "className") for v, _ in TABS],
    Input("tab", "value"),
)


def clicked() -> bool:
    """False when a pattern-matched button was just (re)rendered rather than tapped."""
    return bool(ctx.triggered_id) and bool(ctx.triggered[0]["value"])


@callback(
    Output("version", "data"),
    Input("pending", "data"),
    State("version", "data"),
    prevent_initial_call=True,
)
def act(pending, version):
    """Done/Skip taps, batched by fx.js. Each carries the due date its button showed,
    so a double tap or both phones at once still only counts once (see db.complete)."""
    actions = (pending or {}).get("actions") or []
    for a in actions:
        try:
            chore_id, due, kind = int(a["chore"]), date.fromisoformat(a["due"]).isoformat(), a["act"]
        except (KeyError, TypeError, ValueError):
            continue
        if kind in {"done", "skip"}:
            db.complete(chore_id, session["user_id"], due, kind == "skip", today())
    return version + 1  # refresh even if it was already handled on the other phone


FORM = ["title", "every", "unit", "mode", "due", "assign", "assignee", "points", "notes"]


@callback(
    Output("modal", "opened"), Output("modal", "title"), Output("editing", "data"),
    *[Output(f"f-{k}", "value") for k in FORM],
    Output("f-error", "children"), Output("f-archive", "style"),
    Input("add", "n_clicks"), Input({"edit": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def open_form(*_):
    if not clicked():
        raise PreventUpdate
    if ctx.triggered_id == "add":
        c = {"id": None, "title": "", "every": 1, "unit": "week", "mode": "calendar", "next_due": today().isoformat(),
             "assign": "fixed", "assignee_id": session["user_id"], "points": 1, "notes": ""}
    else:
        c = db.chore(ctx.triggered_id["edit"])
    assignee = str(c["assignee_id"]) if c["assignee_id"] else str(session["user_id"])
    return (True, "New chore" if c["id"] is None else "Edit chore", c["id"], c["title"], c["every"], c["unit"],
            c["mode"], c["next_due"], c["assign"], assignee, c["points"], c["notes"], "",
            {"display": "none"} if c["id"] is None else {})


@callback(Output("f-assignee", "style"), Output("f-assignee", "label"), Input("f-assign", "value"))
def assignee_field(assign):
    return ({"display": "none"} if assign == "anyone" else {}), ("Whose turn is next" if assign == "rotate" else "Who")


def validate(title, every, unit, mode, due, assign, assignee, points, notes) -> dict:
    title = (title or "").strip()
    if not title:
        raise ValueError("Give the chore a name.")
    if not isinstance(every, int) or every < 1:
        raise ValueError("'Every' must be 1 or more.")
    if unit not in {"day", "week", "month"} or mode not in {"calendar", "after_done"} or assign not in {"fixed", "rotate", "anyone"}:
        raise ValueError("Pick how often and who does it.")
    try:
        due = date.fromisoformat(due)
    except (TypeError, ValueError):
        raise ValueError("Pick a due date.")
    assignee_id = None
    if assign != "anyone":
        if not assignee or int(assignee) not in db.users():
            raise ValueError("Pick who does it.")
        assignee_id = int(assignee)
    if not isinstance(points, int) or points < 1:
        raise ValueError("Points must be 1 or more.")
    return {"title": title, "notes": (notes or "").strip(), "mode": mode, "every": every, "unit": unit, "assign": assign,
            "assignee_id": assignee_id, "points": points, "next_due": due.isoformat(), "anchor_day": due.day}


@callback(
    Output("modal", "opened", allow_duplicate=True), Output("f-error", "children", allow_duplicate=True),
    Output("version", "data", allow_duplicate=True),
    Input("f-save", "n_clicks"), Input("f-archive", "n_clicks"),
    State("editing", "data"), *[State(f"f-{k}", "value") for k in FORM], State("version", "data"),
    prevent_initial_call=True,
)
def save(_, __, chore_id, *values):
    *fields, version = values
    if ctx.triggered_id == "f-archive":
        db.archive(chore_id)
    else:
        try:
            db.save_chore(chore_id, validate(*fields))
        except ValueError as e:
            return no_update, str(e), no_update
    return False, "", version + 1


if __name__ == "__main__":
    app.run(debug=True)  # HOST=0.0.0.0 to open it from your phone on the same wifi
