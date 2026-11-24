#!/usr/bin/env python3
"""
07_precision_fpr.py — post hoc descriptive addition (QUESTIONS.md item 19, logged 2026-11-24 before this script
was run): precision and the false-positive rate, which RQ1 names and the frozen score files do not hold.

Reads the frozen item tables only (results/scores/items.parquet, hash asserted against reports/items_build_report.json;
the ensemble rows rebuilt by scoring.ensemble and asserted equal to results/scores/ensemble_predictions.csv; the
two-stage item tables results/scores/additional/twostage_<model>/items.parquet, hashes asserted against their scoring
reports) and writes NEW files only:
  results/scores/additional/precision_fpr/confusion_counts.csv   per cell, analysis and item group: n, predicted
                                                                 phishing, predicted legitimate, invalid, correct
  results/scores/additional/precision_fpr/precision_fpr.csv      precision on the core originals and on the
                                                                 generalisation set; FPR per legitimate group and
                                                                 pooled core legitimate; 95 % cluster-bootstrap CIs
  results/tables/tab_t13_precision_fpr.tex                       T13 in the style of T1 (recall and F1 read from the
                                                                 frozen metrics_long.csv)
  reports/precision_fpr_report.json                              input hashes, B, seed, commit, check results
Definitions (item 19): precision = TP / (TP + FP) with TP = phishing items labelled phishing and FP = legitimate items
labelled phishing (an invalid output is never a predicted phishing; NaN when TP + FP = 0); FPR = FP / n of the group.
Analyses primary (invalid = incorrect) and no_invalid (invalid dropped) exactly as scoring.score handles them.
Descriptive: no test, no p-value, no family. Checks: sensitivity, specificity and f1_phish recomputed from the
counts equal the stored values at the stored precision; (1 - specificity) - FPR equals the invalid rate of the
legitimate group. --check recomputes everything and compares the four output files byte for byte.

Usage: python scripts/07_precision_fpr.py [--check] [--B 2000]
"""
import argparse
import datetime as dt
import importlib
import json
import subprocess
import sys
import tempfile
import time
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd

from common import ROOT, load_config, read_text, write_json, write_text
from scoring.output import FLOAT_FORMAT, compare_outputs, sha256_file, write_csv
from scoring.score import CORE_GROUPS, GROUPS, annotate, cell_order, prepare
from scoring.stats import B_DEFAULT, point_and_ci, stat_rate

SCORES = ROOT / "results" / "scores"
OUT_DIR = SCORES / "additional" / "precision_fpr"
TABLES = ROOT / "results" / "tables"
REPORT = ROOT / "reports" / "precision_fpr_report.json"
ITEMS_REPORT = ROOT / "reports" / "items_build_report.json"
SCORING_REPORT = ROOT / "reports" / "scoring_report.json"
T13 = "tab_t13_precision_fpr.tex"
CSV_OUTPUTS = ("confusion_counts.csv", "precision_fpr.csv")
LEGIT_GROUPS = ["legit_core_neg", "legit_ctrl_modern", "legit_ctrl_para", "gen_legit"]
POOLED_LEGIT = "legit_core_pooled"                      # legit_core_neg + legit_ctrl_modern
GEN_GROUPS = ["gen_phish", "gen_legit"]
PRECISION_SETS = {"core_originals": (CORE_GROUPS, "core"), "generalisation": (GEN_GROUPS, "generalisation")}
ANALYSES = ["primary", "no_invalid"]
TWOSTAGE_PREFIX = "twostage_"
TWOSTAGE_STRATEGIES = ["lr_clean", "lr_all"]


def git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


# ---------------------------------------------------------------- statistics on summed counts

