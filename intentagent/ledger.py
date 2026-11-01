"""Simulated execution ledger — intents in, receipts out. NO network, NO keys.

Every receipt is labeled "mode": "SIMULATED" so nothing here can be
mistaken for a real on-chain transfer. Real NEAR Intents execution is a
documented later step (see README checklist); this module is the
agent core that gets wired to it.
"""
import hashlib
import json
from datetime import datetime, timezone


def _tx_id(entry, index):
    payload = json.dumps({"entry": entry, "index": index},
                         sort_keys=True).encode()
    return "sim_" + hashlib.sha256(payload).hexdigest()[:16]


class Ledger:
    def __init__(self):
        self.entries = []   # scheduled entries (from planner.expand)
        self.receipts = []  # executed receipts

    def schedule(self, entries):
        """Add schedule entries; returns count added (idempotent per content)."""
        known = {(e["due_date"], e["amount"], e["currency"], tuple(e["to"]))
                 for e in self.entries}
        added = 0
        for e in entries:
            key = (e["due_date"], e["amount"], e["currency"], tuple(e["to"]))
            if key not in known:
                self.entries.append(dict(e, status="scheduled"))
                known.add(key)
                added += 1
        return added

    def execute_due(self, as_of):
        """Mark all entries due on/before as_of as executed; returns receipts."""
        out = []
        for i, e in enumerate(self.entries):
            if e["status"] == "scheduled" and e["due_date"] <= as_of:
                e["status"] = "executed"
                r = {"tx_id": _tx_id(e, i), "mode": "SIMULATED",
                     "executed_at": datetime.now(timezone.utc).isoformat(),
                     "due_date": e["due_date"], "amount": e["amount"],
                     "currency": e["currency"], "to": e["to"]}
                self.receipts.append(r)
                out.append(r)
        return out

    def summary(self):
        total = round(sum(e["amount"] for e in self.entries), 2)
        done = sum(1 for e in self.entries if e["status"] == "executed")
        return {"scheduled": len(self.entries), "executed": done,
                "pending": len(self.entries) - done, "total_value": total,
                "mode": "SIMULATED"}

    def dump(self):
        return json.dumps({"entries": self.entries, "receipts": self.receipts,
                           "summary": self.summary()}, indent=2)
