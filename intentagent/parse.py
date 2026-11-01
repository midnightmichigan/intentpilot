"""Parse natural-language payment requests into structured payment intents.

Pure stdlib, zero network. All outputs are intent descriptions — nothing
executes until the (separate) execution layer runs, and the offline ledger
labels everything SIMULATED.

Supported shapes:
  "Pay $45 to Alice"                                   -> once, today
  "Send 120 EUR to Bob tomorrow"                       -> once, +1 day
  "Pay $200 to Alice every Friday"                     -> recurring weekly
  "Pay $60 to rent-pool every month"                   -> recurring monthly
  "Split $90 between Alice Bob Carol"                  -> one-time split
  "Pay $25 to Alice every day for 10 days"             -> recurring daily x10
"""
import re
from datetime import date, timedelta

_AMOUNTS = re.compile(
    r"(?i)\b(?:pay|send|transfer|remit|give)\s+\$?\s*(\d+(?:\.\d{1,2})?)"
    r"\s*([A-Z]{3})?\s+(?:to|for)\s+([A-Za-z][A-Za-z0-9 _-]{0,40})"
)
_SPLIT = re.compile(
    r"(?i)\bsplit\s+\$?\s*(\d+(?:\.\d{1,2})?)\s*([A-Z]{3})?\s+between\s+([A-Za-z0-9 ,_-]+)"
)
_FREQ = re.compile(
    r"(?i)\bevery\s+(day|week|month|friday|monday|tuesday|wednesday|thursday|saturday|sunday)\b"
)
_COUNT = re.compile(r"(?i)\bfor\s+(\d{1,3})\s+(days?|weeks?|months?|payments?)\b")
_TOMORROW = re.compile(r"(?i)\btomorrow\b")

VALID_CURRENCIES = {"USD", "EUR", "NEAR", "USDC"}

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def _clean_recipient(raw):
    r = raw.strip().strip(",")
    r = re.sub(r"\s+(every|for|tomorrow|today)\b.*$", "", r, flags=re.I).strip()
    return r or "unknown"


def parse(request, today=None):
    """Return a list of intent dicts parsed from *request*.

    Each intent: {kind, amount, currency, to, frequency, count, start_date}
    kind: "once" | "recurring" | "split"
    Raises ValueError on unparseable input.
    """
    today = today or date.today()
    if not isinstance(request, str) or not request.strip():
        raise ValueError("empty request")

    m = _SPLIT.search(request)
    if m:
        amount, cur, who = m.groups()
        cur = (cur or "USD").upper()
        if cur not in VALID_CURRENCIES:
            raise ValueError("unsupported currency: %s" % cur)
        recipients = [w.strip() for w in who.split(",")]
        recipients = [r for r in (re.sub(r"\s+(every|for)\b.*$", "", x, flags=re.I).strip()
                                  for x in recipients) if r]
        if len(recipients) < 2:
            raise ValueError("split needs at least 2 recipients")
        return [{"kind": "split", "amount": round(float(amount), 2),
                 "currency": cur, "to": recipients,
                 "frequency": "once", "count": 1, "start_date": today.isoformat()}]

    m = _AMOUNTS.search(request)
    if not m:
        raise ValueError("could not find a payment amount/recipient in: %r" % request)
    amount, cur, who = m.groups()
    cur = (cur or "USD").upper()
    if cur not in VALID_CURRENCIES:
        raise ValueError("unsupported currency: %s" % cur)
    recipient = _clean_recipient(who)

    freq_m = _FREQ.search(request)
    if _TOMORROW.search(request) and not freq_m:
        return [{"kind": "once", "amount": round(float(amount), 2),
                 "currency": cur, "to": [recipient], "frequency": "once",
                 "count": 1,
                 "start_date": (today + timedelta(days=1)).isoformat()}]
    if not freq_m:
        return [{"kind": "once", "amount": round(float(amount), 2),
                 "currency": cur, "to": [recipient], "frequency": "once",
                 "count": 1, "start_date": today.isoformat()}]

    freq = freq_m.group(1).lower()
    count_m = _COUNT.search(request)
    count = int(count_m.group(1)) if count_m else 12
    count = max(1, min(count, 120))

    if freq in WEEKDAYS:                      # e.g. "every friday"
        freq_key = "weekly:" + freq
    elif freq == "week":
        freq_key = "weekly:today"
    elif freq == "month":
        freq_key = "monthly"
    else:
        freq_key = "daily"

    return [{"kind": "recurring", "amount": round(float(amount), 2),
             "currency": cur, "to": [recipient], "frequency": freq_key,
             "count": count, "start_date": today.isoformat()}]
