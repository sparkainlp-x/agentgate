# AgentGate

**Identity, leases, and a ledger for AI agent actions.**

An agent should be able to answer — with proof, not logs it wrote
itself — three questions about everything it did: *who approved this
identity, what was it allowed to do, and what did it actually do,
including what it tried?* AgentGate is the layer that makes those
answers structural:

```
identity   proposed -> human APPROVED -> committed (immutable, suspendable)
lease      (action, scope, limits) -- scoped, expiring, revocable; no ambient authority
gate       every action decided fail-closed BEFORE it runs; attempts ledgered either way
ledger     hash-chained; payloads stored as hashes; tampering breaks the chain
audit      external replay: every ALLOW re-checked against the lease terms
```

Generalized from `identity-runtime` (one governed persona) into
infrastructure any agent — scripted, LLM-driven, or robotic — can be
routed through. Stdlib-only Python. AGPL-3.0.

## Quick start

```bash
python tests.py   # 7 tests
python demo.py    # the full scenario + both forgery proofs
```

## The demo, in brief

`helper-1` is approved and leased: read `files/docs/*`, respond in
chat, spend at most **50 total** at one vendor. Email is never leased.

- read a doc ✓ · read `files/private/keys.txt` **DENY** (scope)
- respond ✓ · send_email **DENY** (no capability)
- spend 30 ✓ · spend 30 again **DENY** (budget) · spend 20 ✓ (exactly 50)
- after expiry **DENY** · under a revoked lease **DENY** · unknown agent **DENY**
- ledger: 10 entries (4 allowed, 6 denied), chain verifies, audit passes
- edit one entry → chain breaks at that entry
- forge an ALLOW with **valid chain hashes** → chain verifies, but the
  replay audit still catches it: *no capability ever granted that action*

## Why the audit matters

Hash chains prove the record wasn't edited. They don't prove the
gate behaved. The audit replays every ALLOW against identity state,
lease terms, tick windows, and cumulative limits — from the raw
records, without the gate — so accountability doesn't require
trusting the gate. See `DESIGN.md`.

## Honest boundary

The gate governs actions **routed through it**. An agent with a
direct line to a tool bypasses it entirely; deployment means hosts
route actions here, the way payments route through a processor.
Approval quality, scope naming discipline, and clock honesty are
host responsibilities — all visible in the ledger when neglected.

## Layout

```
agentgate/
  identity.py  propose/approve/suspend; committed identities are immutable
  lease.py     capabilities, scope globs, limits, expiry, revocation
  gate.py      fail-closed enforcement; receipts per action
  ledger.py    hash-chained entries; payload/result hashing
  audit.py     external replay audit
demo.py        scenario + tamper/forgery proofs
tests.py       7 tests
DESIGN.md      the deep think
```

## Claims note

All results above come from the included `demo.py` and `tests.py`,
run on a SYNTHETIC scenario. No production deployment or external
evaluation has been run (UNRUN).

## Citing

AgentGate v0.1.0 is archived on Zenodo: [10.5281/zenodo.23566402](https://doi.org/10.5281/zenodo.23566402) (version DOI; all versions: [10.5281/zenodo.23566401](https://doi.org/10.5281/zenodo.23566401)). See also [CITATION.cff](CITATION.cff).

```bibtex
@software{agentgate_0_1_0,
  author  = {Brisson, Jean-François},
  title   = {AgentGate},
  version = {0.1.0},
  year    = {2026},
  doi     = {10.5281/zenodo.23566402},
  url     = {https://github.com/sparkainlp-x/agentgate},
  license = {AGPL-3.0-only}
}
```

## Acknowledgements

Mun Seok Lee is acknowledged for discussion only. We cannot verify any specific contribution to this repository, and no file here is known to derive from a package received under his name. He is not an author of this release, and no endorsement of this code or its conclusions is implied.

## License

AGPL-3.0.
