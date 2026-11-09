#!/usr/bin/env python3
"""
07_score_model.py — SpearShift: score one additional detector model after `make evaluate MODEL=<key>`
(README, "Adding a new model"; Chapter 3 Section 3.7, the framework as a contribution).

The six pre-registered models, the majority ensemble, the pre-registered test families (F-RQ4, F-RQ2, F-RQ3,
S-*) and every file written by scripts/07_score.py are frozen (QUESTIONS.md item 12: the scores were computed
once). This script therefore writes separate files for the additional model and never touches results/scores/
metrics_long.csv, deltas_long.csv, contrasts.csv or ensemble_predictions.csv; tests/test_score_model.py checks
that scoring a model alone reproduces its frozen rows and that the frozen files keep their recorded hashes.

Inputs (all hash-verified)
  results/raw/<key>/<strategy>/eval.jsonl   the model's four evaluation cells, sha256 and row counts taken from
                                             the integrity report written for the model
                                             (06_check_integrity.py --models <key> --baselines none --report ...)
  results/scores/pairs.csv                   the pairing table of step 1 (reports/items_build_report.json)
  data/processed/variants_eval.jsonl         the fixed variants artefact (reports/variants_eval_fixed_artifacts.json)
Outputs
  results/scores/additional/<key>/items.parquet      the model's rows in the item-table schema (no metric)
  results/scores/additional/<key>/metrics_long.csv   same columns and functions as 07_score.py: cluster bootstrap,
  results/scores/additional/<key>/deltas_long.csv    B = 2000, seed from configs/data.yaml, per-table random streams,
                                                     exact McNemar; Holm within the model's own families
                                                     A-<key> (zero_shot) and A-<key>-<strategy> (other strategies)
  reports/scoring_additional_<key>.json              inputs, families, output hashes, runtime, versions
Not produced for an additional model: ensemble rows, F-RQ2 / F-RQ3 contrasts, LaTeX tables and figures; the
model is reported as a post-registration addition next to the frozen tables.
--check recomputes everything into a temporary directory and compares the CSVs byte for byte with disk.

Usage: python scripts/07_score_model.py --model <key> [--integrity reports/integrity_check_<key>.json]
                                        [--out-dir results/scores/additional/<key>] [--check] [--B 2000]
                                        [--strategies zero_shot,few_shot,cot,role] [--kind llm|twostage]
--kind twostage (TASK_08, QUESTIONS.md item 18c): the two-stage detector twostage_<key> with its single strategy
`lr`, read from reports/integrity_check_twostage.json, written to results/scores/additional/twostage_<key>/ with
the families A-twostage-<key>; the frozen files and the six models' rows are untouched.
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

from common import ROOT, load_config, read_text, write_json
from detect.items import load_records, load_partitions
from scoring.items import COLUMNS, file_rows, item_meta, load_jsonl, sha256_file, verify_file
from scoring.output import compare_outputs, write_csv
from scoring.score import STRATEGIES, annotate, apply_holm, cell_deltas, cell_metrics
from scoring.stats import B_DEFAULT

SCORES = ROOT / "results" / "scores"
ITEMS_REPORT = ROOT / "reports" / "items_build_report.json"
FIXED = ROOT / "reports" / "variants_eval_fixed_artifacts.json"
VARIANTS = ROOT / "data" / "processed" / "variants_eval.jsonl"
OUTPUTS = ("metrics_long.csv", "deltas_long.csv")


def git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


TWOSTAGE_PREFIX, TWOSTAGE_STRATEGIES = "twostage_", ["lr"]


def family_for(model: str, strategy: str, kind: str = "llm") -> str:
    """The additional detector's own families: a language model gets A-<key> for zero_shot and A-<key>-<strategy>
    otherwise; the two-stage detector gets A-twostage-<key> (TASK_08 section 7)."""
    if kind == "twostage":
        return f"A-twostage-{model[len(TWOSTAGE_PREFIX):] if model.startswith(TWOSTAGE_PREFIX) else model}"
    return f"A-{model}" if strategy == "zero_shot" else f"A-{model}-{strategy}"


def model_specs(integrity: dict, model: str, strategies: list = None, kind: str = "llm") -> list:
    """File specs of the detector's cells from an integrity report; every cell must be present and pass."""
    strategies = strategies or STRATEGIES
    specs = []
    for key, c in integrity.get("cells", {}).items():
        if c["model"] != model:
            continue
        if not c.get("pass"):
            raise SystemExit(f"{key}: the integrity report marks this cell as failed; fix the run first")
        specs.append({"file": c["file"], "sha256": c["file_sha256"], "n_rows": c["n_rows"], "detector": model,
                      "kind": kind, "strategy": c["strategy"]})
    have = {s["strategy"] for s in specs}
    if have != set(strategies):
        raise SystemExit(f"integrity report has cells {sorted(have)} for {model}; need {strategies}")
    return sorted(specs, key=lambda s: strategies.index(s["strategy"]))


