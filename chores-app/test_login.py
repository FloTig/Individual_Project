"""Login brake: after FAIL_LIMIT wrong passwords, even the right one is refused. Run: python test_login.py"""
import os
import tempfile

os.environ["CHORES_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
from werkzeug.security import generate_password_hash  # noqa: E402

import app  # noqa: E402
import db  # noqa: E402

with db.connect() as c:
    c.execute("insert into users (name, pw_hash) values (?, ?)", ("Florian", generate_password_hash("right")))
client = app.server.test_client()
login = lambda pw: client.post("/login", data={"name": "Florian", "password": pw})  # noqa: E731

assert login("right").status_code == 302
for _ in range(app.FAIL_LIMIT):
    assert b"Wrong name or password" in login("wrong").data
r = login("right")
assert r.status_code == 200 and b"Too many" in r.data
app.FAILS.clear()  # the window has passed
assert login("right").status_code == 302
print("ok")
