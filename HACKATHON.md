# HACKATHON.md — IntentPilot (NEAR "Build Beyond Boundaries")

## Project name
IntentPilot — autonomous payment agent for cross-chain intents

## Track
Agent Economy (also fits Autonomous Business / Real-World Money)

## One-line pitch
Tell IntentPilot what to pay and when, in plain English; it compiles the
request into dependency-ordered payment plans and executes them through
NEAR Intents, with a receipt for every step.

## What it does
- Natural-language payment requests → structured intents ("Pay $45 to Alice
  every Friday" → {amount, currency, recipient, schedule})
- Multi-step plans with dependency ordering: fund-then-release,
  split-then-payout, recurring-audit patterns; cycles and unknown steps are
  rejected at compile time
- Canonical wire-intent payloads, each labeled with its verification status
- Simulated execution ledger with receipts and idempotent scheduling
  (`skip_if_scheduled` guards), so re-running a plan never double-schedules

## How it's built
- Python 3, standard library only (no dependencies, no keys, no network in
  the core engine)
- `intentagent/parse.py` — regex-based NL intent extraction (USD/EUR/NEAR/USDC)
- `intentagent/planner.py` — schedule expansion (once/daily/weekly/monthly)
  and splits with exact cent rounding
- `intentagent/plans.py` — multi-step compiler (topological sort + guards)
- `intentagent/adapters/wire.py` — canonical payload serializer
- `intentagent/adapters/oneclick.py` — NEAR Intents 1Click API client,
  implemented against the official docs (docs.near-intents.org):
  `GET /v0/tokens`, `POST /v0/quote`, `GET /v0/status`, with the documented
  request fields, auth shape, and execution-status enum. Live calls are
  disabled by default: NEAR Intents has no testnet, so a live call moves
  real mainnet funds and stays a deliberate, human-confirmed step.
- `intentagent/ledger.py` — simulated execution with deterministic
  receipt ids

## Try it
1. `python3 test_flow.py` → `72/72 PASSED`
2. `python3 -m intentagent.demo` → three end-to-end plans with receipts
   (fund-then-release, split-then-payout, recurring audit)

## Verification
- `test_flow.py`: 72/72 checks passing (parsing, schedule math, split
  rounding, ledger idempotency, plan ordering/cycles/guards, wire labels,
  1Click client request shapes and status parsing via injected transport)
- Demo data is synthetic everywhere ("Alice"/"Bob", test amounts)

## Event facts (verified on the official pages, 2026-11-01)
- NEAR HACKATHON: Build Beyond Boundaries — Nov 1, 2026 00:00 UTC →
  Nov 14, 2026 23:59 UTC; judging Nov 16–18; results by Nov 18, 23:59 UTC
- Prize pool $250,000: Grand $55K ×1, 1st $10K ×13, 2nd $3K ×13, 3rd $2K ×13
  (one prize tier per track, 13 tracks)
- Submission = public repository + public demo post on X (video or
  screenshots, stating it was built for NEAR HACKATHON) + the official
  form (project name, description 20–2,000 chars, team lead, email, team
  size, preferred track, NEAR account address for payout, both links).
  One submission per project; not editable after sending.
- Code written since the announcement counts (official FAQ,
  nearhackathon.com).
