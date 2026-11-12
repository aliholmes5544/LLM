#!/usr/bin/env python3
"""
07_twostage_compare.py — TASK_08 section 7: the primary comparison of the two-stage indicator detector with the direct
zero-shot verdict of the same model (QUESTIONS.md item 18; exploratory, post hoc; Chapter 4 Section 4.5).

For each of the three extraction models and each stage-2 fit of configs/twostage.yaml (`lr_clean`, fitted on the dev
originals only, the primary; `lr_all`, fitted on all dev items, attack-aware) the script computes
  contrasts.csv         the difference of robustness deltas, two-stage minus direct, per condition (the four phishing
                        variant conditions and the paraphrased legitimate control) on the same pairs, as the cluster
                        bootstrap difference of scoring.stats.stat_contrast (B = 2000, seed from configs/data.yaml, one
                        random stream per table) with the 95 % percentile CI, the two-sided bootstrap p of item 12
                        refinement 2 and Holm within the fit's family (A-twostage-<model>-clean or -all, five tests).
                        Both analyses: primary (invalid = incorrect) and no_invalid (a pair is dropped when either member
                        of either arm is invalid). Positive: the rewrite costs the two-stage detector more (or benefits it less) than the direct verdict; negative: less.
  rate_differences.csv  descriptive, primary analysis: two-stage minus direct on the same items for every rate of
                        metrics_long (sensitivity per condition, specificity per legitimate set, generalisation
                        sensitivity and specificity, accuracy and balanced accuracy on the core originals), with the
                        cluster-bootstrap CI and no test (not pre-registered).
  disagreement.csv      descriptive: items on which the two pipelines give different labels, by item group, with the
                        counts of items only the direct verdict or only the two-stage detector gets right.
Inputs are hash-verified: results/scores/items.parquet (frozen; reports/items_build_report.json), the two-stage item
tables results/scores/additional/twostage_<model>/items.parquet (reports/scoring_additional_twostage_<model>.json) and
results/scores/pairs.csv. No frozen CSV is written or re-computed.
Outputs: results/scores/additional/twostage_compare/{contrasts,rate_differences,disagreement}.csv and
reports/twostage_compare_report.json (inputs, families, output hashes, the three largest stage-2 coefficients per fit,
runtime, versions). --check recomputes into a temporary directory and compares the CSVs byte for byte with disk.

Usage: python scripts/07_twostage_compare.py [--check] [--B 2000]
"""
import argparse
import datetime as dt
import importlib
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
from scoring.score import (ANALYSES, CONTROL, CORE_GROUPS, GROUPS, PHISH_CONDITIONS, RATE_METRICS, annotate, apply_holm,
                           cluster_counts, paired_arrays)
from scoring.stats import B_DEFAULT, bootstrap_p, point_and_ci, stat_contrast

SCORES = ROOT / "results" / "scores"
ADDITIONAL = SCORES / "additional"
OUT_DIR = ADDITIONAL / "twostage_compare"
REPORT = ROOT / "reports" / "twostage_compare_report.json"
TWOSTAGE_REPORT = ROOT / "reports" / "twostage_report.json"
ITEMS_REPORT = ROOT / "reports" / "items_build_report.json"
OUTPUTS = ("contrasts.csv", "rate_differences.csv", "disagreement.csv")
DIRECT = "zero_shot"
CONDITIONS = PHISH_CONDITIONS + [CONTROL]
DIFF_METRICS = [(metric, cond, grp) for metric, cond, grp, _ in RATE_METRICS]      # same rows as metrics_long

score_model = importlib.import_module("07_score_model")
TWOSTAGE_PREFIX, family_for = score_model.TWOSTAGE_PREFIX, score_model.family_for


def git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


# ---------------------------------------------------------------- statistics on summed counts

def stat_rate_diff(s):
    """columns [correct_a, correct_b, n] -> rate_b - rate_a (two-stage minus direct on the same items)"""
    with np.errstate(invalid="ignore", divide="ignore"):
        r = (s[..., 1] - s[..., 0]) / s[..., 2]
    return np.where(s[..., 2] > 0, r, np.nan)


def stat_bal_acc_diff(s):
    """columns [cp_a, cn_a, cp_b, cn_b, n_pos, n_neg] -> balanced accuracy of b minus balanced accuracy of a"""
    with np.errstate(invalid="ignore", divide="ignore"):
        a = 0.5 * (s[..., 0] / s[..., 4] + s[..., 1] / s[..., 5])
        b = 0.5 * (s[..., 2] / s[..., 4] + s[..., 3] / s[..., 5])
    return np.where((s[..., 4] > 0) & (s[..., 5] > 0), b - a, np.nan)


# ---------------------------------------------------------------- inputs

