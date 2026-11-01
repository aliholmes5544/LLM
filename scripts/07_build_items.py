#!/usr/bin/env python3
"""
07_build_items.py — step 07, item 1 (TASK_07 sections 0, 1, 7 and 8): the scoring item table.

Reads the 24 detector cells and the 3 baseline cells of results/raw/, asserts that every file has the sha256
and row count frozen in reports/integrity_check.json, joins each row with its item's partition, condition,
item class (phish_original, phish_variant, legit_core_neg, legit_ctrl_modern, legit_ctrl_para, gen_phish,
gen_legit), partition set (core / generalisation), cluster (the source e-mail id, identical for an original
and all its variants), source, subclass and body length, and writes
  results/scores/items.parquet   one row per prediction (27 x 5,207 = 140,589)
  results/scores/pairs.csv       one row per accepted variant: cluster, condition, variant_id, item_class
  reports/items_build_report.json  input hashes, output hashes, structural counts, versions.
No metric is computed: no prediction is compared with its label here (TASK_07 section 8, step 1).
--check rebuilds in memory and verifies that the parquet and csv on disk are byte-identical (reproducibility).

Usage: python scripts/07_build_items.py [--check]
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pyarrow

from common import ROOT, read_text, write_json
from detect.items import load_records, load_partitions
from scoring.items import build, write_outputs, load_jsonl, sha256_file

INTEGRITY = ROOT / "reports" / "integrity_check.json"
OUT_DIR = ROOT / "results" / "scores"
REPORT = ROOT / "reports" / "items_build_report.json"
VARIANTS = ROOT / "data" / "processed" / "variants_eval.jsonl"
EXPECTED_FILES, EXPECTED_ROWS = 27, 5207


def git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="rebuild and compare with the files on disk; write nothing")
    a = ap.parse_args()
    integrity = json.loads(read_text(INTEGRITY))
    if not integrity.get("all_pass"):
        raise SystemExit("reports/integrity_check.json does not report all_pass; run scripts/06_check_integrity.py first")
    recs, part = load_records(), load_partitions()
    variants = load_jsonl(VARIANTS)
    items, pairs, report = build(ROOT, integrity, recs, part, variants)
    if report["n_files"] != EXPECTED_FILES or report["n_items_per_cell"] != EXPECTED_ROWS:
        raise SystemExit(f"expected {EXPECTED_FILES} files x {EXPECTED_ROWS} items, got {report['n_files']} x {report['n_items_per_cell']}")

    if a.check:
        with tempfile.TemporaryDirectory() as td:
            fresh = write_outputs(items, pairs, Path(td))
        disk = {k: sha256_file(OUT_DIR / k) for k in fresh}
        same = fresh == disk
        print(f"rebuild {'IDENTICAL' if same else 'DIFFERS'}: {json.dumps({k: v[:16] for k, v in disk.items()})}")
        return 0 if same else 1

    hashes = write_outputs(items, pairs, OUT_DIR)
    report.update({"built_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "integrity_checked_at": integrity["checked_at"],
                   "variants_file_sha256": sha256_file(VARIANTS), "outputs": hashes,
                   "versions": {"pandas": pd.__version__, "pyarrow": pyarrow.__version__},
                   "git_commit": git("rev-parse", "--short", "HEAD"), "git_describe": git("describe", "--tags", "--always"),
                   "note": "No metric computed; label_true and label_pred are carried side by side for scripts/07_score.py."})
    write_json(REPORT, report)
    print(f"{report['n_files']} files verified against integrity_check.json; {report['n_rows']:,} rows "
          f"({report['n_items_per_cell']:,} items per cell); {report['n_clusters']:,} clusters")
    print("items by class:", report["items_by_class"])
    print("pairs by condition:", report["pairs_by_condition"])
    print(f"-> {OUT_DIR.relative_to(ROOT)}/items.parquet ({hashes['items.parquet'][:16]}), pairs.csv "
          f"({hashes['pairs.csv'][:16]}), {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
