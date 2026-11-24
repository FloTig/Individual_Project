"""Run with `python test_schedule.py` (or pytest)."""
from datetime import date as d

from schedule import add, next_due


def test_month_end_clamps_and_recovers():
    assert add(d(2026, 1, 31), 1, "month", 31) == d(2026, 2, 28)
    assert add(d(2026, 2, 28), 1, "month", 31) == d(2026, 3, 31)
    assert add(d(2026, 11, 15), 2, "month", 15) == d(2027, 1, 15)


def test_calendar_done_early_keeps_rhythm():
    # Bins every Tuesday (Dec 1), put out on Monday -> next Tuesday.
    assert next_due("calendar", 1, "week", 1, d(2026, 12, 1), today=d(2026, 11, 30)) == d(2026, 12, 8)


def test_calendar_done_late_skips_missed_weeks():
    assert next_due("calendar", 1, "week", 3, d(2026, 11, 3), today=d(2026, 11, 24)) == d(2026, 12, 1)
    assert next_due("calendar", 1, "week", 3, d(2026, 11, 3), today=d(2026, 11, 25)) == d(2026, 12, 1)


def test_after_done_counts_from_today():
    assert next_due("after_done", 3, "week", 1, d(2026, 11, 1), today=d(2026, 11, 24)) == d(2026, 12, 15)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
