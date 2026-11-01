"""Turn parsed intents into concrete execution schedules (stdlib only)."""
from datetime import date, timedelta
import calendar

_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def _next_weekday(from_date, weekday):
    delta = (weekday - from_date.weekday()) % 7
    return from_date + timedelta(days=delta)


def expand(intent):
    """Return list of schedule entries {due_date, amount, currency, to}."""
    start = date.fromisoformat(intent["start_date"])
    amount, cur = intent["amount"], intent["currency"]
    freq, count = intent.get("frequency", "once"), int(intent.get("count", 1))

    if intent["kind"] == "split":
        recipients = intent["to"]
        share = round(amount / len(recipients), 2)
        fixed = round(share * (len(recipients) - 1), 2)
        entries = []
        for i, r in enumerate(recipients):
            share_i = round(amount - fixed, 2) if i == len(recipients) - 1 else share
            entries.append({"due_date": start.isoformat(), "amount": share_i,
                            "currency": cur, "to": [r]})
        return entries

    if freq == "once":
        return [{"due_date": start.isoformat(), "amount": amount,
                 "currency": cur, "to": intent["to"]}]

    dates = []
    if freq.startswith("weekly:"):
        day = freq.split(":", 1)[1]
        target = _WEEKDAYS.get(day)
        d = _next_weekday(start, target) if target is not None else start
        for _ in range(count):
            dates.append(d)
            d = d + timedelta(days=7)
    elif freq == "daily":
        dates = [start + timedelta(days=i) for i in range(count)]
    elif freq == "monthly":
        for i in range(count):
            m = start.month - 1 + i
            y, m = start.year + m // 12, m % 12 + 1
            day = min(start.day, calendar.monthrange(y, m)[1])
            dates.append(date(y, m, day))
    else:
        raise ValueError("unknown frequency: %s" % freq)

    return [{"due_date": d.isoformat(), "amount": amount,
             "currency": cur, "to": intent["to"]} for d in dates]


def total_value(entries):
    return round(sum(e["amount"] for e in entries), 2)
