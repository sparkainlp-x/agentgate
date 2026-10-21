"""Tests for agentgate. Run: python tests.py"""

import copy

from agentgate import Gate, IdentityRegistry, Lease, LeaseBook, Ledger, audit, verify_chain
from agentgate.ledger import _hash_obj


class Clock:
    def __init__(self):
        self.t = 0

    def __call__(self):
        return self.t


def setup(clock=None, caps=None, expires=100):
    clock = clock or Clock()
    ids = IdentityRegistry()
    ids.propose("a1", "Agent One", "testing", owner="Jean")
    ids.approve("a1", approver="Jean")
    leases = LeaseBook()
    leases.issue(Lease("L1", "a1", "Jean",
                       caps if caps is not None else
                       [{"action": "read", "scope": "files/docs/*"}],
                       issued_tick=0, expires_tick=expires))
    ledger = Ledger()
    gate = Gate(ids, leases, ledger,
                {"read": lambda r, p: "data",
                 "spend_money": lambda r, p: "paid"}, clock=clock)
    return gate, ids, leases, ledger


def test_pending_identity_denied_then_allowed():
    ids = IdentityRegistry()
    ids.propose("a1", "A", "t", owner="Jean")
    leases = LeaseBook()
    leases.issue(Lease("L1", "a1", "Jean", [{"action": "read", "scope": "*"}], 0, 100))
    gate = Gate(ids, leases, Ledger(), {"read": lambda r, p: "x"}, clock=Clock())
    assert gate.act("a1", "L1", "read", "files/docs/x")["decision"] == "DENY"
    ids.approve("a1", approver="Jean")
    assert gate.act("a1", "L1", "read", "files/docs/x")["decision"] == "ALLOW"


def test_unknown_suspended_and_foreign_lease_denied():
    gate, ids, leases, _ = setup()
    assert gate.act("ghost", "L1", "read", "files/docs/x")["decision"] == "DENY"
    leases.issue(Lease("L2", "someone-else", "Jean",
                       [{"action": "read", "scope": "*"}], 0, 100))
    assert gate.act("a1", "L2", "read", "files/docs/x")["decision"] == "DENY"
    ids.suspend("a1")
    assert gate.act("a1", "L1", "read", "files/docs/x")["decision"] == "DENY"


def test_scope_and_expiry_and_revocation():
    clock = Clock()
    gate, _, leases, _ = setup(clock=clock)
    assert gate.act("a1", "L1", "read", "files/docs/a")["decision"] == "ALLOW"
    assert gate.act("a1", "L1", "read", "files/private/a")["decision"] == "DENY"
    clock.t = 100
    assert gate.act("a1", "L1", "read", "files/docs/a")["decision"] == "DENY"
    clock.t = 50
    leases.revoke("L1")
    assert gate.act("a1", "L1", "read", "files/docs/a")["decision"] == "DENY"


def test_limits_count_and_amount():
    caps = [{"action": "read", "scope": "*", "limits": {"max_count": 2}},
            {"action": "spend_money", "scope": "vendor/*",
             "limits": {"max_total_amount": 50}}]
    gate, _, _, _ = setup(caps=caps)
    assert gate.act("a1", "L1", "read", "x")["decision"] == "ALLOW"
    assert gate.act("a1", "L1", "read", "x")["decision"] == "ALLOW"
    assert gate.act("a1", "L1", "read", "x")["decision"] == "DENY"
    assert gate.act("a1", "L1", "spend_money", "vendor/s", {"amount": 30})["decision"] == "ALLOW"
    assert gate.act("a1", "L1", "spend_money", "vendor/s", {"amount": 30})["decision"] == "DENY"
    assert gate.act("a1", "L1", "spend_money", "vendor/s", {"amount": 20})["decision"] == "ALLOW"


def test_attempts_are_ledgered_and_chain_verifies():
    gate, _, _, ledger = setup()
    gate.act("a1", "L1", "read", "files/docs/a")
    gate.act("a1", "L1", "read", "files/private/a")
    assert len(ledger.entries) == 2
    assert [e["decision"] for e in ledger.entries] == ["ALLOW", "DENY"]
    ok, bad = verify_chain(ledger.entries)
    assert ok and bad is None
    tampered = copy.deepcopy(ledger.entries)
    tampered[1]["decision"] = "ALLOW"
    ok, bad = verify_chain(tampered)
    assert not ok and bad == 1


def test_audit_passes_clean_and_catches_forged_allow():
    gate, _, leases, ledger = setup()
    gate.act("a1", "L1", "read", "files/docs/a")
    lease_dicts = {"L1": leases.get("L1").to_dict()}
    rep = audit(ledger.entries, lease_dicts, {"a1"})
    assert rep["audit_passed"]
    prev = ledger.entries[-1]["entry_hash"]
    forged = {"seq": 1, "tick": 10, "agent_id": "a1", "lease_id": "L1",
              "action": "spend_money", "resource": "vendor/x",
              "decision": "ALLOW", "reason": "within lease",
              "payload_sha256": None, "result_sha256": None, "prev_hash": prev}
    forged["entry_hash"] = _hash_obj(forged)
    rep2 = audit(ledger.entries + [forged], lease_dicts, {"a1"})
    assert rep2["chain_ok"] and not rep2["audit_passed"]
    assert any("no capability" in v["why"] for v in rep2["violations"])


def test_identity_immutable_registration():
    ids = IdentityRegistry()
    ids.propose("a1", "A", "t", owner="Jean")
    try:
        ids.propose("a1", "A2", "other", owner="Jean")
        raise AssertionError("duplicate identity accepted")
    except ValueError:
        pass


if __name__ == "__main__":
    for name, fn in sorted(
        [(k, v) for k, v in globals().items() if k.startswith("test_")]
    ):
        fn()
        print(f"PASS {name}")
    print("all tests passed")
