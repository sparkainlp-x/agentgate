"""AgentGate: identity, leases, and a ledger for AI agent actions.

The accountability layer for agents that act in the world:

    identity  -- committed by human approval, immutable, suspendable
    lease     -- least-privilege capabilities: scoped, limited,
                 expiring, revocable; no ambient authority
    gate      -- the single enforcement point; fail-closed; every
                 attempt (allowed or denied) is ledgered
    ledger    -- hash-chained, payloads stored as hashes; tampering
                 breaks verification at the edited entry
    audit     -- an external replay that re-evaluates every ALLOW
                 against the lease terms: proof, not trust

Generalized from identity-runtime (one governed persona) into
infrastructure any agent -- scripted, LLM-driven, or robotic -- can
be routed through. Handlers are the host's; the gate governs.

Honest boundary: the gate governs actions ROUTED THROUGH it. An
agent with direct access to a tool, bypassing the gate, is out of
scope -- exactly as a claims passport cannot stop fabrication at
the source. Deployment means hosts route actions here, the way
payments route through a payment processor.
"""

from .identity import IdentityRegistry
from .lease import Lease, LeaseBook
from .ledger import Ledger, verify_chain
from .gate import Gate
from .audit import audit

__all__ = [
    "IdentityRegistry",
    "Lease",
    "LeaseBook",
    "Ledger",
    "verify_chain",
    "Gate",
    "audit",
]

__version__ = "0.1.0"
