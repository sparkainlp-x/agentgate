# DESIGN — Deep think: agent accountability as infrastructure

## The problem, precisely

Agents are being given tools faster than they are being given
identities. The 2026 numbers frame it: most enterprises run agents
in production; almost none can answer three elementary questions
about any given action an agent took:

1. **Who** was this agent — not its display name, but the identity
   a human approved, with the purpose it was approved *for*?
2. **Was it allowed** — under what grant, with what scope and
   limits, at that moment?
3. **What did it do** — all of it, including what it *tried* to do?

Guidelines don't answer these. Logs written by the agent itself
don't answer them either — an agent (or its operator after an
incident) can edit its own diary. What answers them is the same
thing that answers them for money: an enforcement point the action
must pass through, plus a ledger the actor doesn't control.

## The model

Four components, each mapped to a property that financial
infrastructure takes for granted:

| Property | Finance | AgentGate |
|---|---|---|
| Committed identity | KYC / account holder | identity proposed + human-approved, immutable, suspendable |
| Least-privilege grant | card limits, scoped credentials | lease: (action, scope glob, limits), expiring, revocable |
| Enforcement at the point of action | payment processor declines | gate: fail-closed checks before any handler runs |
| Proof after the fact | statements + chargeback audit | hash-chained ledger + external replay audit |

Two decisions deserve argument:

**Attempts are ledgered, not just successes.** A ledger of only
allowed actions cannot distinguish "the agent never tried" from
"the gate stopped it twelve times." Incident review needs the
denials — they are also the earliest warning that an agent (or
someone steering it) is probing its fence.

**The audit is external and replay-based.** The gate software is
itself software; it can have bugs. The audit therefore re-evaluates
every ALLOW from the raw records — identity states, lease terms,
entries — without running or trusting the gate. The demo's hardest
test forges an ALLOW entry with *valid chain hashes* (an attacker
holding the code): the chain verifies, the entry is still caught,
because no lease ever granted that action. Hash chains prove the
record wasn't edited; replay proves the record was *earned*.

**Payloads are hashed, not stored.** The ledger proves what
happened without becoming a second copy of everything the agent
touched (data minimization, the signal-commons instinct). Hosts
keep content; the ledger keeps receipts.

## Deployment picture

- Wrap tool calls: an LLM agent's function-calling layer routes
  through the gate; the model experiences DENY as a tool result and
  plans around it, exactly as it plans around a declined card.
- Issue leases per task, not per agent lifetime: "for the next hour,
  read these docs, draft replies, spend nothing" is a lease.
- The kill switch is suspension: one call, every lease stops, and
  the suspension is itself on the record.
- Insurers and regulators get the audit, not a promise: entries +
  leases + identities are sufficient for an independent verdict.

## The honest limits

1. **The gate governs only what routes through it.** An agent with
   a direct line to a tool bypasses everything — the same limit as
   the claims layer (cannot stop fabrication at the source) and as
   payment networks (cash exists). Deployment discipline is part of
   the system, not a footnote.
2. **Identity approval is a human process.** The registry makes
   approval *necessary and recorded*; it cannot make approvers
   careful. Two-person approval (as in identity-runtime) is a policy
   choice the host can layer on the propose/approve split.
3. **Scopes are strings.** Glob scopes over resource names are only
   as meaningful as the host's naming discipline. A host that calls
   everything "resource/*" has leased everything.
4. **The clock is logical.** Hosts must supply real time (or accept
   step-count expiry). A host that freezes its clock freezes expiry
   — visible in the ledger's ticks, and therefore auditable, but
   hosts should wire a real clock.

## Relation to the portfolio

identity-runtime proved these ideas for one scripted persona.
AgentGate extracts them into infrastructure with no persona in it —
the governance layer any agent can be routed through. It composes
with Solution 1 (an agent's public claims can ship as claims-layer
passports, receipts as their checks) and inherits the org's rules:
fail closed, tag everything, publish the negative results.
