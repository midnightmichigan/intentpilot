"""Wire adapters: canonical intent payload serialization.

Two layers:
  1. canonical_wire(entries, plan_id) — turns compiled schedule entries into a
     canonical, transport-agnostic intent payload (internal schema). Every
     payload is labeled "mode": "SIMULATED".
  2. NearIntentsAdapter — STUB. The real NEAR Intents submission shape lives in
     NEAR's docs (https://docs.near.org or the intents API reference), which
     require a live window to read. This stub documents exactly what to verify
     and raises until wired. It MUST NOT be used to guess the API format.

DO NOT invent the NEAR Intents request format — verify against the real docs
at the first live window.
"""
import hashlib
import json

# Docs to verify before wiring (live window required):
NEAR_WIRE_VERIFY_LIST = [
    "NEAR Intents 1Click API request shape (intent, nonce, sender, receiver, "
    "assets, deltas — verify field names and types against the real docs)",
    "Signature scheme for intent payloads (which keys sign what)",
    "Testnet vs mainnet endpoints and how to switch",
    "Asset identifiers for NEAR/USDC/USDT on testnet",
    "Confirmation/settlement status polling flow — VERIFIED via 1Click "
    "GET /v0/status (OpenAPI spec read 2026-10-22); "
    "see adapters/oneclick.py get_execution_status",
]


def canonical_wire(entries, plan_id, sender="synthetic-agent"):
    """Canonical payload list. Internal schema, NOT a chain API format."""
    payloads = []
    for i, e in enumerate(entries):
        body = {
            "plan_id": plan_id,
            "step_index": i,
            "sender": sender,
            "receiver": e["to"][0] if e.get("to") else "unknown",
            "additional_receivers": e.get("to", [])[1:],
            "asset": e["currency"],
            "amount": "%.2f" % e["amount"],
            "due_date": e["due_date"],
            "mode": "SIMULATED",
            "wire": "canonical-unverified",
        }
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]
        payloads.append({"payload": body, "payload_id": "wire_" + digest})
    return payloads


class NearIntentsAdapter:
    """Stub for the real NEAR Intents wire layer.

    Until NEAR_WIRE_VERIFY_LIST is verified against the real docs, every
    method raises. Calling code should route through this adapter so the
    swap-in is a one-line change once docs are read.
    """

    def __init__(self):
        raise NotImplementedError(
            "NearIntentsAdapter is unwired: verify NEAR_WIRE_VERIFY_LIST "
            "against the official NEAR Intents docs (live window required), "
            "then implement. Never guess the API format.")