def stat_precision(s):
    """columns [tp, fp] -> tp / (tp + fp); NaN when no item is labelled phishing."""
    num, den = np.asarray(s[..., 0], dtype=float), np.asarray(s[..., 0] + s[..., 1], dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = num / den
    return np.where(den > 0, r, np.nan)


def cluster_counts(d: pd.DataFrame, cols: list) -> np.ndarray:
    if len(d) == 0:
        return np.zeros((0, len(cols)), dtype=np.int64)
    return d.groupby("cluster", sort=True)[cols].sum().to_numpy(dtype=np.int64)


def flags(d: pd.DataFrame) -> pd.DataFrame:
    """Add the 0/1 columns the counts are summed from: pred_phish, tp, fp, one."""
    d = d.copy()
    pos = d["label_true"] == "phish"
    pred_phish = d["label_pred"] == "phish"            # an invalid output is never a predicted phishing
    d["pred_phish"] = pred_phish.astype(int)
    d["pred_legit"] = (d["label_pred"] == "legit").astype(int)
    d["inv"] = d["invalid"].astype(int)
    d["corr"] = d["correct"].astype(int)
    d["tp"] = (pred_phish & pos).astype(int)
    d["fp"] = (pred_phish & ~pos).astype(int)
    d["one"] = 1
    return d


def analysis_frame(df: pd.DataFrame, analysis: str) -> pd.DataFrame:
    return flags(df[~df["invalid"]] if analysis == "no_invalid" else df)


# ---------------------------------------------------------------- per-cell tables

def confusion_rows(cell, d: pd.DataFrame, analysis: str) -> list:
    det, kind, strat = cell
    rows = []
    for grp in GROUPS:
        sub = d[d["group"] == grp]
        rows.append({"detector": det, "kind": kind, "strategy": strat, "analysis": analysis, "group": grp,
                     "n": int(len(sub)), "pred_phish": int(sub["pred_phish"].sum()), "pred_legit": int(sub["pred_legit"].sum()),
                     "invalid": int(sub["inv"].sum()), "correct": int(sub["corr"].sum())})
    return rows


def _row(cell, analysis, pset, condition, metric, sub, res, num, den):
    det, kind, strat = cell
    return {"detector": det, "kind": kind, "strategy": strat, "analysis": analysis, "partition_set": pset,
            "condition": condition, "metric": metric, "n": int(len(sub)), "n_clusters": int(sub["cluster"].nunique()),
            "num": int(num), "den": int(den), "value": res["value"], "ci_lo": res["ci_lo"], "ci_hi": res["ci_hi"]}


def metric_rows(cell, d: pd.DataFrame, analysis: str, seed: int, B: int) -> list:
    det, kind, strat = cell
    rows = []
    for cond, (groups, pset) in PRECISION_SETS.items():
        sub = d[d["group"].isin(groups)]
        counts = cluster_counts(sub, ["tp", "fp"])
        res = point_and_ci(counts, stat_precision, seed, f"{det}/{strat}/{analysis}/precision/{cond}", B)
        rows.append(_row(cell, analysis, pset, cond, "precision", sub, res, sub["tp"].sum(), sub["tp"].sum() + sub["fp"].sum()))
    for cond in LEGIT_GROUPS + [POOLED_LEGIT]:
        groups = ["legit_core_neg", "legit_ctrl_modern"] if cond == POOLED_LEGIT else [cond]
        sub = d[d["group"].isin(groups)]
        counts = cluster_counts(sub, ["fp", "one"])
        res = point_and_ci(counts, stat_rate, seed, f"{det}/{strat}/{analysis}/fpr/{cond}", B)
        pset = "generalisation" if cond.startswith("gen_") else "core"
        rows.append(_row(cell, analysis, pset, cond, "fpr", sub, res, sub["fp"].sum(), len(sub)))
    return rows


# ---------------------------------------------------------------- checks against the frozen metrics

def fmt(x) -> str:
    return "nan" if pd.isna(x) else FLOAT_FORMAT % x


def recomputed_metrics(cell, d: pd.DataFrame, analysis: str) -> list:
    """sens per phishing group, spec per legitimate group, f1_phish on the core originals, from the counts."""
    det, kind, strat = cell
    out = []
    for grp in GROUPS:
        sub = d[d["group"] == grp]
        if grp.startswith("gen_"):
            metric, cond = ("gen_sens", grp) if grp == "gen_phish" else ("gen_spec", grp)
        elif grp.startswith("phish_"):
            metric, cond = "sens", grp[len("phish_"):]
        else:
            metric, cond = "spec", {"legit_core_neg": "original_core_neg", "legit_ctrl_modern": "original_ctrl_modern",
                                    "legit_ctrl_para": "para_high_ctrl"}[grp]
        value = sub["corr"].sum() / len(sub) if len(sub) else np.nan
        out.append({"detector": det, "strategy": strat, "analysis": analysis, "metric": metric, "condition": cond, "value": value})
    core = d[d["group"].isin(CORE_GROUPS)]
    tp, fp = core["tp"].sum(), core["fp"].sum()
    fn = ((core["label_true"] == "phish") & (core["pred_phish"] == 0)).sum()
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else np.nan
    out.append({"detector": det, "strategy": strat, "analysis": analysis, "metric": "f1_phish", "condition": "core_originals", "value": f1})
    return out


def compare_with_stored(recomputed: list, stored: pd.DataFrame) -> dict:
    """Every recomputed value must equal the stored value at the stored precision (%.6g)."""
    S = stored.set_index(["detector", "strategy", "analysis", "metric", "condition"])["value"]
    mismatches, n = [], 0
    for r in recomputed:
        key = (r["detector"], r["strategy"], r["analysis"], r["metric"], r["condition"])
        if key not in S.index:
            mismatches.append({"key": "/".join(key), "reason": "not in stored metrics"})
            continue
        n += 1
        if fmt(S.at[key]) != fmt(r["value"]):
            mismatches.append({"key": "/".join(key), "stored": fmt(S.at[key]), "recomputed": fmt(r["value"])})
    return {"n_compared": n, "n_mismatch": len(mismatches), "mismatches": mismatches}


def fpr_identity(conf: pd.DataFrame, pf: pd.DataFrame, stored_primary: pd.DataFrame) -> dict:
    """(1 - spec) - fpr == invalid rate of the legitimate group: exact on the counts ((n - correct) - fp == invalid),
    and at the stored precision against the invalid_rate rows of the frozen metrics (primary analysis only)."""
    S = stored_primary.set_index(["detector", "strategy", "metric", "condition"])["value"]
    exact_fail, stored_fail, n_exact, n_stored, max_dev = [], [], 0, 0, 0.0
    pfi = pf.set_index(["detector", "strategy", "analysis", "metric", "condition"])
    for _, r in conf[conf["group"].isin(LEGIT_GROUPS)].iterrows():
        n, correct, invalid = int(r["n"]), int(r["correct"]), int(r["invalid"])
        fp = n - correct - invalid                                      # legit items labelled phishing
        row = pfi.loc[(r["detector"], r["strategy"], r["analysis"], "fpr", r["group"])]
        n_exact += 1
        # exact, on the counts: (n - correct) - fp == invalid, and the FPR row holds exactly fp / n
        if int(row["num"]) != fp or int(row["den"]) != n or (n - correct) - fp != invalid:
            exact_fail.append(f"{r['detector']}/{r['strategy']}/{r['analysis']}/{r['group']}")
        if n:
            # in floating point, with the unrounded specificity and the written FPR value
            max_dev = max(max_dev, abs((1 - correct / n) - float(row["value"]) - invalid / n))
        if r["analysis"] == "primary":
            key = (r["detector"], r["strategy"], "invalid_rate", r["group"])
            if key in S.index:
                n_stored += 1
                lhs = Fraction(n - correct, n) - Fraction(fp, n) if n else np.nan   # exact (1 - spec) - fpr
                if fmt(float(lhs)) != fmt(S.at[key]):
                    stored_fail.append({"key": "/".join(key), "lhs": fmt(float(lhs)), "invalid_rate": fmt(S.at[key])})
    return {"exact_count_identity": {"n": n_exact, "n_fail": len(exact_fail), "failures": exact_fail,
                                     "float_max_abs_deviation": max_dev},
            "against_stored_invalid_rate": {"n": n_stored, "n_fail": len(stored_fail), "failures": stored_fail,
                                            "note": "(1 - spec) - FPR computed exactly on the counts, compared with the stored "
                                                    "invalid_rate at the stored precision (%.6g); primary analysis"}}


# ---------------------------------------------------------------- table T13

def t13(pf: pd.DataFrame, metrics: pd.DataFrame) -> str:
    tf = importlib.import_module("07_tables_figures")
    P = pf[pf["analysis"] == "primary"].set_index(["detector", "strategy", "metric", "condition"])
    M = metrics[metrics["analysis"] == "primary"].set_index(["detector", "strategy", "metric", "condition"])

    def c(T, det, s, metric, cond):
        r = T.loc[(det, s, metric, cond)]
        return tf.ci(r["value"], r["ci_lo"], r["ci_hi"])

    rows = []
    for det, s in tf.ref_cells():
        rows.append([tf.NAME[det], tf.STRAT[s], c(P, det, s, "precision", "core_originals"), c(M, det, s, "sens", "original"),
                     c(M, det, s, "f1_phish", "core_originals"), c(P, det, s, "fpr", "legit_core_neg"), c(P, det, s, "fpr", "legit_ctrl_modern")])
    header = ["Detector", "Strategy", "Precision [95% CI]", "Recall [95% CI]", "F1 (phishing) [95% CI]",
              "FPR core (1,002) [95% CI]", "FPR modern (334) [95% CI]"]
    groups = [("Language models, zero-shot", 6), ("Ensemble", 1), ("Supervised baselines", 3)]
    return tf.tex_table(header, rows, "lllllll", groups)


# ---------------------------------------------------------------- inputs and run

def verify_inputs(cfg_models: list) -> dict:
    items_rep = json.loads(read_text(ITEMS_REPORT))
    scoring_rep = json.loads(read_text(SCORING_REPORT))
    hashes = {}
    sha = sha256_file(SCORES / "items.parquet")
    if sha != items_rep["outputs"]["items.parquet"]:
        raise SystemExit("results/scores/items.parquet differs from reports/items_build_report.json")
    hashes["results/scores/items.parquet"] = sha
    for name in ("ensemble_predictions.csv", "metrics_long.csv"):
        sha = sha256_file(SCORES / name)
        if sha != scoring_rep["outputs"][name]:
            raise SystemExit(f"results/scores/{name} differs from reports/scoring_report.json")
        hashes[f"results/scores/{name}"] = sha
    for m in cfg_models:
        rep = json.loads(read_text(ROOT / "reports" / f"scoring_additional_{TWOSTAGE_PREFIX}{m}.json"))
        d = SCORES / "additional" / f"{TWOSTAGE_PREFIX}{m}"
        for name in ("items.parquet", "metrics_long.csv"):
            sha = sha256_file(d / name)
            if sha != rep["outputs"][name]:
                raise SystemExit(f"{d.relative_to(ROOT)}/{name} differs from its scoring report")
            hashes[str((d / name).relative_to(ROOT))] = sha
    return hashes


def assert_ensemble_equal(items: pd.DataFrame) -> int:
    """The rebuilt ensemble rows must equal the frozen ensemble_predictions.csv (label and invalid flag)."""
    ens = items[items["kind"] == "ensemble"][["strategy", "item_id", "label_pred", "invalid"]]
    frozen = pd.read_csv(SCORES / "ensemble_predictions.csv", dtype={"label_pred": str})
    merged = ens.merge(frozen[["strategy", "item_id", "label_pred", "invalid"]], on=["strategy", "item_id"], how="outer",
                       suffixes=("", "_frozen"), indicator=True)
    bad = (merged["_merge"] != "both") | (merged["label_pred"] != merged["label_pred_frozen"]) | \
          (merged["invalid"].astype(bool) != merged["invalid_frozen"].astype(bool))
    if bad.any():
        raise SystemExit(f"rebuilt ensemble differs from ensemble_predictions.csv in {int(bad.sum())} rows")
    return int(len(merged))


def load_cells(cfg_models: list):
    """{(detector, kind, strategy): annotated frame} in report order: 31 main cells, then the 6 two-stage cells."""
    items = prepare(pd.read_parquet(SCORES / "items.parquet"))
    n_ens = assert_ensemble_equal(items)
    order = cell_order(items)
    cells = {}
    for det, kind, strat in order:
        cells[(det, kind, strat)] = items[(items["detector"] == det) & (items["strategy"] == strat)]
    stored = [pd.read_csv(SCORES / "metrics_long.csv")]
    for m in cfg_models:
        det = TWOSTAGE_PREFIX + m
        ts = annotate(pd.read_parquet(SCORES / "additional" / det / "items.parquet"))
        for strat in TWOSTAGE_STRATEGIES:
            cells[(det, "twostage", strat)] = ts[(ts["detector"] == det) & (ts["strategy"] == strat)]
        stored.append(pd.read_csv(SCORES / "additional" / det / "metrics_long.csv"))
    return cells, pd.concat(stored, ignore_index=True), n_ens


def run(cells: dict, stored: pd.DataFrame, seed: int, B: int, log=print) -> dict:
    conf, pf, recomputed = [], [], []
    for analysis in ANALYSES:
        for cell, df in cells.items():
            d = analysis_frame(df, analysis)
            conf += confusion_rows(cell, d, analysis)
            pf += metric_rows(cell, d, analysis, seed, B)
            recomputed += recomputed_metrics(cell, d, analysis)
            log(f"  {analysis:<10} {cell[0]}/{cell[2]}")
    conf, pf = pd.DataFrame(conf), pd.DataFrame(pf)
    checks = {"stored_metrics": compare_with_stored(recomputed, stored),
              "fpr_identity": fpr_identity(conf, pf, stored[stored["analysis"] == "primary"])}
    undefined = pf[(pf["metric"] == "precision") & pf["value"].isna()]
    checks["precision_undefined_cells"] = [f"{r.detector}/{r.strategy}/{r.analysis}/{r.condition}" for r in undefined.itertuples()]
    tex = t13(pf, stored)
    return {"confusion_counts": conf, "precision_fpr": pf, "tex": tex, "checks": checks}


def write_all(res: dict, out_dir: Path, tables_dir: Path) -> dict:
    hashes = {name: write_csv(res[name[:-4]], out_dir / name) for name in CSV_OUTPUTS}
    tables_dir.mkdir(parents=True, exist_ok=True)
    write_text(tables_dir / T13, res["tex"])
    hashes[T13] = sha256_file(tables_dir / T13)
    return hashes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="recompute and compare the output files byte for byte; write nothing")
    ap.add_argument("--B", type=int, default=B_DEFAULT)
    a = ap.parse_args()
    seed = load_config("data.yaml")["seed"]
    cfg_models = load_config("twostage.yaml")["models"]
    t0 = time.time()
    in_hashes = verify_inputs(cfg_models)
    cells, stored, n_ens = load_cells(cfg_models)
    res = run(cells, stored, seed, a.B, log=lambda s: print(s, flush=True))
    runtime = time.time() - t0
    ch = res["checks"]
    ok_checks = ch["stored_metrics"]["n_mismatch"] == 0 and ch["fpr_identity"]["exact_count_identity"]["n_fail"] == 0 \
        and ch["fpr_identity"]["against_stored_invalid_rate"]["n_fail"] == 0 \
        and ch["fpr_identity"]["exact_count_identity"]["float_max_abs_deviation"] < 1e-9
    print(f"checks: stored metrics compared {ch['stored_metrics']['n_compared']}, mismatches {ch['stored_metrics']['n_mismatch']}; "
          f"FPR identity exact {ch['fpr_identity']['exact_count_identity']['n']} rows, failures "
          f"{ch['fpr_identity']['exact_count_identity']['n_fail']}; against stored invalid_rate "
          f"{ch['fpr_identity']['against_stored_invalid_rate']['n']} rows, failures "
          f"{ch['fpr_identity']['against_stored_invalid_rate']['n_fail']}; precision undefined in "
          f"{len(ch['precision_undefined_cells'])} cells")
    if a.check:
        with tempfile.TemporaryDirectory() as td:
            fresh = write_all(res, Path(td), Path(td))
        cmp = {**compare_outputs({k: v for k, v in fresh.items() if k != T13}, OUT_DIR),
               **compare_outputs({T13: fresh[T13]}, TABLES)}
        ok = all(v == "identical" for v in cmp.values())
        print(f"re-run {'IDENTICAL' if ok else 'DIFFERS'}: {cmp} ({runtime:.0f} s)")
        return 0 if ok and ok_checks else 1
    if not ok_checks:
        print("a check failed; nothing written", file=sys.stderr)
        return 1
    out_hashes = write_all(res, OUT_DIR, TABLES)
    report = {"computed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "note": "Post hoc descriptive addition (QUESTIONS.md item 19, logged 2026-11-24 before this computation): "
                      "precision and the false-positive rate; no test, no family; frozen files unchanged.",
              "inputs": in_hashes, "ensemble_rows_checked_against_ensemble_predictions.csv": n_ens,
              "cells": [f"{d}/{s}" for d, _, s in cells], "n_cells": len(cells), "analyses": ANALYSES,
              "B": a.B, "seed": seed, "definitions": {
                  "precision": "TP / (TP + FP); TP = phishing items labelled phishing, FP = legitimate items labelled phishing; "
                               "an invalid output is never a predicted phishing; NaN when TP + FP = 0",
                  "precision_sets": {k: v[0] for k, v in PRECISION_SETS.items()},
                  "fpr": "FP / n of the legitimate group in the analysis", "fpr_groups": LEGIT_GROUPS + [POOLED_LEGIT],
                  "pooled": ["legit_core_neg", "legit_ctrl_modern"]},
              "checks": ch, "rows": {k: int(len(res[k])) for k in ("confusion_counts", "precision_fpr")},
              "outputs": {**{f"results/scores/additional/precision_fpr/{k}": v for k, v in out_hashes.items() if k != T13},
                          f"results/tables/{T13}": out_hashes[T13]},
              "runtime_s": round(runtime, 1),
              "versions": {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__},
              "git_commit": git("rev-parse", "--short", "HEAD"), "git_describe": git("describe", "--tags", "--always")}
    write_json(REPORT, report)
    print(f"{len(cells)} cells x 2 analyses; rows {report['rows']}; runtime {runtime:.0f} s -> "
          f"{', '.join(f'{k.split('/')[-1]} {v[:12]}' for k, v in report['outputs'].items())}; {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
