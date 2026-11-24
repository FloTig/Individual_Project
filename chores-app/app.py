"""Chores app: Dash + Mantine UI, SQLite storage, simple session login."""
import os
import secrets
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import dash_mantine_components as dmc
from dash import ALL, Dash, Input, Output, State, callback, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate
from flask import redirect, request, session

import db

# "Today" in the household's timezone. Unset = this machine's local time (fine on a laptop).
TZ = ZoneInfo(os.environ["APP_TZ"]) if os.environ.get("APP_TZ") else None


def today() -> date:
    return datetime.now(TZ).date()


db.init()
app = Dash(__name__, title="Chores", update_title=None, meta_tags=[
    {"name": "apple-mobile-web-app-capable", "content": "yes"},
    {"name": "apple-mobile-web-app-title", "content": "Chores"},
])
server = app.server

# --- Login -------------------------------------------------------------------
secret = os.environ.get("SECRET_KEY")
server.secret_key = secret or secrets.token_hex()  # dev: random key, so logins reset on restart
server.config.update(
    SESSION_COOKIE_SECURE=bool(secret),  # production sets SECRET_KEY and runs on HTTPS
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=365),  # stay logged in on the phone
)

LOGIN_PAGE = """<!doctype html><html><head>
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Chores</title>
<style>:root{color-scheme:light dark}body{font-family:system-ui;max-width:20rem;margin:20vh auto;padding:0 1rem}
input,button{display:block;width:100%;margin:.5rem 0;padding:.7rem;font-size:1rem;box-sizing:border-box}</style>
</head><body><h2>Chores</h2><form method="post">
<input name="name" placeholder="Name" autocomplete="username" required>
<input name="password" type="password" placeholder="Password" autocomplete="current-password" required>
<button>Log in</button></form><p style="color:#d33">{error}</p></body></html>"""


@server.before_request
def require_login():
    if "user_id" not in session and request.path != "/login":
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
        error = "Wrong name or password."
    return LOGIN_PAGE.replace("{error}", error)


@server.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# --- Views -------------------------------------------------------------------
UNITS = [{"value": "day", "label": "day(s)"}, {"value": "week", "label": "week(s)"}, {"value": "month", "label": "month(s)"}]
MODES = [{"value": "calendar", "label": "Fixed schedule"}, {"value": "after_done", "label": "After last done"}]
ASSIGN = [{"value": "fixed", "label": "One person"}, {"value": "rotate", "label": "Take turns"}, {"value": "anyone", "label": "Either"}]
TABS = [("today", "Today"), ("upcoming", "Upcoming"), ("chores", "Chores"), ("history", "History")]


def nice_date(d: date) -> str:
    return f"{d:%a} {d.day} {d:%b}"


def due_text(due: date, t: date) -> str:
    days = (due - t).days
    if days < 0:
        return f"{-days} day{'s' if days < -1 else ''} overdue"
    return {0: "today", 1: "tomorrow"}.get(days) or nice_date(due)


def who(c: dict, users: dict) -> str:
    return "either" if c["assign"] == "anyone" else users.get(c["assignee_id"], "?")


def describe(c: dict, users: dict) -> str:
    every = f"Every {c['unit']}" if c["every"] == 1 else f"Every {c['every']} {c['unit']}s"
    when = "on schedule" if c["mode"] == "calendar" else "after last done"
    owner = {"fixed": who(c, users), "rotate": f"turns, next: {who(c, users)}", "anyone": "either"}[c["assign"]]
    return f"{every} {when} · {owner} · {c['points']} pt"


def empty(text: str):
    return dmc.Text(text, c="dimmed", ta="center", py="xl")


def card(title: str, subtitle: str, buttons: list, late: bool = False):
    return dmc.Paper(withBorder=True, p="sm", radius="md", children=dmc.Group(justify="space-between", wrap="nowrap", children=[
        dmc.Stack(gap=0, children=[dmc.Text(title, fw=500), dmc.Text(subtitle, size="sm", c="red" if late else "dimmed")]),
        dmc.Group(buttons, gap=4, wrap="nowrap"),
    ]))


def chore_card(c: dict, t: date, tab: str, owner: str | None = None):
    due = date.fromisoformat(c["next_due"])
    ids = {"chore": c["id"], "due": c["next_due"], "tab": tab}
    return card(c["title"], " · ".join(filter(None, [due_text(due, t), owner, f"{c['points']} pt"])), [
        dmc.Button("Skip", id={"act": "skip", **ids}, size="xs", variant="subtle", color="gray"),
        dmc.Button("Done", id={"act": "done", **ids}, size="xs"),
    ], late=due < t)


def section(title: str, rows: list):
    return dmc.Stack([dmc.Text(title, fw=700, size="xs", c="dimmed", tt="uppercase"), *rows], gap="xs", mb="md")


def today_view(chores, me, users, t):
    due = [c for c in chores if date.fromisoformat(c["next_due"]) <= t]
    other = next((n for i, n in users.items() if i != me), "Other")
    groups = [
        ("Mine", [c for c in due if c["assign"] != "anyone" and c["assignee_id"] == me]),
        (other, [c for c in due if c["assign"] != "anyone" and c["assignee_id"] != me]),
        ("Either of us", [c for c in due if c["assign"] == "anyone"]),
    ]
    return [section(name, [chore_card(c, t, "today") for c in cs]) for name, cs in groups if cs] or empty("Nothing due today 🎉")


