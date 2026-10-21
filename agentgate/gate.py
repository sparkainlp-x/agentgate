"""The Gate: the single enforcement point for agent actions.

An agent does nothing except through gate.act(...). Every call is
decided FAIL-CLOSED -- any doubt is a DENY, and the attempt is
ledgered either way:

    1. identity must exist and be COMMITTED (not PENDING/SUSPENDED)
    2. lease must exist, belong to this agent, and be active
       (not expired, not revoked) at the current tick
    3. some capability in the lease must grant (action, resource)
    4. the capability's limits must not be exhausted
       (max_count, max_total_amount -- tracked cumulatively)
    5. a handler must be registered for the action

Only then does the handler run. Its result is hashed into the
ledger entry, and the caller receives a receipt carrying the
entry_hash -- the agent's proof of what it did, checkable by anyone
with the ledger.

The clock is injected (a callable returning int ticks) so lease
expiry is deterministic and testable; a host app passes time.time
or a step counter.
"""

import itertools


class Gate:
    def __init__(self, identities, leases, ledger, handlers, clock=None):
        self.identities = identities
        self.leases = leases
        self.ledger = ledger
        self.handlers = handlers
        self.clock = clock or itertools.count().__next__
        self._counts = {}    # (lease_id, action, scope) -> n allowed
        self._amounts = {}   # (lease_id, action, scope) -> total amount

    def _deny(self, tick, agent_id, lease_id, action, resource, reason, payload):
        entry = self.ledger.append(tick, agent_id, lease_id, action, resource,
                                   "DENY", reason, payload=payload)
        return {"decision": "DENY", "reason": reason, "receipt": entry["entry_hash"]}

    def act(self, agent_id, lease_id, action, resource, payload=None):
        tick = int(self.clock())
        if not self.identities.is_active(agent_id):
            return self._deny(tick, agent_id, lease_id, action, resource,
                              "identity unknown, pending, or suspended", payload)
        lease = self.leases.get(lease_id)
        if lease is None or lease.agent_id != agent_id:
            return self._deny(tick, agent_id, lease_id, action, resource,
                              "lease unknown or not held by this agent", payload)
        if not lease.active_at(tick):
            return self._deny(tick, agent_id, lease_id, action, resource,
                              "lease expired or revoked", payload)
        cap = lease.match(action, resource)
        if cap is None:
            return self._deny(tick, agent_id, lease_id, action, resource,
                              "no capability grants this action on this resource",
                              payload)
        key = (lease_id, action, cap["scope"])
        limits = cap.get("limits", {})
        if "max_count" in limits and self._counts.get(key, 0) >= limits["max_count"]:
            return self._deny(tick, agent_id, lease_id, action, resource,
                              "capability max_count exhausted", payload)
        amount = 0.0
        if isinstance(payload, dict) and "amount" in payload:
            amount = float(payload["amount"])
        if "max_total_amount" in limits and \
                self._amounts.get(key, 0.0) + amount > limits["max_total_amount"]:
            return self._deny(tick, agent_id, lease_id, action, resource,
                              "capability max_total_amount would be exceeded", payload)
        handler = self.handlers.get(action)
        if handler is None:
            return self._deny(tick, agent_id, lease_id, action, resource,
                              "no handler registered for action", payload)

        result = handler(resource, payload)
        self._counts[key] = self._counts.get(key, 0) + 1
        self._amounts[key] = self._amounts.get(key, 0.0) + amount
        entry = self.ledger.append(tick, agent_id, lease_id, action, resource,
                                   "ALLOW", "within lease", payload=payload,
                                   result=result)
        return {"decision": "ALLOW", "result": result,
                "receipt": entry["entry_hash"]}
