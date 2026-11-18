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
from collections import Counter
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
    graded = {m["id"] for m in spec["metrics"] if m["id"] in GRADERS}

    def finite(value):
        return isinstance(value, (int, float)) and math.isfinite(value)

    def inspect(report, name):
        manifest = report.get("manifest", {})
        rows, metrics = report.get("rows"), report.get("metrics")
        if not isinstance(rows, list) or not isinstance(metrics, dict):
            problems.append(f"{name}: invalid rows or metrics")
            return {}, {}
        if report.get("evaluator_failures"):
            problems.append(f"{name}: evaluator_failures is not empty")
        for mid, value in metrics.items():
            if not finite(value):
                problems.append(f"{name}: metric {mid} is missing or non-finite")
        for metric in spec["metrics"]:
            if metric["id"] not in metrics:
                problems.append(f"{name}: missing metric {metric['id']}")

        seeds, items = manifest.get("seeds"), manifest.get("items")
        if (not isinstance(seeds, list) or not seeds or
                any(type(s) is not int for s in seeds) or len(set(seeds)) != len(seeds) or
                type(items) is not int or items < 1):
            problems.append(f"{name}: invalid item count or seeds")
            return {}, {}
        if len(rows) != items * len(seeds):
            problems.append(f"{name}: row count differs from items x seeds")
        pairs, tags = {}, {}
        counts = Counter()
        for row in rows:
            if (not isinstance(row, dict) or not isinstance(row.get("item_id"), str) or
                    type(row.get("seed")) is not int):
                problems.append(f"{name}: invalid row identity")
                continue
            key = (row["item_id"], row["seed"])
            counts[key] += 1
            pairs[key] = row
            for mid in graded:
                value = row.get(mid)
                if not finite(value) or not 0 <= value <= 1:
                    problems.append(f"{name}: {key} has missing/invalid grader value {mid}")
            if "cost" in row or any(m["id"] == "cost_per_success" for m in spec["metrics"]):
                if not finite(row.get("cost")) or row["cost"] < 0:
                    problems.append(f"{name}: {key} has missing/invalid cost")
            slices = row.get("slices", [])
            if not isinstance(slices, list) or any(not isinstance(s, str) for s in slices):
                problems.append(f"{name}: {key} has invalid slice tags")
                continue
            tag_set = frozenset(slices)
            if len(tag_set) != len(slices):
                problems.append(f"{name}: {key} has duplicate slice tags")
            if row["item_id"] in tags and tags[row["item_id"]] != tag_set:
                problems.append(f"{name}: inconsistent slice tags across seeds for {row['item_id']}")
            tags[row["item_id"]] = tag_set
        if any(count != 1 for count in counts.values()):
            problems.append(f"{name}: duplicate (item_id, seed) rows")
        item_ids = {item for item, _ in pairs}
        if len(item_ids) != items or set(pairs) != {(item, seed) for item in item_ids for seed in seeds}:
            problems.append(f"{name}: rows do not cover the declared items and seeds")
        return pairs, tags

    pr_pairs, pr_tags = inspect(pr, "PR")
    base_pairs, base_tags = inspect(base, "baseline")
    if set(pr_pairs) != set(base_pairs):
        problems.append("PR and baseline have different (item_id, seed) sets")
    if pr_tags != base_tags:
        problems.append("PR slice tags differ from baseline")

    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        def ratchet(old, new, name):
            if old.get("blocking") and not new.get("blocking"):
                problems.append(f"ratchet {name}: blocking was removed")
            if old.get("no_significant_drop") and not new.get("no_significant_drop"):
                problems.append(f"ratchet {name}: no_significant_drop was removed")
            for key in ("min", "max", "max_increase"):
                if key not in old:
                    continue
                if key not in new or not finite(new[key]):
                    problems.append(f"ratchet {name}: threshold {key} removed or invalid")
                elif (key == "min" and new[key] < old[key]) or (key != "min" and new[key] > old[key]):
                    problems.append(f"ratchet {name}: threshold {key} loosened")

        current_metrics = {m["id"]: m for m in spec["metrics"]}
        for old in base_spec.get("metrics", []):
            mid = old["id"]
            if mid not in current_metrics:
                problems.append(f"ratchet: metric {mid} removed")
                continue
            new = current_metrics[mid]
            ratchet(old, new, mid)
            ratchet(old.get("threshold", {}), new.get("threshold", {}), mid)
        current_slices = {(s["name"], s["metric"]): s for s in spec.get("slices", [])}
        for old in base_spec.get("slices", []):
            key = (old["name"], old["metric"])
            if key not in current_slices:
                problems.append(f"ratchet: slice {key} removed")
            else:
                ratchet(old, current_slices[key], f"slice:{key[0]}/{key[1]}")

    # Do not trust a hand-edited green aggregate over failing row values.
    if not problems:
        for report, name in ((pr, "PR"), (base, "baseline")):
            # Minimal test/consumer reports need not carry cost when it is not
            # in the spec; aggregate() also computes that optional metric.
            rows = [{"cost": 0.0, **row} for row in report["rows"]]
            computed = aggregate(rows, sorted(graded), k_values=spec.get("pass_k", []))
            for metric in spec["metrics"]:
                mid = metric["id"]
                if mid in computed and (not finite(computed[mid]) or
                                        not math.isclose(report["metrics"][mid], computed[mid], abs_tol=1e-4)):
                    problems.append(f"{name}: aggregate {mid} differs from row values")
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
    for entry in spec.get("slices", []):
        name, metric = entry["name"], entry["metric"]
        sid = f"slice:{name}/{metric}"
        a = per_item(pr, metric, slice_name=name)
        val = sum(a.values()) / len(a) if a else None
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "min" in entry and val < entry["min"]:
            verdict = "fail"
        if entry.get("no_significant_drop") and val is not None:
            b = per_item(base, metric, slice_name=name)
            keys = sorted(set(a) & set(b))
            if keys:
                d, lo, hi = stats.paired_bootstrap(
                    [a[k] for k in keys], [b[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
                note = f"Delta {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
            else:
                verdict = "missing"
                note = "no paired items"
        if verdict != "ok" and entry.get("blocking"):
            blocked.append(sid)
        label = {"ok": "ok", "missing": "MISSING"}.get(
            verdict, "BLOCK" if entry.get("blocking") else "warn")
        lines.append(f"  {sid:<22} {val!s:<8} {json.dumps(entry):<40} {note:<28} {label}")
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
