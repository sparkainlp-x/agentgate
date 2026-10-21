"""Committed agent identities.

An agent may act only under an identity that a human has APPROVED.
Registration is two-step (pattern from identity-runtime):

    propose(agent_id, name, purpose, owner)  -> PENDING record
    approve(agent_id, approver)              -> COMMITTED record

Rules:
- A PENDING identity authorizes nothing.
- A COMMITTED identity is immutable: name, purpose, and owner are
  frozen at approval. Changing them means a new identity version
  (propose again under a new id) -- an agent can never quietly
  become a different agent under the same id.
- Suspension is a state, not an edit: a suspended identity's leases
  all stop working (the gate checks), and the suspension itself is
  a recorded event, not a silent flag flip.
"""

import hashlib
import json


def _policy_hash(record):
    canonical = json.dumps(
        {k: record[k] for k in ("agent_id", "name", "purpose", "owner")},
        sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IdentityRegistry:
    def __init__(self):
        self._records = {}

    def propose(self, agent_id, name, purpose, owner):
        if agent_id in self._records:
            raise ValueError(f"identity already exists: {agent_id}")
        rec = {"agent_id": agent_id, "name": name, "purpose": purpose,
               "owner": owner, "state": "PENDING", "approver": None}
        rec["policy_hash"] = _policy_hash(rec)
        self._records[agent_id] = rec
        return rec

    def approve(self, agent_id, approver):
        rec = self._records.get(agent_id)
        if rec is None:
            raise ValueError(f"unknown identity: {agent_id}")
        if rec["state"] != "PENDING":
            raise ValueError(f"identity not pending: {agent_id} ({rec['state']})")
        rec["state"] = "COMMITTED"
        rec["approver"] = approver
        return rec

    def suspend(self, agent_id):
        rec = self._records.get(agent_id)
        if rec is None:
            raise ValueError(f"unknown identity: {agent_id}")
        rec["state"] = "SUSPENDED"
        return rec

    def get(self, agent_id):
        return self._records.get(agent_id)

    def is_active(self, agent_id):
        rec = self._records.get(agent_id)
        return bool(rec and rec["state"] == "COMMITTED")
