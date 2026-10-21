"""Capability leases: least privilege, scoped, expiring, revocable.

An agent holds NO ambient authority. Every action requires a lease
(pattern from identity-runtime's capability leases, generalized):

    lease = {
      lease_id, agent_id, issued_by,
      capabilities: [ {action, scope, limits} ... ],
      issued_tick, expires_tick, revoked
    }

- action:   a verb the host application registers ("read",
            "respond_in_chat", "send_email", "spend_money", ...)
- scope:    an fnmatch glob over resource strings ("files/docs/*").
            A capability authorizes only resources its scope matches.
- limits:   optional {"max_count": n} (per capability, cumulative)
            and/or {"max_total_amount": x} (cumulative sum of
            payload["amount"] for that capability).
- expiry:   leases are issued against a logical clock (ticks) so
            behaviour is deterministic and testable; a lease past
            expires_tick authorizes nothing.
- revocation: immediate and permanent for that lease (the kill
            switch). A revoked lease cannot be un-revoked; issue a
            new lease instead -- the history stays legible.

The full lease record is what the audit replays against: if the
gate ever allowed something the lease did not grant, the audit
finds it from these records alone.
"""

import fnmatch


class Lease:
    def __init__(self, lease_id, agent_id, issued_by, capabilities,
                 issued_tick, expires_tick):
        self.lease_id = lease_id
        self.agent_id = agent_id
        self.issued_by = issued_by
        self.capabilities = capabilities
        self.issued_tick = issued_tick
        self.expires_tick = expires_tick
        self.revoked = False

    def to_dict(self):
        return {
            "lease_id": self.lease_id,
            "agent_id": self.agent_id,
            "issued_by": self.issued_by,
            "capabilities": self.capabilities,
            "issued_tick": self.issued_tick,
            "expires_tick": self.expires_tick,
            "revoked": self.revoked,
        }

    def active_at(self, tick):
        return (not self.revoked) and self.issued_tick <= tick < self.expires_tick

    def match(self, action, resource):
        """Return the capability granting (action, resource), or None."""
        for cap in self.capabilities:
            if cap["action"] == action and fnmatch.fnmatchcase(resource, cap["scope"]):
                return cap
        return None


class LeaseBook:
    def __init__(self):
        self._leases = {}

    def issue(self, lease):
        if lease.lease_id in self._leases:
            raise ValueError(f"lease already exists: {lease.lease_id}")
        self._leases[lease.lease_id] = lease
        return lease

    def get(self, lease_id):
        return self._leases.get(lease_id)

    def revoke(self, lease_id):
        lease = self._leases.get(lease_id)
        if lease is None:
            raise ValueError(f"unknown lease: {lease_id}")
        lease.revoked = True
        return lease
