"""SQLite storage. Create or reset a login with `python db.py adduser NAME`."""
import os
import sqlite3
import sys
from contextlib import contextmanager
from datetime import date
from getpass import getpass

from werkzeug.security import check_password_hash, generate_password_hash

import schedule

PATH = os.environ.get("CHORES_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "chores.db"))

SCHEMA = """
create table if not exists users (
    id integer primary key,
    name text not null unique,
    pw_hash text not null
);
create table if not exists chores (
    id integer primary key,
    title text not null,
    notes text not null default '',
    mode text not null check (mode in ('calendar', 'after_done')),
    every integer not null check (every > 0),
    unit text not null check (unit in ('day', 'week', 'month')),
    assign text not null check (assign in ('fixed', 'rotate', 'anyone')),
    assignee_id integer references users (id),
    points integer not null default 1 check (points > 0),
    next_due text not null,       -- ISO date
    anchor_day integer not null,  -- day of month that monthly calendar chores land on
    archived integer not null default 0,
    check ((assign = 'anyone') = (assignee_id is null))
);
create table if not exists completions (
    id integer primary key,
    chore_id integer not null references chores (id),
    user_id integer not null references users (id),
    done_on text not null,        -- ISO date
    skipped integer not null default 0,
    points integer not null,      -- copied, so editing a chore doesn't rewrite history
    created_at text not null default current_timestamp
);
"""


@contextmanager
def connect():
    c = sqlite3.connect(PATH)
    c.row_factory = sqlite3.Row
    c.execute("pragma foreign_keys = on")
    try:
        with c:  # commit on success, roll back on error
            yield c
    finally:
        c.close()


def init():
    with connect() as c:
        c.executescript(SCHEMA)


def users() -> dict[int, str]:
    with connect() as c:
        return {r["id"]: r["name"] for r in c.execute("select id, name from users order by id")}


def login(name: str, password: str) -> int | None:
    with connect() as c:
        r = c.execute("select id, pw_hash from users where name = ?", (name.strip(),)).fetchone()
    return r["id"] if r and check_password_hash(r["pw_hash"], password) else None


def chores() -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute("select * from chores where not archived order by next_due, title")]


def chore(chore_id: int) -> dict:
    with connect() as c:
        return dict(c.execute("select * from chores where id = ?", (chore_id,)).fetchone())


def save_chore(chore_id: int | None, f: dict):
    """f holds validated columns. anchor_day only moves when the due date is changed."""
    with connect() as c:
        if chore_id is None:
            c.execute(
                "insert into chores (title, notes, mode, every, unit, assign, assignee_id, points, next_due, anchor_day)"
                " values (:title, :notes, :mode, :every, :unit, :assign, :assignee_id, :points, :next_due, :anchor_day)",
                f,
            )
        else:
            # SET expressions see the old row, so the case compares against the old next_due.
            c.execute(
                "update chores set title = :title, notes = :notes, mode = :mode, every = :every, unit = :unit,"
                " assign = :assign, assignee_id = :assignee_id, points = :points,"
                " anchor_day = case when next_due = :next_due then anchor_day else :anchor_day end,"
                " next_due = :next_due where id = :id",
                {**f, "id": chore_id},
            )


def archive(chore_id: int):
    with connect() as c:
        c.execute("update chores set archived = 1 where id = ?", (chore_id,))


def complete(chore_id: int, user_id: int, due: str, skipped: bool, today: date) -> bool:
    """Mark the occurrence due on `due` done (or skipped). False if someone already handled it."""
    with connect() as c:
        ch = c.execute("select * from chores where id = ? and not archived", (chore_id,)).fetchone()
        if not ch or ch["next_due"] != due:
            return False
        new_due = schedule.next_due(ch["mode"], ch["every"], ch["unit"], ch["anchor_day"], date.fromisoformat(due), today)
        assignee = ch["assignee_id"]
        if ch["assign"] == "rotate" and not skipped:
            other = c.execute("select id from users where id != ? order by id limit 1", (assignee,)).fetchone()
            assignee = other["id"] if other else assignee
        # Guarded on the old due date: a double tap or both phones at once only counts once.
        cur = c.execute(
            "update chores set next_due = ?, assignee_id = ? where id = ? and next_due = ?",
            (new_due.isoformat(), assignee, chore_id, due),
        )
        if cur.rowcount != 1:
            return False
        c.execute(
            "insert into completions (chore_id, user_id, done_on, skipped, points) values (?, ?, ?, ?, ?)",
            (chore_id, user_id, today.isoformat(), int(skipped), 0 if skipped else ch["points"]),
        )
        return True


def history(limit: int = 50) -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute(
            "select c.done_on, c.skipped, c.points, u.name, ch.title from completions c"
            " join users u on u.id = c.user_id join chores ch on ch.id = c.chore_id"
            " order by c.id desc limit ?",
            (limit,),
        )]


if __name__ == "__main__":
    init()
    if len(sys.argv) == 3 and sys.argv[1] == "adduser":
        name = sys.argv[2]
        pw = getpass(f"Password for {name}: ")
        with connect() as c:
            c.execute(
                "insert into users (name, pw_hash) values (?, ?) on conflict (name) do update set pw_hash = excluded.pw_hash",
                (name, generate_password_hash(pw)),
            )
        print(f"Saved login for {name}.")
    else:
        print("usage: python db.py adduser NAME")