def fits_of(tcfg: dict) -> list:
    """[(fit_key, strategy_key, primary)] in config order, the primary fit first."""
    fits = [(k, v["strategy_key"], bool(v.get("primary"))) for k, v in tcfg["fits"].items()]
    return sorted(fits, key=lambda f: (not f[2], [k for k in tcfg["fits"]].index(f[0])))


def load_cells(tcfg: dict) -> tuple:
    """{(detector, strategy): items indexed by item_id} for the direct zero-shot cells of the three models and the
    two-stage cells of both fits, every input file verified against its recorded sha256; plus the input record."""
    inputs = {}
    items_rep = json.loads(read_text(ITEMS_REPORT))["outputs"]
    frozen_path = SCORES / "items.parquet"
    sha = sha256_file(frozen_path)
    if sha != items_rep["items.parquet"]:
        raise SystemExit("results/scores/items.parquet differs from reports/items_build_report.json")
    inputs["results/scores/items.parquet"] = sha
    pairs_sha = sha256_file(SCORES / "pairs.csv")
    if pairs_sha != items_rep["pairs.csv"]:
        raise SystemExit("results/scores/pairs.csv differs from reports/items_build_report.json")
    inputs["results/scores/pairs.csv"] = pairs_sha
    frozen = pd.read_parquet(frozen_path)
    frames = [frozen[(frozen["kind"] == "llm") & (frozen["strategy"] == DIRECT) & frozen["detector"].isin(tcfg["models"])]]
    for m in tcfg["models"]:
        det = TWOSTAGE_PREFIX + m
        rep_path = ROOT / "reports" / f"scoring_additional_{det}.json"
        if not rep_path.exists():
            raise SystemExit(f"{rep_path.relative_to(ROOT)} not found; run scripts/07_score_model.py --model {m} --kind twostage first")
        rep = json.loads(read_text(rep_path))
        p = ROOT / rep["out_dir"] / "items.parquet"
        sha = sha256_file(p)
        if sha != rep["outputs"]["items.parquet"]:
            raise SystemExit(f"{p.relative_to(ROOT)} differs from {rep_path.relative_to(ROOT)}")
        inputs[str(p.relative_to(ROOT))] = sha
        add = pd.read_parquet(p)
        frames.append(add[(add["detector"] == det) & (add["kind"] == "twostage")])
    items = annotate(pd.concat(frames, ignore_index=True))
    cells = {}
    for (det, strat), d in items.groupby(["detector", "strategy"], sort=False):
        cells[(det, strat)] = d.set_index("item_id", drop=False).sort_index()
    expected = {(m, DIRECT) for m in tcfg["models"]} | {(TWOSTAGE_PREFIX + m, sk) for m in tcfg["models"] for _, sk, _ in fits_of(tcfg)}
    missing = sorted(expected - set(cells))
    if missing:
        raise SystemExit(f"cells missing from the item tables: {missing}")
    ids = None
    for key, d in cells.items():
        if ids is None:
            ids = set(d.index)
        elif set(d.index) != ids:
            raise SystemExit(f"cell {key} does not hold the same evaluation items as the others")
    return cells, inputs


# ---------------------------------------------------------------- the three tables

def contrast_rows(cells: dict, pairs: pd.DataFrame, model: str, fit_key: str, sk: str, analysis: str, seed: int, B: int) -> list:
    """Difference of deltas, two-stage (arm b) minus direct zero-shot (arm a), per condition; family = the fit's own."""
    a, b = cells[(model, DIRECT)], cells[(TWOSTAGE_PREFIX + model, sk)]
    fam = family_for(TWOSTAGE_PREFIX + model, sk, "twostage")
    rows = []
    for cond in CONDITIONS:
        oa, va, ia, iva = paired_arrays(a, pairs, cond)
        ob, vb, ib, ivb = paired_arrays(b, pairs, cond)
        if analysis == "no_invalid":
            keep = ~(ia | iva | ib | ivb)
            oa, va, ob, vb = oa[keep], va[keep], ob[keep], vb[keep]
        n = len(oa)
        counts = np.column_stack([oa, va, ob, vb, np.ones(n, dtype=bool)]).astype(np.int64)
        res = point_and_ci(counts, stat_contrast, seed, f"twostage_contrast/{model}/{sk}/{analysis}/{cond}", B)
        rows.append({"family": fam, "model": model, "fit": fit_key, "strategy": sk, "condition": cond,
                     "metric": "spec" if cond == CONTROL else "sens", "arm_a": f"{model}/{DIRECT}", "arm_b": f"{TWOSTAGE_PREFIX}{model}/{sk}",
                     "analysis": analysis, "n_pairs": n,
                     "delta_direct": float(np.mean(oa) - np.mean(va)) if n else np.nan,
                     "delta_twostage": float(np.mean(ob) - np.mean(vb)) if n else np.nan,
                     "value": res["value"], "ci_lo": res["ci_lo"], "ci_hi": res["ci_hi"],
                     "boot_p": bootstrap_p(res["boot"], B), "holm_p": np.nan})
    return rows