def upcoming_view(chores, users, t):
    soon = [c for c in chores if t < date.fromisoformat(c["next_due"]) <= t + timedelta(days=14)]
    return dmc.Stack([chore_card(c, t, "upcoming", who(c, users)) for c in soon], gap="xs") if soon else empty("Nothing in the next two weeks.")


def chores_view(chores, users):
    rows = [card(c["title"], describe(c, users), [dmc.Button("Edit", id={"edit": c["id"]}, size="xs", variant="light")])
            for c in sorted(chores, key=lambda c: c["title"].lower())]
    return dmc.Stack(rows, gap="xs") if rows else empty("No chores yet.")


def history_view(rows):
    if not rows:
        return empty("Nothing done yet.")
    return dmc.Stack(gap=6, children=[
        dmc.Text([dmc.Text(nice_date(date.fromisoformat(r["done_on"])), span=True, c="dimmed"),
                  f"  {r['name']} {'skipped' if r['skipped'] else 'did'} {r['title']}",
                  "" if r["skipped"] else f" (+{r['points']})"], size="sm")
        for r in rows
    ])


def chore_form(users):
    return dmc.Stack(gap="sm", children=[
        dmc.TextInput(id="f-title", label="Chore", placeholder="Take out the bins"),
        dmc.Group(grow=True, children=[
            dmc.NumberInput(id="f-every", label="Every", min=1, allowDecimal=False, allowNegative=False),
            dmc.Select(id="f-unit", label="Unit", data=UNITS, allowDeselect=False),
        ]),
        dmc.SegmentedControl(id="f-mode", data=MODES, fullWidth=True),
        dmc.DatePickerInput(id="f-due", label="Next due", valueFormat="ddd D MMM YYYY", dropdownType="modal"),
        dmc.SegmentedControl(id="f-assign", data=ASSIGN, fullWidth=True),
        dmc.Select(id="f-assignee", label="Who", data=[{"value": str(i), "label": n} for i, n in users.items()], allowDeselect=False),
        dmc.NumberInput(id="f-points", label="Points", description="Effort: 1 quick, 2 normal, 3 big job", min=1, max=5, allowDecimal=False),
        dmc.Textarea(id="f-notes", label="Notes", autosize=True, minRows=1),
        dmc.Text(id="f-error", c="red", size="sm"),
        dmc.Group(justify="space-between", children=[
            dmc.Button("Archive", id="f-archive", color="red", variant="subtle"),
            dmc.Button("Save", id="f-save"),
        ]),
    ])


def layout():
    users = db.users()
    panels = {"chores": [dmc.Button("+ Add chore", id="add", fullWidth=True, mb="xs")]}
    return dmc.MantineProvider(defaultColorScheme="auto", children=dmc.Container(size="xs", px="sm", py="md", children=[
        dcc.Store(id="version", data=0),
        dcc.Store(id="editing"),
        dcc.Interval(id="tick", interval=60_000),  # picks up changes made on the other phone
        dmc.Group(justify="space-between", mb="sm", children=[
            dmc.Title("Chores", order=3),
            dmc.Anchor(id="me", href="/logout", refresh=True, size="sm"),
        ]),
        dmc.Tabs(value="today", persistence=True, persistence_type="local", children=[
            dmc.TabsList(grow=True, children=[dmc.TabsTab(label, value=v) for v, label in TABS]),
            *[dmc.TabsPanel([*panels.get(v, []), html.Div(id=f"{v}-list")], value=v, pt="sm") for v, _ in TABS],
        ]),
        dmc.Modal(id="modal", title="Chore", children=chore_form(users)),
    ]))


app.layout = layout


# --- Callbacks ---------------------------------------------------------------
@callback(
    Output("today-list", "children"), Output("upcoming-list", "children"),
    Output("chores-list", "children"), Output("history-list", "children"), Output("me", "children"),
    Input("version", "data"), Input("tick", "n_intervals"),
)
def render(*_):
    users, chores, t = db.users(), db.chores(), today()
    return (today_view(chores, session["user_id"], users, t), upcoming_view(chores, users, t),
            chores_view(chores, users), history_view(db.history()), f"{users.get(session['user_id'], '')} · log out")


def clicked() -> bool:
    """False when a pattern-matched button was just (re)rendered rather than tapped."""
    return bool(ctx.triggered_id) and bool(ctx.triggered[0]["value"])


@callback(
    Output("version", "data"),
    Input({"act": ALL, "chore": ALL, "due": ALL, "tab": ALL}, "n_clicks"),
    State("version", "data"),
    prevent_initial_call=True,
)
def act(_, version):
    if not clicked():
        raise PreventUpdate
    b = ctx.triggered_id
    db.complete(b["chore"], session["user_id"], b["due"], b["act"] == "skip", today())
    return version + 1  # refresh even if it was already handled on the other phone


FORM = ["title", "every", "unit", "mode", "due", "assign", "assignee", "points", "notes"]


@callback(
    Output("modal", "opened"), Output("editing", "data"),
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
    return (True, c["id"], c["title"], c["every"], c["unit"], c["mode"], c["next_due"], c["assign"], assignee,
            c["points"], c["notes"], "", {"display": "none"} if c["id"] is None else {})


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
