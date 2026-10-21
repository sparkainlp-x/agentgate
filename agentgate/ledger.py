"""Hash-chained action ledger (pattern from measurement-trail and
identity-runtime's audit ledger).

Every action ATTEMPT -- allowed or denied -- appends one entry:

    {seq, tick, agent_id, lease_id, action, resource,
     decision: ALLOW | DENY, reason,
     payload_sha256, result_sha256, prev_hash, entry_hash}

Design choices:
- Attempts are recorded, not just successes. Accountability that only
  logs what happened cannot answer "what did the agent TRY to do?"
- Payloads and results are stored as hashes, not raw content
  (data minimization): the ledger proves what happened without
  becoming a second copy of everything the agent touched. A host
  that needs content keeps it elsewhere and matches by hash.
- entry_hash chains over the canonical entry + prev_hash, so any
  edit, deletion, or reordering breaks verification at that seq.
"""

import hashlib
import json

GENESIS = "0" * 64


def _hash_obj(obj):
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def hash_payload(payload):
    if payload is None:
        return None
    if isinstance(payload, (dict, list)):
        return _hash_obj(payload)
    return hashlib.sha256(str(payload).encode("utf-8")).hexdigest()


class Ledger:
    def __init__(self):
        self.entries = []

    def append(self, tick, agent_id, lease_id, action, resource,
               decision, reason, payload=None, result=None):
        prev = self.entries[-1]["entry_hash"] if self.entries else GENESIS
        entry = {
            "seq": len(self.entries),
            "tick": tick,
            "agent_id": agent_id,
            "lease_id": lease_id,
            "action": action,
            "resource": resource,
            "decision": decision,
            "reason": reason,
            "payload_sha256": hash_payload(payload),
            "result_sha256": hash_payload(result),
            "prev_hash": prev,
        }
        entry["entry_hash"] = _hash_obj(entry)
        self.entries.append(entry)
        return entry

    def save_jsonl(self, path):
        with open(path, "w", encoding="utf-8") as f:
            for e in self.entries:
                f.write(json.dumps(e, sort_keys=True) + "\n")

    @staticmethod
    def load_jsonl(path):
        led = Ledger()
        with open(path, encoding="utf-8") as f:
            led.entries = [json.loads(line) for line in f if line.strip()]
        return led


def verify_chain(entries):
    """Re-check the hash chain. Return (ok, first_bad_seq_or_None)."""
    prev = GENESIS
    for i, e in enumerate(entries):
        if e.get("seq") != i or e.get("prev_hash") != prev:
            return False, i
        body = {k: v for k, v in e.items() if k != "entry_hash"}
        if _hash_obj(body) != e.get("entry_hash"):
            return False, i
        prev = e["entry_hash"]
    return True, None