def _aligned(a: pd.DataFrame, b: pd.DataFrame, groups: list) -> pd.DataFrame:
    sub = a[a["group"].isin(groups)]
    bb = b.loc[sub.index]
    pos = sub["label_true"] == "phish"
    return pd.DataFrame({"cluster": sub["cluster"].to_numpy(), "ca": sub["correct"].to_numpy(int), "cb": bb["correct"].to_numpy(int),
                         "one": 1, "cpa": (sub["correct"] & pos).to_numpy(int), "cna": (sub["correct"] & ~pos).to_numpy(int),
                         "cpb": (bb["correct"] & pos).to_numpy(int), "cnb": (bb["correct"] & ~pos).to_numpy(int),
                         "np_": pos.to_numpy(int), "nn": (~pos).to_numpy(int)})


def rate_diff_rows(cells: dict, model: str, fit_key: str, sk: str, seed: int, B: int) -> list:
    """Two-stage minus direct rate on the same items (primary analysis), one row per rate of metrics_long."""
    a, b = cells[(model, DIRECT)], cells[(TWOSTAGE_PREFIX + model, sk)]
    rows = []

    def row(metric, cond, d, res, n):
        return {"model": model, "fit": fit_key, "strategy": sk, "metric": metric, "condition": cond, "analysis": "primary",
                "n": n, "n_clusters": int(d["cluster"].nunique()), "rate_direct": float(d["ca"].mean()) if n else np.nan,
                "rate_twostage": float(d["cb"].mean()) if n else np.nan, "value": res["value"], "ci_lo": res["ci_lo"], "ci_hi": res["ci_hi"]}

    for metric, cond, grp in DIFF_METRICS:
        d = _aligned(a, b, [grp])
        res = point_and_ci(cluster_counts(d, ["ca", "cb", "one"]), stat_rate_diff, seed, f"twostage_ratediff/{model}/{sk}/{metric}/{cond}", B)
        rows.append(row(metric, cond, d, res, len(d)))
    core = _aligned(a, b, CORE_GROUPS)
    res = point_and_ci(cluster_counts(core, ["ca", "cb", "one"]), stat_rate_diff, seed, f"twostage_ratediff/{model}/{sk}/acc/core_originals", B)
    rows.append(row("acc", "core_originals", core, res, len(core)))
    res = point_and_ci(cluster_counts(core, ["cpa", "cna", "cpb", "cnb", "np_", "nn"]), stat_bal_acc_diff, seed,
                       f"twostage_ratediff/{model}/{sk}/bal_acc/core_originals", B)
    r = row("bal_acc", "core_originals", core, res, len(core))
    r["rate_direct"] = 0.5 * (core["cpa"].sum() / core["np_"].sum() + core["cna"].sum() / core["nn"].sum())
    r["rate_twostage"] = 0.5 * (core["cpb"].sum() / core["np_"].sum() + core["cnb"].sum() / core["nn"].sum())
    rows.append(r)
    return rows


def disagreement_rows(cells: dict, model: str, fit_key: str, sk: str) -> list:
    """Items on which the direct verdict and the two-stage label differ, by item group and over all items."""
    a, b = cells[(model, DIRECT)], cells[(TWOSTAGE_PREFIX + model, sk)]
    bb = b.loc[a.index]
    rows = []
    for grp in ["all"] + GROUPS:
        mask = np.ones(len(a), dtype=bool) if grp == "all" else (a["group"] == grp).to_numpy()
        la, lb = a["label_pred"].to_numpy()[mask], bb["label_pred"].to_numpy()[mask]
        ca, cb = a["correct"].to_numpy()[mask], bb["correct"].to_numpy()[mask]
        n = int(mask.sum())
        rows.append({"model": model, "fit": fit_key, "strategy": sk, "group": grp, "n": n, "n_disagree": int(np.sum(la != lb)),
                     "share_disagree": float(np.mean(la != lb)) if n else np.nan, "direct_only_correct": int(np.sum(ca & ~cb)),
                     "twostage_only_correct": int(np.sum(~ca & cb)), "both_correct": int(np.sum(ca & cb)), "neither_correct": int(np.sum(~ca & ~cb))})
    return rows


