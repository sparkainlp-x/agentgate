"""Demo: an agent that can act only through the gate.

Scenario (deterministic, manual clock):
  helper-1 is proposed, approved, and leased: read project docs,
  respond in chat, spend up to 50 total at one vendor. Email is NOT
  leased. Watch the gate allow the leased actions and deny --
  on the record -- everything else: out-of-scope reads, unleased
  email, the spend that would break the budget, actions after the
  lease expires, actions after revocation.

Then the two proofs:
  1. tamper with one ledger entry -> chain verification breaks
     at exactly that entry;
  2. forge an ALLOW entry with VALID chain hashes (an attacker who
     holds the code) -> the chain verifies, but the replay audit
     still catches it: no capability ever granted that action.

Run:  python demo.py
"""

import copy

from agentgate import Gate, IdentityRegistry, Lease, LeaseBook, Ledger, audit, verify_chain
from agentgate.ledger import _hash_obj


class Clock:
    def __init__(self):
        self.t = 0

    def __call__(self):
        return self.t


def main():
    clock = Clock()
    ids = IdentityRegistry()
    ids.propose("helper-1", "Helper", "Draft replies and read project docs", owner="Jean")
    ids.approve("helper-1", approver="Jean")

    leases = LeaseBook()
    leases.issue(Lease("L1", "helper-1", issued_by="Jean",
                       capabilities=[
                           {"action": "read", "scope": "files/docs/*"},
                           {"action": "respond_in_chat", "scope": "*"},
                           {"action": "spend_money", "scope": "vendor/store",
                            "limits": {"max_total_amount": 50}},
                       ], issued_tick=0, expires_tick=100))
    ledger = Ledger()
    handlers = {
        "read": lambda res, p: f"<contents of {res}>",
        "respond_in_chat": lambda res, p: "<drafted reply>",
        "send_email": lambda res, p: "<sent>",
        "spend_money": lambda res, p: f"<paid {p['amount']} at {res}>",
    }
    gate = Gate(ids, leases, ledger, handlers, clock=clock)

    script = [
        ("read files/docs/plan.md", gate.act("helper-1", "L1", "read", "files/docs/plan.md")),
        ("read files/private/keys.txt", gate.act("helper-1", "L1", "read", "files/private/keys.txt")),
        ("respond in chat", gate.act("helper-1", "L1", "respond_in_chat", "chat/main")),
        ("send_email (never leased)", gate.act("helper-1", "L1", "send_email", "mail/ceo")),
        ("spend 30", gate.act("helper-1", "L1", "spend_money", "vendor/store", {"amount": 30})),
        ("spend 30 again (budget 50)", gate.act("helper-1", "L1", "spend_money", "vendor/store", {"amount": 30})),
        ("spend 20 (exactly to budget)", gate.act("helper-1", "L1", "spend_money", "vendor/store", {"amount": 20})),
    ]
    for label, r in script:
        print(f"  {r['decision']:<6} {label}" + (f" -- {r['reason']}" if r["decision"] == "DENY" else ""))

    clock.t = 150  # lease L1 expired at tick 100
    r = gate.act("helper-1", "L1", "read", "files/docs/plan.md")
    print(f"  {r['decision']:<6} read after lease expiry -- {r['reason']}")

    leases.issue(Lease("L2", "helper-1", issued_by="Jean",
                       capabilities=[{"action": "read", "scope": "files/docs/*"}],
                       issued_tick=150, expires_tick=200))
    leases.revoke("L2")
    r = gate.act("helper-1", "L2", "read", "files/docs/plan.md")
    print(f"  {r['decision']:<6} read under revoked lease -- {r['reason']}")

    r = gate.act("rogue-9", "L2", "read", "files/docs/plan.md")
    print(f"  {r['decision']:<6} unknown agent -- {r['reason']}")

    ok_chain, _ = verify_chain(ledger.entries)
    rep = audit(ledger.entries,
                {l.lease_id: l.to_dict() for l in leases._leases.values()},
                {"helper-1"})
    print(f"  ledger: {rep['entries']} entries, {rep['allowed']} allowed, "
          f"{rep['denied']} denied, chain ok: {ok_chain}, audit passed: {rep['audit_passed']}")

    # proof 1: tamper
    forged = copy.deepcopy(ledger.entries)
    forged[0]["resource"] = "files/private/keys.txt"
    ok_t, bad = verify_chain(forged)
    print(f"  tamper test: edited entry 0 -> chain ok: {ok_t} (breaks at seq {bad})")

    # proof 2: forged ALLOW with valid chain hashes
    prev = ledger.entries[-1]["entry_hash"]
    entry = {"seq": len(ledger.entries), "tick": 50, "agent_id": "helper-1",
             "lease_id": "L1", "action": "send_email", "resource": "mail/ceo",
             "decision": "ALLOW", "reason": "within lease",
             "payload_sha256": None, "result_sha256": None, "prev_hash": prev}
    entry["entry_hash"] = _hash_obj(entry)
    rep2 = audit(ledger.entries + [entry],
                 {l.lease_id: l.to_dict() for l in leases._leases.values()},
                 {"helper-1"})
    caught = any("no capability" in v["why"] for v in rep2["violations"])
    print(f"  forged-ALLOW test: chain ok: {rep2['chain_ok']}, "
          f"audit caught it: {caught} ({rep2['violations'][-1]['why'] if rep2['violations'] else 'none'})")

    ok = ok_chain and rep["audit_passed"] and not ok_t and caught
    print("RESULT:", "PASS -- leased actions allowed, everything else denied on the record; "
          "tampering and forgery both caught" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
