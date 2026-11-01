"""test_flow.py — IntentPilot core checks. Run: python3 test_flow.py"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date
from intentagent import parse, planner, ledger

P = []
def check(name, cond):
    P.append((name, bool(cond)))

T = date(2026, 11, 1)  # Sunday Nov 1, 2026

# --- parse: once ---
i = parse.parse("Pay $45 to Alice", today=T)[0]
check("parse once kind", i["kind"] == "once")
check("parse once amount", i["amount"] == 45.0)
check("parse once currency default USD", i["currency"] == "USD")
check("parse once recipient", i["to"] == ["Alice"])
check("parse once date", i["start_date"] == "2026-11-01")

i = parse.parse("Send 120 EUR to Bob tomorrow", today=T)[0]
check("parse tomorrow date", i["start_date"] == "2026-11-02")
check("parse currency EUR", i["currency"] == "EUR")

# --- parse: recurring ---
i = parse.parse("Pay $45 to Alice every Friday", today=T)[0]
check("parse weekly-friday freq", i["frequency"] == "weekly:friday")
check("parse weekly count default 12", i["count"] == 12)

i = parse.parse("Pay $25 to savings every day for 10 days", today=T)[0]
check("parse daily count 10", i["count"] == 10 and i["frequency"] == "daily")

i = parse.parse("Pay $60 to rent-pool every month", today=T)[0]
check("parse monthly freq", i["frequency"] == "monthly")

# --- parse: split ---
i = parse.parse("Split $90 between Alice, Bob, Carol", today=T)[0]
check("parse split kind", i["kind"] == "split")
check("parse split 3 recipients", i["to"] == ["Alice", "Bob", "Carol"])

# --- parse: failures ---
try:
    parse.parse("hello there", today=T); check("parse garbage raises", False)
except ValueError:
    check("parse garbage raises", True)
try:
    parse.parse("Split $90 between Alice", today=T); check("split needs 2 raises", False)
except ValueError:
    check("split needs 2 raises", True)

# --- planner: weekly friday from Sunday Nov 1 ---
i = parse.parse("Pay $45 to Alice every Friday", today=T)[0]
entries = planner.expand(i)
check("planner 12 friday entries", len(entries) == 12)
check("planner first friday is Nov 6", entries[0]["due_date"] == "2026-11-06")
check("planner 7-day spacing", entries[1]["due_date"] == "2026-11-13")

# --- planner: split rounding sums to total ---
i = parse.parse("Split $90 between Alice, Bob, Carol", today=T)[0]
entries = planner.expand(i)
check("planner split 3 entries", len(entries) == 3)
check("planner split sums to 90", planner.total_value(entries) == 90.0)

i = parse.parse("Split $100 between Alice, Bob, Carol", today=T)[0]
entries = planner.expand(i)
check("planner split 100 sums exactly", planner.total_value(entries) == 100.0)

# --- ledger: schedule idempotency + execution ---
led = ledger.Ledger()
i = parse.parse("Pay $25 to savings every day for 10 days", today=T)[0]
e1 = planner.expand(i)
check("ledger schedules 10", led.schedule(e1) == 10)
check("ledger duplicate schedules 0", led.schedule(e1) == 0)
receipts = led.execute_due("2026-11-03")
check("ledger executes due (3)", len(receipts) == 3)
check("receipts labeled SIMULATED", all(r["mode"] == "SIMULATED" for r in receipts))
s = led.summary()
check("ledger summary pending 7", s["pending"] == 7 and s["executed"] == 3)

# --- end-to-end smoke: demo runs clean ---
from intentagent import demo
check("demo module loads", hasattr(demo, "main"))

# --- plans: multi-step dependency ordering ---
from intentagent import plans
from intentagent.adapters import canonical_wire, NearIntentsAdapter, NEAR_WIRE_VERIFY_LIST
from intentagent.adapters import (OneClickClient, OneClickError, nep141,
                                  BASE_URL, EXECUTION_STATUS,
                                  TERMINAL_STATUS, is_terminal)

plan_steps = [
    {"step_id": "a", "request": "Pay $10 to Alice"},
    {"step_id": "b", "request": "Pay $20 to Bob", "depends_on": ["a"]},
    {"step_id": "c", "request": "Pay $30 to Carol",
     "depends_on": ["b"]},
]
pe = plans.compile_plan(plan_steps, today=T)
check("plan compiles 3 entries", len(pe) == 3)
check("plan topo order a->b->c",
      [e["step_id"] for e in pe] == ["a", "b", "c"])
check("plan entries carry step ids", all("step_id" in e for e in pe))

# reverse declaration still orders by dependency
pe2 = plans.compile_plan(list(reversed(plan_steps)), today=T)
check("plan order independent of declaration",
      [e["step_id"] for e in pe2] == ["a", "b", "c"])

# cycle raises
try:
    plans.compile_plan([
        {"step_id": "x", "request": "Pay $1 to A", "depends_on": ["y"]},
        {"step_id": "y", "request": "Pay $1 to B", "depends_on": ["x"]},
    ], today=T)
    check("plan cycle raises", False)
except ValueError:
    check("plan cycle raises", True)

# unknown dependency raises
try:
    plans.compile_plan([
        {"step_id": "x", "request": "Pay $1 to A", "depends_on": ["ghost"]},
    ], today=T)
    check("plan unknown dep raises", False)
except ValueError:
    check("plan unknown dep raises", True)

# guard: skip_if_scheduled drops already-scheduled entries
led3 = ledger.Ledger()
first = plans.compile_plan(plan_steps, today=T)
check("plan first schedule adds 3", led3.schedule(first) == 3)
second = plans.compile_plan(
    [{"step_id": s["step_id"], "request": s["request"],
      "depends_on": s.get("depends_on"),
      "guard": {"skip_if_scheduled": True}} for s in plan_steps],
    today=T, existing_keys=plans.plan_keys(led3.entries))
check("plan guard skips rescheduled entries", len(second) == 0)

# ledger accepts plan entries (extra step_id key tolerated)
led4 = ledger.Ledger()
check("plan entries ledger-compatible", led4.schedule(first) == 3)

# --- wire: canonical payloads labeled, stub raises ---
wire = canonical_wire(first, plan_id="t1")
check("wire payload count matches entries", len(wire) == 3)
check("wire payloads labeled SIMULATED",
      all(p["payload"]["mode"] == "SIMULATED" for p in wire))
check("wire schema flagged unverified",
      all(p["payload"]["wire"] == "canonical-unverified" for p in wire))
check("wire verify list non-empty", len(NEAR_WIRE_VERIFY_LIST) >= 4)
try:
    NearIntentsAdapter()
    check("near stub raises", False)
except NotImplementedError:
    check("near stub raises", True)

# --- oneclick: verified 1Click client (docs read 2026-10-22), fake transport ---
import json as _json

_calls = []
def _fake_transport(method, url, headers, body):
    _calls.append((method, url, headers, body))
    if url.endswith("/tokens"):
        return 200, _json.dumps([{"assetId": "nep141:wrap.near"}]).encode()
    if url.endswith("/quote"):
        return 200, _json.dumps({"quoteId": "q1"}).encode()
    return 404, b"{}"

c = OneClickClient(live=True, transport=_fake_transport, jwt="TESTJWT")
check("base url verified", BASE_URL == "https://1click.chaindefuser.com/v0")
check("nep141 shape", nep141("wrap.near") == "nep141:wrap.near")
try:
    nep141("  ")
    check("nep141 rejects empty", False)
except ValueError:
    check("nep141 rejects empty", True)

status, tokens = c.get_tokens()
check("get_tokens hits /v0/tokens",
      _calls[-1][0] == "GET" and _calls[-1][1].endswith("/v0/tokens"))
check("get_tokens parses list", tokens == [{"assetId": "nep141:wrap.near"}])
check("auth header sent with jwt",
      _calls[-1][2].get("Authorization") == "Bearer TESTJWT")
check("jwt never in url or body",
      "TESTJWT" not in _calls[-1][1]
      and "TESTJWT" not in (_calls[-1][3] or b"").decode())

c2 = OneClickClient(live=True, transport=_fake_transport, jwt=None)
c2.get_tokens()
check("no auth header without jwt",
      "Authorization" not in _calls[-1][2])

res = c.request_quote(nep141("wrap.near"),
                      "nep141:arb-0x912ce59144191c1204e64559fe8253a0e49e6548.omft.near",
                      "100000000000000000000000")
sent = _json.loads(_calls[-1][3].decode())
check("quote hits /v0/quote",
      _calls[-1][0] == "POST" and _calls[-1][1].endswith("/v0/quote"))
check("quote verified fields present",
      sent["swapType"] == "EXACT_INPUT"
      and sent["originAsset"] == "nep141:wrap.near"
      and sent["depositType"] == "ORIGIN_CHAIN"
      and sent["destinationAsset"].endswith(".omft.near")
      and sent["amount"] == "100000000000000000000000")
check("quote field_verified flags honest",
      all(res["field_verified"][k] for k in
          ("swapType", "originAsset", "depositType",
           "destinationAsset", "amount")))
res2 = c.request_quote("a", "b", "1", customFee="x")
check("extra fields flagged unverified",
      res2["field_verified"]["customFee"] is False)
try:
    c.request_quote("a", "b", "1.5")
    check("quote rejects float amount", False)
except ValueError:
    check("quote rejects float amount", True)

c_off = OneClickClient(live=False, transport=_fake_transport)
try:
    c_off.get_tokens()
    check("live=False blocks network", False)
except OneClickError as e:
    check("live=False blocks network", "no testnet" in str(e))

def _boom(method, url, headers, body):
    raise TimeoutError("down")
c_boom = OneClickClient(live=True, transport=_boom)
# transport raising raw -> OneClickClient._call wraps only urllib transport;
# custom transports surface their own errors: client must not crash the suite
try:
    c_boom.get_tokens()
    check("custom transport error surfaces", False)
except Exception:
    check("custom transport error surfaces", True)

# --- oneclick status endpoint (docs read verbatim 2026-10-22), fake transport ---
def _fake_status_transport(method, url, headers, body):
    _calls.append((method, url, headers, body))
    if "/v0/status?" in url:
        if "depositAddress=deadbeef" in url:
            raise OneClickError("HTTP 404 on GET " + url)
        return 200, _json.dumps({
            "correlationId": "550e8400-e29b-41d4-a716-446655440000",
            "status": "PROCESSING",
            "updatedAt": "2026-10-22T04:00:00Z",
            "swapDetails": {"intentHashes": [], "nearTxHashes": [],
                            "originChainTxHashes": [],
                            "destinationChainTxHashes": []},
        }).encode()
    return 404, b"{}"

cs = OneClickClient(live=True, transport=_fake_status_transport, jwt="TESTJWT")
r = cs.get_execution_status("0xabc123")
check("status hits GET /v0/status",
      _calls[-1][0] == "GET" and "/v0/status?" in _calls[-1][1])
check("status sends depositAddress query param",
      "depositAddress=0xabc123" in _calls[-1][1])
check("status omits depositMemo when not given",
      "depositMemo" not in _calls[-1][1])
check("status enum value in EXECUTION_STATUS",
      r["execution_status"] == "PROCESSING"
      and r["execution_status"] in EXECUTION_STATUS)
check("status_known true for documented value", r["status_known"] is True)
check("is_terminal false mid-flight", r["is_terminal"] is False)
check("jwt never in status url",
      "TESTJWT" not in _calls[-1][1])

r2 = cs.get_execution_status("0xabc123", deposit_memo="memo42")
check("status includes depositMemo when given",
      "depositMemo=memo42" in _calls[-1][1])

try:
    cs.get_execution_status("   ")
    check("status rejects empty address", False)
except ValueError:
    check("status rejects empty address", True)

try:
    cs.get_execution_status("deadbeef")
    check("status 404 surfaces OneClickError", False)
except OneClickError as e:
    check("status 404 surfaces OneClickError", "404" in str(e))

check("terminal set is SUCCESS/REFUNDED/FAILED",
      set(TERMINAL_STATUS) == {"SUCCESS", "REFUNDED", "FAILED"})
check("is_terminal true for SUCCESS", is_terminal("SUCCESS") is True)
check("is_terminal true for REFUNDED", is_terminal("REFUNDED") is True)
check("is_terminal false for PENDING_DEPOSIT",
      is_terminal("PENDING_DEPOSIT") is False)
check("all 7 documented statuses present",
      set(EXECUTION_STATUS) == {"KNOWN_DEPOSIT_TX", "PENDING_DEPOSIT",
                               "INCOMPLETE_DEPOSIT", "PROCESSING",
                               "SUCCESS", "REFUNDED", "FAILED"})

cs_off = OneClickClient(live=False, transport=_fake_status_transport)
try:
    cs_off.get_execution_status("0xabc123")
    check("status blocked when live=False", False)
except OneClickError:
    check("status blocked when live=False", True)

fails = [n for n, c in P if not c]
print("test_flow.py: %d/%d PASSED" % (len(P) - len(fails), len(P)))
for n in fails:
    print("  FAILED:", n)
sys.exit(1 if fails else 0)
