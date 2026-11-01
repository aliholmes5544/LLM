#!/usr/bin/env python3
"""
07_score.py — step 07, step 3 (TASK_07 sections 2, 3 and 8): the primary tables and inference. The first and
only computation of the evaluation scores (QUESTIONS.md item 12, refinements 1 to 7; items 15 and 16).

Reads results/scores/items.parquet and results/scores/pairs.csv (hashes asserted against
reports/items_build_report.json), adds the majority-vote ensemble (item 12a) as a seventh detector, and writes
  results/scores/metrics_long.csv      rates with 95% cluster-bootstrap CIs (primary and no_invalid analyses)
  results/scores/deltas_long.csv       paired deltas, exact McNemar p, Holm p within family
  results/scores/contrasts.csv         F-RQ2 size and F-RQ3 strategy contrasts (bootstrap p, Holm p)
  results/scores/ensemble_predictions.csv
  reports/scoring_report.json          inputs, families, power note, output hashes, runtime, versions.
--check recomputes everything into a temporary directory and compares the CSVs byte for byte with disk.

Usage: python scripts/07_score.py [--check] [--B 2000]
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
from scoring.output import compare_outputs, sha256_file, write_csv
from scoring.score import run
from scoring.stats import B_DEFAULT

SCORES = ROOT / "results" / "scores"
ITEMS_REPORT = ROOT / "reports" / "items_build_report.json"
REPORT = ROOT / "reports" / "scoring_report.json"
OUTPUTS = ("metrics_long.csv", "deltas_long.csv", "contrasts.csv", "ensemble_predictions.csv")


def git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def verify_inputs() -> dict:
    rep = json.loads(read_text(ITEMS_REPORT))
    hashes = {}
    for name in ("items.parquet", "pairs.csv"):
        sha = sha256_file(SCORES / name)
        if sha != rep["outputs"][name]:
            raise SystemExit(f"{name}: sha256 {sha[:16]} differs from items_build_report.json {rep['outputs'][name][:16]}")
        hashes[name] = sha
    return hashes


def write_all(res: dict, out_dir: Path) -> dict:
    return {name: write_csv(res[name[:-4]], out_dir / name) for name in OUTPUTS}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="recompute and compare with the CSVs on disk; write nothing")
    ap.add_argument("--B", type=int, default=B_DEFAULT)
    a = ap.parse_args()
    seed = load_config("data.yaml")["seed"]
    t0 = time.time()
    in_hashes = verify_inputs()
    items = pd.read_parquet(SCORES / "items.parquet")
    pairs = pd.read_csv(SCORES / "pairs.csv")
    res = run(items, pairs, seed, a.B, log=lambda s: print(s, flush=True))
    runtime = time.time() - t0
    if a.check:
        with tempfile.TemporaryDirectory() as td:
            fresh = write_all(res, Path(td))
        cmp = compare_outputs(fresh, SCORES)
        ok = all(v == "identical" for v in cmp.values())
        print(f"re-run {'IDENTICAL' if ok else 'DIFFERS'}: {cmp} ({runtime:.0f} s)")
        return 0 if ok else 1
    out_hashes = write_all(res, SCORES)
    info = res["info"]
    report = {"computed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "note": "First and only computation of the evaluation scores (TASK_07 step 3); plan in QUESTIONS.md item 12.",
              "inputs": in_hashes, "items_build_report_built_at": json.loads(read_text(ITEMS_REPORT))["built_at"],
              **{k: v for k, v in info.items()}, "analyses": ["primary", "no_invalid"],
              "rows": {k: int(len(res[k])) for k in ("metrics_long", "deltas_long", "contrasts", "ensemble_predictions")},
              "outputs": out_hashes, "runtime_s": round(runtime, 1),
              "versions": {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__},
              "git_commit": git("rev-parse", "--short", "HEAD"), "git_describe": git("describe", "--tags", "--always")}
    write_json(REPORT, report)
    print(f"{info['n_cells']} cells x 2 analyses; rows: {report['rows']}; families {info['families']}")
    print(f"power note: {info['power_note']}; observed discordance F-RQ4: {info['observed_discordance_F_RQ4']}")
    print(f"runtime {runtime:.0f} s -> {', '.join(f'{k} {v[:12]}' for k, v in out_hashes.items())}; {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
