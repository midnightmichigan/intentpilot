"""Adapters package: wire-intent serialization (see adapters/wire.py)
and the verified NEAR Intents 1Click API client (see adapters/oneclick.py)."""
from .wire import canonical_wire, NearIntentsAdapter, NEAR_WIRE_VERIFY_LIST
from .oneclick import (OneClickClient, OneClickError, nep141, BASE_URL,
                       EXECUTION_STATUS, TERMINAL_STATUS, is_terminal)

__all__ = ["canonical_wire", "NearIntentsAdapter", "NEAR_WIRE_VERIFY_LIST",
           "OneClickClient", "OneClickError", "nep141", "BASE_URL",
           "EXECUTION_STATUS", "TERMINAL_STATUS", "is_terminal"]
