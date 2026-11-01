"""IntentPilot end-to-end demo: request -> parse -> plan -> simulate -> receipts.

All data SYNTHETIC. Run:  python3 demo.py  (or  python3 -m intentagent.demo)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from intentagent import parse, planner, ledger, plans
from intentagent.adapters import canonical_wire, NEAR_WIRE_VERIFY_LIST

REQUESTS = [
    "Pay $45 to Alice every Friday",
    "Split $90 between Alice, Bob, Carol",
    "Send 120 EUR to Bob tomorrow",
    "Pay $25 to savings every day for 10 days",
]

# Multi-step plan: fund a payout pool first, then release payments that
# depend on the pool being funded. All synthetic.
MULTI_STEP_PLAN = [
    {"step_id": "fund-pool", "request": "Pay $200 to pool"},
    {"step_id": "payout-alice", "request": "Pay $90 to Alice",
     "depends_on": ["fund-pool"]},
    {"step_id": "payout-bob", "request": "Pay $60 to Bob",
     "depends_on": ["fund-pool"]},
    {"step_id": "weekly-audit", "request": "Pay $10 to Alice every week",
     "depends_on": ["payout-alice", "payout-bob"],
     "guard": {"skip_if_scheduled": True}},
]


def main():
    led = ledger.Ledger()
    for req in REQUESTS:
        intents = parse.parse(req, today=date(2026, 11, 1))
        for intent in intents:
            entries = planner.expand(intent)
            n = led.schedule(entries)
            print("REQUEST : %s" % req)
            print("  intent: %s %s %s freq=%s x%d  -> %d execution(s) scheduled"
                  % (intent["kind"], intent["amount"], intent["currency"],
                     intent.get("frequency", "once"), intent["count"], n))
    receipts = led.execute_due("2026-11-08")
    print("\n--- executed as of 2026-11-08: %d receipts (all SIMULATED) ---"
          % len(receipts))
    for r in receipts:
        print("  %s | %s %s -> %s | %s" % (
            r["tx_id"], r["amount"], r["currency"], ", ".join(r["to"]),
            r["due_date"]))
    s = led.summary()
    print("\nsummary: %d scheduled, %d executed, %d pending, total %.2f (%s)"
          % (s["scheduled"], s["executed"], s["pending"], s["total_value"],
             s["mode"]))

    # --- multi-step plan demo ---
    print("\n--- multi-step plan (dependency-ordered) ---")
    led2 = ledger.Ledger()
    entries = plans.compile_plan(MULTI_STEP_PLAN, today=date(2026, 11, 1))
    n = led2.schedule(entries)
    seq = [(e["step_id"], e["due_date"], e["amount"], e["to"][0])
           for e in led2.entries]
    for sid, d, amt, who in seq:
        print("  step %-12s due %s  %6.2f USD -> %s" % (sid, d, amt, who))
    print("  scheduled %d entries (guards: skip_if_scheduled on weekly-audit)" % n)
    wire = canonical_wire(entries, plan_id="demo-plan-1")
    print("  canonical wire payloads: %d (all labeled %s, wire=%s)"
          % (len(wire), wire[0]["payload"]["mode"],
             wire[0]["payload"]["wire"]))
    print("  NEAR Intents docs verify-list items: %d (see adapters/wire.py)"
          % len(NEAR_WIRE_VERIFY_LIST))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
