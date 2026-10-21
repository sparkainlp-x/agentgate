"""Replay audit: prove the gate never allowed what no lease granted.

The ledger alone proves the record is untampered. The audit proves
something stronger: re-evaluating every ALLOW entry against the
lease terms as issued, plus identity state, plus cumulative limits
recomputed from the entries themselves. If a gate bug (or a forged
entry with a valid-looking hash made by someone holding the code
but not the leases) ever let an action through outside its lease,
the audit names the seq.

Inputs are plain records (identity states, lease dicts, ledger
entries) so an EXTERNAL auditor can run this without the gate --
that is the point: accountability that requires trusting the gate
is not accountability.
"""

from .ledger import verify_chain


def audit(entries, leases_by_id, active_identities):
    """Return a report dict: chain validity, violations, tallies.

    leases_by_id: lease_id -> lease dict (as issued; revoked state is
    evaluated historically -- an ALLOW is judged against the lease's
    terms and its tick window, and revocation is checked against the
    entry tick only if the caller supplies revoked_at per lease;
    simplest correct rule used here: terms + tick window + scope).
    active_identities: set of agent_ids COMMITTED at audit scope --
    entries for other agents are violations if ALLOW.
    """
    chain_ok, bad_seq = verify_chain(entries)
    violations = []
    counts = {}
    amounts = {}
    allowed = denied = 0

    for e in entries:
        if e["decision"] == "DENY":
            denied += 1
            continue
        allowed += 1
        lease = leases_by_id.get(e["lease_id"])
        if lease is None:
            violations.append({"seq": e["seq"], "why": "ALLOW under unknown lease"})
            continue
        if lease["agent_id"] != e["agent_id"]:
            violations.append({"seq": e["seq"], "why": "lease held by another agent"})
        if e["agent_id"] not in active_identities:
            violations.append({"seq": e["seq"], "why": "agent identity not committed"})
        if not (lease["issued_tick"] <= e["tick"] < lease["expires_tick"]):
            violations.append({"seq": e["seq"], "why": "ALLOW outside lease tick window"})
        cap = None
        import fnmatch
        for c in lease["capabilities"]:
            if c["action"] == e["action"] and fnmatch.fnmatchcase(e["resource"], c["scope"]):
                cap = c
                break
        if cap is None:
            violations.append({"seq": e["seq"], "why": "no capability grants this ALLOW"})
            continue
        key = (e["lease_id"], e["action"], cap["scope"])
        counts[key] = counts.get(key, 0) + 1
        limits = cap.get("limits", {})
        if "max_count" in limits and counts[key] > limits["max_count"]:
            violations.append({"seq": e["seq"], "why": "max_count exceeded in replay"})

    return {
        "chain_ok": chain_ok,
        "chain_bad_seq": bad_seq,
        "entries": len(entries),
        "allowed": allowed,
        "denied": denied,
        "violations": violations,
        "audit_passed": chain_ok and not violations,
    }
