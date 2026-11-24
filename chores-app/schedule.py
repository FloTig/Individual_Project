"""Due-date maths. Pure functions, no database."""
import calendar
from datetime import date, timedelta


def add(d: date, every: int, unit: str, day: int) -> date:
    """d plus `every` days/weeks/months. Months land on `day`, clamped to the month's end."""
    if unit == "day":
        return d + timedelta(days=every)
    if unit == "week":
        return d + timedelta(weeks=every)
    years, month0 = divmod(d.month - 1 + every, 12)
    y, m = d.year + years, month0 + 1
    return date(y, m, min(day, calendar.monthrange(y, m)[1]))


def next_due(mode: str, every: int, unit: str, anchor_day: int, due: date, today: date) -> date:
    """Next due date for a chore that was done or skipped today.

    calendar:   step forward from the current due date until it's after today,
                so the rhythm stays (bins on Tuesdays) and missed weeks don't pile up.
    after_done: today + the period.
    """
    if mode == "after_done":
        return add(today, every, unit, today.day)
    d = add(due, every, unit, anchor_day)
    while d <= today:
        d = add(d, every, unit, anchor_day)
    return d
