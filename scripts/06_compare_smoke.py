#!/usr/bin/env python3
"""
06_compare_smoke.py — agreement between two smoke-test runs of the same dev sample on different backends
(Section 3.7, reproducibility across tiers; QUESTIONS.md item 11). For every (model, strategy) cell present
in both directories it reports the percentage of items with the same extracted label, the percentage with
byte-identical raw output, and lists the disagreements. Writes reports/smoke_backend_agreement.json.

Usage: python scripts/06_compare_smoke.py [--a results/smoke_dev] [--b results/smoke_gpu]
         [--out reports/smoke_backend_agreement.json]
"""
import argparse
import datetime as dt
import json
import sys

from common import ROOT, write_json, open_utf8


def load_dir(path) -> dict:
    """{model/strategy: {item_id: row}}"""
    cells = {}
    for f in sorted(path.glob("*/*.jsonl")):
        rows = [json.loads(l) for l in open_utf8(f) if l.strip()]
        cells[f"{f.parent.name}/{f.stem}"] = {r["item_id"]: r for r in rows}
    return cells


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="results/smoke_dev")
    ap.add_argument("--b", default="results/smoke_gpu")
    ap.add_argument("--out", default="reports/smoke_backend_agreement.json")
    a = ap.parse_args()
    A, B = load_dir(ROOT / a.a), load_dir(ROOT / a.b)
    common = sorted(set(A) & set(B))
    if not common:
        raise SystemExit(f"no common cells between {a.a} and {a.b}")
    out = {"a": a.a, "b": a.b, "compared_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "cells": {}}
    tot_n = tot_same = 0
    print(f"{'cell':28s} {'n':>3s} {'label agree':>12s} {'raw identical':>14s}  backends")
    for key in common:
        ra, rb = A[key], B[key]
        ids = sorted(set(ra) & set(rb))
        same = [i for i in ids if ra[i]["label_pred"] == rb[i]["label_pred"]]
        raw_same = [i for i in ids if ra[i]["raw_output"] == rb[i]["raw_output"]]
        dis = [{"item_id": i, "label_true": ra[i]["label_true"], "a": ra[i]["label_pred"], "b": rb[i]["label_pred"],
                "a_raw": ra[i]["raw_output"][:200], "b_raw": rb[i]["raw_output"][:200]} for i in ids if i not in same]
        same_hash = (next(iter(ra.values()))["prompt_hash"] == next(iter(rb.values()))["prompt_hash"] and
                     next(iter(ra.values()))["model_hash"] == next(iter(rb.values()))["model_hash"])
        cell = {"n": len(ids), "n_only_a": len(set(ra) - set(rb)), "n_only_b": len(set(rb) - set(ra)),
                "label_agreement_pct": round(100 * len(same) / len(ids), 1) if ids else None,
                "raw_identical_pct": round(100 * len(raw_same) / len(ids), 1) if ids else None,
                "same_prompt_and_model_hash": same_hash,
                "backend_a": next(iter(ra.values())).get("backend", "unrecorded"),
                "backend_b": next(iter(rb.values())).get("backend", "unrecorded"),
                "latency_median_a_s": round(sorted(r["latency_s"] for r in ra.values())[len(ra) // 2], 2),
                "latency_median_b_s": round(sorted(r["latency_s"] for r in rb.values())[len(rb) // 2], 2),
                "disagreements": dis}
        out["cells"][key] = cell
        tot_n += len(ids)
        tot_same += len(same)
        print(f"{key:28s} {len(ids):>3d} {cell['label_agreement_pct']:>11.1f}% {cell['raw_identical_pct']:>13.1f}%  "
              f"{cell['backend_a']} vs {cell['backend_b']}{'' if same_hash else '  HASHES DIFFER'}")
    out["overall_label_agreement_pct"] = round(100 * tot_same / tot_n, 1) if tot_n else None
    out["n_items_compared"] = tot_n
    write_json(ROOT / a.out, out)
    print(f"overall label agreement {out['overall_label_agreement_pct']}% over {tot_n} items -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
