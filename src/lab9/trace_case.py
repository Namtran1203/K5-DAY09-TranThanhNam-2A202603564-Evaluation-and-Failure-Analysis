"""Trace -> decision: lay one trial's reply, tool calls and ledger side by side.

    python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11

Find the FIRST wrong step, then turn that trial into a regression case
(docs/trace_case.md). Runs the shape on a fresh temp store, never the team DB.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

from lab8.console import utf8_stdio
from lab8.benchmark import prepare_from_memory, run_trial
from lab8.db import connect, load_json, load_jsonl
from lab8.metrics import artifact_blob, ledger_snapshot, trial_pass, unexpected_ledger_rows
from lab9 import variants

WORLD = Path("data/public_world_state.json")


def investigate(shape: str, claim_id: str, seed: int) -> dict:
    variants.register()
    claims = load_jsonl(Path("data/public_claims.jsonl"))
    labels = {c["claim_id"]: c["expected"] for c in claims}
    with tempfile.TemporaryDirectory(prefix="lab9-case-", ignore_cleanup_errors=True) as tmp:
        store = Path(tmp) / f"{shape}-{claim_id}-{seed}.sqlite"
        prepare_from_memory(store, load_json(WORLD), claims)
        started = time.time()
        payload, error = run_trial(shape, claim_id, seed, store)
        conn = connect(store)
        try:
            snap = ledger_snapshot(conn, claim_id)
            ok, reason = trial_pass(payload, labels[claim_id], conn, started_at=started) if payload else (False, error)
            events = json.loads(Path(payload["trace_path"]).read_text(encoding="utf-8")).get("events", []) if payload and Path(payload.get("trace_path") or "").is_file() else []
            trial = {"result": payload or {"status": "error"}, "snapshot": snap,
                     "unexpected_rows": unexpected_ledger_rows(conn, claim_id),
                     "blob": artifact_blob(payload) if payload else "", "events": events,
                     "lab8_pass": ok, "lab8_reason": reason}
        finally:
            conn.close()
    return {"trial": trial, "label": labels[claim_id]}


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.trace_case")
    ap.add_argument("--shape", required=True)
    ap.add_argument("--claim", required=True)
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args(argv)
    case = investigate(args.shape, args.claim, args.seed)
    t, label = case["trial"], case["label"]
    print(f"== {args.shape} {args.claim}@{args.seed}  lab8 grader: {'PASS' if t['lab8_pass'] else 'FAIL'} ({t['lab8_reason']})")
    print("-- trace (step, kind, payload)")
    for i, e in enumerate(t["events"], 1):
        print(f"  {i:>2} {e.get('kind', '?'):<18} {json.dumps(e.get('payload'), ensure_ascii=False)[:110]}")
    print("-- ledger vs label")
    for k in ("refund_vnd", "refund_count"):
        mark = "" if t["snapshot"].get(k) == label.get(k) else "   <-- differs"
        print(f"  {k:<14} ledger={t['snapshot'].get(k)!s:<8} label={label.get(k)}{mark}")
    print(f"  status         result={t['result'].get('status')!s:<8} label={label.get('status')}")
    print(f"  unexpected ledger rows: {t['unexpected_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
