# IntentPilot — autonomous payment agent for NEAR Intents

Built for **NEAR HACKATHON: Build Beyond Boundaries** (Nov 1–14, 2026) —
**Agent Economy** track.

Tell IntentPilot what to pay and when, in plain English. It compiles the
request into a dependency-ordered payment plan, expands recurring schedules
into concrete dates, splits amounts with exact-cent rounding, and executes
each step exactly once — re-runs never double-schedule, thanks to idempotent
guards. Every run produces a receipted ledger a payer can audit.

## Try it (judges: do X, see Y)

Requires Python 3.10+. No dependencies, no keys, no network.

1. **Run the test suite**
   `python3 test_flow.py`
   → See: `test_flow.py: 72/72 PASSED` — parsing, schedule math, split
   rounding, ledger idempotency, plan ordering/cycle rejection, and the
   NEAR Intents wire layer are all covered.

2. **Run the end-to-end demo**
   `python3 -m intentagent.demo`
   → See: three synthetic plans executed end to end — fund-then-release
   (a pool is funded first, dependent payouts follow), split-then-payout
   (one amount split across recipients), and a recurring audit schedule —
   each step printed with its ledger receipt.

3. **Feed it your own request**
   Import `intentagent.parse.parse_request` and pass a string like
   `"Pay $45 to Alice every Friday"` → see a structured intent:
   `{action, amount, currency, recipient, schedule}`.

## How it works

```
plain-English request → intent → ordered plan → wire payload → ledger receipt
```

- `intentagent/parse.py` — regex-based natural-language intent extraction
  (USD / EUR / NEAR / USDC; once / daily / weekly / monthly schedules)
- `intentagent/planner.py` — schedule expansion and amount splits with
  exact cent rounding (no float drift: splits always sum to the total)
- `intentagent/plans.py` — multi-step plan compiler: topological ordering,
  dependency guards (`skip_if_scheduled`), cycles and unknown steps rejected
- `intentagent/ledger.py` — execution ledger with deterministic receipt ids;
  re-running a plan is a no-op for steps already scheduled
- `intentagent/adapters/wire.py` — canonical wire-intent payloads
  (internal schema, every payload labeled with its verification status)
- `intentagent/adapters/oneclick.py` — NEAR Intents **1Click API client**
  implemented against the official docs (docs.near-intents.org, verified
  verbatim): `GET /v0/tokens`, `POST /v0/quote`, `GET /v0/status` with the
  documented request fields and status enum

## Honest scope of this prototype

- The plan engine executes against a **simulated ledger**, so the whole
  prototype is verifiable with zero keys and zero funds at risk.
- The 1Click client is real and docs-verified, but **live calls are
  disabled by default** (`live=False`): NEAR Intents has no testnet, so any
  live call would move real mainnet funds. Enabling it is a deliberate,
  human-confirmed step (`NEAR_INTENTS_JWT` in the environment + `live=True`).
- All demo data is synthetic ("Alice" / "Bob", test amounts).

## Why this matters

Agents that can pay for services, APIs, and each other need payment
infrastructure that is ordered, auditable, and safe to re-run. IntentPilot
is that layer in miniature: describe the payment once, get a plan whose
steps cannot execute out of order or twice, with a receipt for every step —
aimed squarely at NEAR Intents as the settlement rail.

## License

MIT — see `LICENSE`.
