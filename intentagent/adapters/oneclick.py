"""NEAR Intents 1Click API client.

VERIFIED against the official docs (https://docs.near-intents.org,
read verbatim 2026-10-22; docs updated 2026-10-08):

- Base URL: https://1click.chaindefuser.com/v0
- GET  /v0/tokens  — query supported tokens
- POST /v0/quote   — request a quote. Verified request fields:
    swapType:         "EXACT_INPUT" (from the docs' own curl example)
    originAsset:      "nep141:wrap.near"  (nep141:<contract> shape)
    depositType:      "ORIGIN_CHAIN"
    destinationAsset: "nep141:arb-0x912c...e6548.omft.near"
                      (cross-chain shape: nep141:<chain>-<address>.omft.near)
    amount:           smallest-unit string, e.g. "100000000000000000000000"
- Auth header:  Authorization: Bearer <jwt>
  (JWT = his tap; unauthenticated requests pay +0.25% fee per docs)
- NO TESTNET: "There is no testnet version of NEAR Intents - use small
  amounts for test swaps." Any live call moves real funds => his tap.
- Status tracking: GET /v0/status?depositAddress=<addr>[&depositMemo=<memo>]
  (VERIFIED verbatim from the OpenAPI spec at
  https://docs.near-intents.org/api-reference/oneclick/check-swap-execution-status.md,
  read 2026-10-22). depositAddress = the unique deposit address from the
  quote response (required); depositMemo = required only when the quote
  response included a deposit memo (MEMO deposit-mode chains). Status enum:
  KNOWN_DEPOSIT_TX, PENDING_DEPOSIT, INCOMPLETE_DEPOSIT, PROCESSING,
  SUCCESS, REFUNDED, FAILED. 401 = invalid key/JWT, 404 = address not found.
  Read-only call — moves no funds, but still gated behind live=True for
  consistency (network leaves the VM only on his explicit tap).

Design rules: stdlib only; transport injectable for tests; the JWT is
read from the NEAR_INTENTS_JWT env var only, never logged, never stored.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
import urllib.error


BASE_URL = "https://1click.chaindefuser.com/v0"  # verified, docs 2026-10-08

# Fields captured verbatim from the docs' quote example. Anything else the
# caller passes goes through labeled as caller-supplied, not docs-verified.
VERIFIED_QUOTE_FIELDS = ("swapType", "originAsset", "depositType",
                         "destinationAsset", "amount")


# Status enum captured verbatim from the 1Click OpenAPI spec
# (docs.near-intents.org/api-reference/oneclick/check-swap-execution-status.md,
# read 2026-10-22).
EXECUTION_STATUS = ("KNOWN_DEPOSIT_TX", "PENDING_DEPOSIT",
                    "INCOMPLETE_DEPOSIT", "PROCESSING",
                    "SUCCESS", "REFUNDED", "FAILED")
TERMINAL_STATUS = ("SUCCESS", "REFUNDED", "FAILED")


def is_terminal(status: str) -> bool:
    """True when the swap reached a terminal state (no more transitions)."""
    return status in TERMINAL_STATUS


class OneClickError(Exception):
    """Typed error for 1Click API failures (network, HTTP, schema)."""


def nep141(contract: str) -> str:
    """NEAR fungible-token asset id: nep141:<contract>. Verified shape."""
    contract = contract.strip()
    if not contract:
        raise ValueError("contract must be non-empty")
    return "nep141:" + contract


class OneClickClient:
    """Thin client over the verified 1Click endpoints.

    Live calls need NEAR_INTENTS_JWT in the environment (his tap) and move
    real funds on mainnet (no testnet exists) — construct with
    live=False (default) and every network method raises until he
    explicitly enables it.
    """

    def __init__(self, jwt: str | None = None, base_url: str = BASE_URL,
                 live: bool = False, transport=None):
        self.jwt = jwt or os.environ.get("NEAR_INTENTS_JWT")
        self.base_url = base_url.rstrip("/")
        self.live = live
        self._transport = transport or self._urllib_transport

    # -- transport ---------------------------------------------------------
    @staticmethod
    def _urllib_transport(method, url, headers, body):
        req = urllib.request.Request(url, data=body, headers=headers,
                                     method=method)
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            raise OneClickError(f"HTTP {e.code} on {method} {url}") from e
        except Exception as e:  # timeouts, DNS, proxy stalls
            raise OneClickError(f"transport failure on {method} {url}: {e}") from e

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json",
                   "User-Agent": "IntentPilot/1click-client"}
        if self.jwt:
            headers["Authorization"] = "Bearer " + self.jwt
        return headers

    def _call(self, method, path, payload=None):
        if not self.live:
            raise OneClickError(
                "live calls disabled: 1Click has no testnet and moves real "
                "funds — enable live=True only on his explicit tap "
                "(NEAR_INTENTS_JWT in env).")
        body = json.dumps(payload).encode() if payload is not None else None
        status, raw = self._transport(method, self.base_url + path,
                                      self._headers(), body)
        try:
            return status, json.loads(raw.decode())
        except Exception as e:
            raise OneClickError(f"non-JSON response on {method} {path}") from e

    # -- verified endpoints -------------------------------------------------
    def get_tokens(self):
        """GET /v0/tokens — verified endpoint."""
        return self._call("GET", "/tokens")

    def request_quote(self, origin_asset: str, destination_asset: str,
                      amount: str, swap_type: str = "EXACT_INPUT",
                      deposit_type: str = "ORIGIN_CHAIN", **extra):
        """POST /v0/quote — verified fields only unless caller adds extras.

        amount: smallest-unit STRING (e.g. yoctoNEAR), never float.
        extra: caller-supplied fields, passed through but NOT docs-verified.
        """
        if not (isinstance(amount, str) and amount.isdigit()):
            raise ValueError("amount must be a smallest-unit digit string")
        payload = {
            "swapType": swap_type,
            "originAsset": origin_asset,
            "depositType": deposit_type,
            "destinationAsset": destination_asset,
            "amount": amount,
        }
        payload.update(extra)
        verified = {k: (k in VERIFIED_QUOTE_FIELDS) for k in payload}
        status, data = self._call("POST", "/quote", payload)
        return {"status": status, "quote": data, "field_verified": verified,
                "payload": payload}

    def get_execution_status(self, deposit_address: str,
                             deposit_memo: str | None = None):
        """GET /v0/status — verified endpoint + verified query-param shape.

        deposit_address: unique deposit address from the quote response
            (required, non-empty). deposit_memo: pass only when the quote
            response included a deposit memo (MEMO deposit-mode chains) —
            the docs require it in that case.
        Returns {"status": http_status, "execution": <parsed payload>,
                 "execution_status": <the status enum string>,
                 "is_terminal": bool}.
        Read-only: moves no funds. Still requires live=True (his tap).
        """
        if not (isinstance(deposit_address, str)
                and deposit_address.strip()):
            raise ValueError("deposit_address must be a non-empty string")
        params = {"depositAddress": deposit_address.strip()}
        if deposit_memo:
            params["depositMemo"] = deposit_memo
        http_status, data = self._call(
            "GET", "/status?" + urllib.parse.urlencode(params))
        exec_status = data.get("status") if isinstance(data, dict) else None
        return {"status": http_status, "execution": data,
                "execution_status": exec_status,
                "is_terminal": is_terminal(exec_status) if exec_status else False,
                "status_known": exec_status in EXECUTION_STATUS}