def build_model_items(root: Path, integrity: dict, model: str, recs: dict, part: dict, variants: list,
                      strategies: list = None, kind: str = "llm") -> pd.DataFrame:
    """The detector's rows in the step-1 item-table schema (scoring.items.build for one detector)."""
    specs = model_specs(integrity, model, strategies, kind)
    for spec in specs:
        verify_file(root, spec)
    meta = item_meta(recs, part, variants)
    rows = []
    for spec in specs:
        fr = file_rows(root, spec, meta)
        if {r["item_id"] for r in fr} != set(meta):
            raise SystemExit(f"{spec['file']}: item set differs from the expected evaluation item set")
        rows.extend(fr)
    items = pd.DataFrame(rows, columns=COLUMNS).sort_values(["kind", "detector", "strategy", "item_id"]).reset_index(drop=True)
    items["score"] = items["score"].astype("float64")
    return items


def score_model(items: pd.DataFrame, pairs: pd.DataFrame, model: str, seed: int, B: int = B_DEFAULT, log=print,
                strategies: list = None, kind: str = "llm") -> dict:
    """metrics_long and deltas_long for one detector: the functions of scoring.score, cell by cell, both analyses."""
    strategies = strategies or STRATEGIES
    items = annotate(items[(items["detector"] == model) & (items["kind"] == kind)])
    metrics, deltas = [], []
    for analysis in ("primary", "no_invalid"):
        for strat in strategies:
            cell = (model, kind, strat)
            d = items[items["strategy"] == strat].set_index("item_id", drop=False)
            if len(d) == 0:
                raise SystemExit(f"no rows for {model}/{strat}")
            metrics += cell_metrics(cell, d, analysis, seed, B)
            for row in cell_deltas(cell, d, pairs, analysis, seed, B):
                row["family"] = family_for(model, strat, kind)
                deltas.append(row)
            log(f"  {analysis:<10} {model}/{strat}")
    metrics = pd.DataFrame(metrics)
    deltas = apply_holm(pd.DataFrame(deltas), "mcnemar_p", ["analysis", "family"])
    fams = deltas[deltas["analysis"] == "primary"].groupby("family").size().to_dict()
    return {"metrics_long": metrics, "deltas_long": deltas, "families": {k: int(v) for k, v in sorted(fams.items())}}


