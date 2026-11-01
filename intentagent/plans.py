"""Multi-step payment plans: compile ordered, dependency-aware schedules.

A plan is a list of steps. Each step is a dict:
    {
      "step_id": "escrow-release",        # unique within the plan
      "request": "Pay $120 to Bob",       # natural-language payment request(s)
      "depends_on": ["escrow-fund"],      # step_ids that must execute first
      "guard": {"skip_if_scheduled": True}  # optional guard (see below)
    }

The compiler:
  1. topologically sorts steps (raises ValueError on unknown deps or cycles),
  2. parses + expands each step into schedule entries via parse/planner,
  3. applies guards, then hands the ordered entries to the ledger.

Guards (all honest no-ops if the condition can't be evaluated offline):
  - skip_if_scheduled: drop entries already present in the ledger's schedule
    (idempotent re-runs of a plan across sessions).

Plans are still pure descriptions until a ledger executes them; the offline
ledger labels everything SIMULATED.
"""
from . import parse, planner


def _topo_sort(steps):
    """Order steps so dependencies come first. Raises ValueError on
    unknown dependency or dependency cycle."""
    ids = [s["step_id"] for s in steps]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate step_id in plan")
    by_id = {s["step_id"]: s for s in steps}
    order, visiting, visited = [], set(), set()

    def visit(sid):
        if sid in visited:
            return
        if sid in visiting:
            raise ValueError("dependency cycle at step %r" % sid)
        if sid not in by_id:
            raise ValueError("unknown dependency %r" % sid)
        visiting.add(sid)
        for dep in by_id[sid].get("depends_on", []) or []:
            visit(dep)
        visiting.discard(sid)
        visited.add(sid)
        order.append(by_id[sid])

    for sid in ids:
        visit(sid)
    return order


def compile_plan(steps, today=None, existing_keys=None):
    """Return ordered schedule entries [{step_id, due_date, amount, currency, to}].

    existing_keys: optional set of (due_date, amount, currency, recipients)
    used by the skip_if_scheduled guard; when None the guard is a no-op
    that keeps everything.
    """
    ordered = _topo_sort(steps)
    out = []
    for step in ordered:
        intents = parse.parse(step["request"], today=today)
        entries = []
        for intent in intents:
            entries.extend(planner.expand(intent))
        if step.get("guard", {}).get("skip_if_scheduled") and existing_keys:
            entries = [
                e for e in entries
                if (e["due_date"], e["amount"], e["currency"], tuple(e["to"]))
                not in existing_keys
            ]
        for e in entries:
            out.append({"step_id": step["step_id"], "due_date": e["due_date"],
                        "amount": e["amount"], "currency": e["currency"],
                        "to": e["to"]})
    return out


def plan_keys(entries):
    """Keys for the skip_if_scheduled guard (ledger-backed)."""
    return {(e["due_date"], e["amount"], e["currency"], tuple(e["to"]))
            for e in entries}