def run(cells: dict, pairs: pd.DataFrame, tcfg: dict, seed: int, B: int = B_DEFAULT, log=print) -> dict:
    cons, diffs, dis = [], [], []
    for analysis in ANALYSES:
        for m in tcfg["models"]:
            for fit_key, sk, _ in fits_of(tcfg):
                cons += contrast_rows(cells, pairs, m, fit_key, sk, analysis, seed, B)
        log(f"  {analysis:<10} contrasts")
    for m in tcfg["models"]:
        for fit_key, sk, _ in fits_of(tcfg):
            diffs += rate_diff_rows(cells, m, fit_key, sk, seed, B)
            dis += disagreement_rows(cells, m, fit_key, sk)
        log(f"  primary    rate differences and disagreement {m}")
    cons = apply_holm(pd.DataFrame(cons), "boot_p", ["analysis", "family"])
    fams = cons[cons["analysis"] == "primary"].groupby("family").size().to_dict()
    return {"contrasts": cons, "rate_differences": pd.DataFrame(diffs), "disagreement": pd.DataFrame(dis),
            "families": {k: int(v) for k, v in sorted(fams.items())}}


def write_all(res: dict, out_dir: Path) -> dict:
    return {name: write_csv(res[name[:-4]], out_dir / name) for name in OUTPUTS}


def top_coefficients(tcfg: dict, k: int = 3) -> dict:
    """The k largest |coefficient| of every fitted stage 2, from reports/twostage_report.json (section 7, last bullet)."""
    rep = json.loads(read_text(TWOSTAGE_REPORT))["stage2"]
    return {m: {fit: [{"feature": c["feature"], "coef": c["coef"]} for c in rep[m][fit]["coefficients"][:k]]
                for fit, _, _ in fits_of(tcfg)} for m in tcfg["models"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="recompute and compare with the CSVs on disk; write nothing")
    ap.add_argument("--B", type=int, default=B_DEFAULT)
    a = ap.parse_args()
    tcfg, seed = load_config("twostage.yaml"), load_config("data.yaml")["seed"]
    t0 = time.time()
    cells, inputs = load_cells(tcfg)
    pairs = pd.read_csv(SCORES / "pairs.csv")
    res = run(cells, pairs, tcfg, seed, a.B, log=lambda s: print(s, flush=True))
    runtime = time.time() - t0
    if a.check:
        with tempfile.TemporaryDirectory() as td:
            fresh = write_all(res, Path(td))
        cmp = compare_outputs(fresh, OUT_DIR)
        ok = all(v == "identical" for v in cmp.values())
        print(f"re-run {'IDENTICAL' if ok else 'DIFFERS'}: {cmp} ({runtime:.0f} s)")
        return 0 if ok else 1
    hashes = write_all(res, OUT_DIR)
    prim = res["contrasts"][res["contrasts"]["analysis"] == "primary"]
    report = {"computed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "note": "TASK_08 section 7 primary comparison (exploratory, post hoc; QUESTIONS.md item 18): difference of robustness deltas, "
                      "two-stage minus the same model's direct zero-shot verdict, per condition; the pre-registered families, CSVs, tables "
                      "and figures are untouched. Positive values: the rewrite costs the two-stage detector more (or benefits it less) than the direct verdict; negative: less.",
              "models": tcfg["models"], "fits": {k: v["strategy_key"] for k, v in tcfg["fits"].items()}, "direct_strategy": DIRECT,
              "conditions": CONDITIONS, "inputs": inputs, "B": a.B, "seed": seed, "analyses": ANALYSES, "families": res["families"],
              "holm": "within (analysis, family); boot_p = two-sided percentile p floored at 1/B (item 12 refinement 2)",
              "rows": {k: int(len(res[k])) for k in ("contrasts", "rate_differences", "disagreement")},
              "primary_contrasts": {f"{r['model']}/{r['strategy']}/{r['condition']}": {"n_pairs": int(r["n_pairs"]), "delta_direct": round(float(r["delta_direct"]), 6),
                                                                                     "delta_twostage": round(float(r["delta_twostage"]), 6), "value": round(float(r["value"]), 6),
                                                                                     "ci_lo": round(float(r["ci_lo"]), 6), "ci_hi": round(float(r["ci_hi"]), 6),
                                                                                     "boot_p": float(r["boot_p"]), "holm_p": float(r["holm_p"])}
                                    for _, r in prim.iterrows()},
              "largest_coefficients": top_coefficients(tcfg), "out_dir": str(OUT_DIR.relative_to(ROOT)), "outputs": hashes,
              "runtime_s": round(runtime, 1), "versions": {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__},
              "git_commit": git("rev-parse", "--short", "HEAD"), "git_describe": git("describe", "--tags", "--always")}
    write_json(REPORT, report)
    print(f"two-stage comparison: {report['rows']}; families {res['families']}; runtime {runtime:.0f} s -> {report['out_dir']}, "
          f"{REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
