"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems = []
    for name, rep in (("PR", pr), ("baseline", base)):
        manifest, rows = rep.get("manifest", {}), rep.get("rows", [])
        seeds = manifest.get("seeds", [])
        expected = manifest.get("items", 0) * len(seeds)
        pairs = [(r.get("item_id"), r.get("seed")) for r in rows]
        if len(rows) != expected or len(set(pairs)) != len(rows):
            problems.append(f"{name}: row count or duplicate item/seed")
        if len(set(seeds)) != len(seeds) or {r.get("seed") for r in rows} != set(seeds):
            problems.append(f"{name}: seed manifest mismatch")
        if rep.get("evaluator_failures"):
            problems.append(f"{name}: evaluator failures")
        for mid, value in rep.get("metrics", {}).items():
            if isinstance(value, (int, float)) and not isinstance(value, bool) and not math.isfinite(value):
                problems.append(f"{name}: {mid} is nonfinite")
        for m in spec["metrics"]:
            mid = m["id"]
            if mid not in rep.get("metrics", {}) or rep["metrics"][mid] is None:
                problems.append(f"{name}: missing metric {mid}")
            if mid in GRADERS and any(r.get(mid) is None for r in rows):
                problems.append(f"{name}: missing row value {mid}")
        if rows and all("cost" in r for r in rows) and all(all(r.get(mid) is not None for r in rows) for mid in GRADERS if mid in rep.get("metrics", {})):
            metric_ids = [m["id"] for m in spec["metrics"] if m["id"] in GRADERS]
            calculated = aggregate(rows, metric_ids, k_values=spec.get("pass_k", []))
            for mid in (m["id"] for m in spec["metrics"]):
                reported, actual = rep.get("metrics", {}).get(mid), calculated.get(mid)
                if isinstance(reported, (int, float)) and actual is not None and math.isfinite(reported) and abs(reported - actual) > 0.00011:
                    problems.append(f"{name}: aggregate {mid} differs from rows")
    pr_pairs = {(r.get("item_id"), r.get("seed")) for r in pr.get("rows", [])}
    base_pairs = {(r.get("item_id"), r.get("seed")) for r in base.get("rows", [])}
    if pr_pairs != base_pairs or pr.get("manifest", {}).get("seeds") != base.get("manifest", {}).get("seeds"):
        problems.append("PR item/seed coverage differs from baseline")
    base_slices = {r["item_id"]: set(r.get("slices") or []) for r in base.get("rows", [])}
    if any(set(r.get("slices") or []) != base_slices.get(r.get("item_id"), set()) for r in pr.get("rows", [])):
        problems.append("PR slice tags differ from baseline")
    if base_spec and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        for section in ("metrics", "slices"):
            old = {(m.get("id") if section == "metrics" else (m.get("name"), m.get("metric"))): m
                   for m in base_spec.get(section, [])}
            new = {(m.get("id") if section == "metrics" else (m.get("name"), m.get("metric"))): m
                   for m in spec.get(section, [])}
            for key, prior in old.items():
                cur = new.get(key)
                if cur is None:
                    problems.append(f"ratchet: removed {section} {key}")
                    continue
                if prior.get("blocking") and not cur.get("blocking"):
                    problems.append(f"ratchet: unblocked {key}")
                pth = prior.get("threshold", {}) if section == "metrics" else prior
                cth = cur.get("threshold", {}) if section == "metrics" else cur
                for bound in ("min", "max", "max_increase"):
                    if bound in pth and (bound not in cth or
                            (bound == "min" and cth[bound] < pth[bound]) or
                            (bound != "min" and cth[bound] > pth[bound])):
                        problems.append(f"ratchet: loosened {key}/{bound}")
                if pth.get("no_significant_drop") and not cth.get("no_significant_drop"):
                    problems.append(f"ratchet: removed significance check {key}")
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices", []):
        name, mid = s["name"], s["metric"]
        a, b = per_item(pr, mid, name), per_item(base, mid, name)
        keys = sorted(set(a) & set(b))
        value = sum(a.values()) / len(a) if a else None
        fail = value is None or ("min" in s and value < s["min"])
        note = ""
        if s.get("no_significant_drop") and keys:
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000),
                                               rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            fail |= hi < 0
        if fail and s.get("blocking"):
            blocked.append(f"slice:{name}/{mid}")
        lines.append(f"  slice:{name}/{mid} {value!s} {note} {'BLOCK' if fail and s.get('blocking') else 'ok' if not fail else 'warn'}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