def write_all(res: dict, out_dir: Path) -> dict:
    return {name: write_csv(res[name[:-4]], out_dir / name) for name in OUTPUTS}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="key in configs/models.yaml")
    ap.add_argument("--integrity", default=None, help="integrity report with the model's cells; default reports/integrity_check_<key>.json")
    ap.add_argument("--out-dir", default=None, help="default results/scores/additional/<key>")
    ap.add_argument("--check", action="store_true", help="recompute and compare with the CSVs on disk; write nothing")
    ap.add_argument("--B", type=int, default=B_DEFAULT)
    ap.add_argument("--strategies", default=None, help="comma list; default the four prompting strategies (llm) or lr (twostage)")
    ap.add_argument("--kind", default="llm", choices=("llm", "twostage"), help="twostage: the TASK_08 detector twostage_<key>")
    a = ap.parse_args()
    mcfg = load_config("models.yaml")
    if a.model not in mcfg["models"]:
        raise SystemExit(f"unknown model {a.model}; keys: {list(mcfg['models'])}")
    if a.kind == "twostage" and a.model not in load_config("twostage.yaml")["models"]:
        raise SystemExit(f"{a.model} is not one of the three two-stage models (configs/twostage.yaml)")
    detector = TWOSTAGE_PREFIX + a.model if a.kind == "twostage" else a.model
    strategies = a.strategies.split(",") if a.strategies else (TWOSTAGE_STRATEGIES if a.kind == "twostage" else STRATEGIES)
    seed = load_config("data.yaml")["seed"]
    integrity_path = ROOT / (a.integrity or ("reports/integrity_check_twostage.json" if a.kind == "twostage" else f"reports/integrity_check_{a.model}.json"))
    out_dir = ROOT / (a.out_dir or f"results/scores/additional/{detector}")
    report_path = ROOT / "reports" / f"scoring_additional_{detector}.json"
    t0 = time.time()

    if not integrity_path.exists():
        raise SystemExit(f"{integrity_path.relative_to(ROOT)} not found; run scripts/06_check_integrity.py --models "
                         f"{a.model} --baselines none --report {integrity_path.relative_to(ROOT)} first")
    integrity = json.loads(read_text(integrity_path))
    items_rep = json.loads(read_text(ITEMS_REPORT))
    pairs_sha = sha256_file(SCORES / "pairs.csv")
    if pairs_sha != items_rep["outputs"]["pairs.csv"]:
        raise SystemExit("results/scores/pairs.csv differs from reports/items_build_report.json")
    fixed = json.loads(read_text(FIXED))["files"]["data/processed/variants_eval.jsonl"]["sha256"]
    var_sha = sha256_file(VARIANTS)
    if var_sha != fixed:
        raise SystemExit("data/processed/variants_eval.jsonl differs from the fixed artefact hash")
    recs, part = load_records(), load_partitions()
    items = build_model_items(ROOT, integrity, detector, recs, part, load_jsonl(VARIANTS), strategies, a.kind)
    pairs = pd.read_csv(SCORES / "pairs.csv")
    res = score_model(items, pairs, detector, seed, a.B, log=lambda s: print(s, flush=True), strategies=strategies, kind=a.kind)
    runtime = time.time() - t0

    if a.check:
        with tempfile.TemporaryDirectory() as td:
            fresh = write_all(res, Path(td))
        cmp = compare_outputs(fresh, out_dir)
        ok = all(v == "identical" for v in cmp.values())
        print(f"re-run {'IDENTICAL' if ok else 'DIFFERS'}: {cmp} ({runtime:.0f} s)")
        return 0 if ok else 1

    out_dir.mkdir(parents=True, exist_ok=True)
    items.to_parquet(out_dir / "items.parquet", engine="pyarrow", index=False, compression="snappy")
    hashes = {"items.parquet": sha256_file(out_dir / "items.parquet"), **write_all(res, out_dir)}
    report = {"computed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "model": a.model,
              "detector": detector, "kind": a.kind, "strategies": strategies,
              "note": "Additional detector scored after the pre-registered computation (07_score.py); not part of the "
                      "ensemble, the pre-registered families, the tables or the figures.",
              "inputs": {"integrity_report": str(integrity_path.relative_to(ROOT)),
                         "cells": {s["strategy"]: {"file": s["file"], "sha256": s["sha256"], "n_rows": s["n_rows"]}
                                   for s in model_specs(integrity, detector, strategies, a.kind)},
                         "pairs.csv": pairs_sha, "variants_eval.jsonl": var_sha},
              "B": a.B, "seed": seed, "families": res["families"], "analyses": ["primary", "no_invalid"],
              "rows": {k: int(len(res[k])) for k in ("metrics_long", "deltas_long")},
              "out_dir": str(out_dir.relative_to(ROOT)) if out_dir.is_relative_to(ROOT) else str(out_dir),
              "outputs": hashes, "runtime_s": round(runtime, 1),
              "versions": {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__},
              "git_commit": git("rev-parse", "--short", "HEAD"), "git_describe": git("describe", "--tags", "--always")}
    write_json(report_path, report)
    print(f"{detector}: {report['rows']}; families {res['families']}; runtime {runtime:.0f} s -> {report['out_dir']}, "
          f"{report_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
