"""
score.py — primary metrics, robustness deltas and pre-registered contrasts (TASK_07 sections 1 to 3;
QUESTIONS.md item 12e with refinements 1, 2, 5, 6; item 15 decisions; Chapter 4 Sections 4.3 and 4.5).

Inputs are the item table (results/scores/items.parquet) and the pairing table (results/scores/pairs.csv)
of step 1, plus the ensemble rows built from the six language models. For every cell (detector x strategy)
and both analyses (primary: invalid = incorrect; no_invalid: invalid items dropped, a pair dropped when
either member is invalid) the module computes
  metrics_long  sens by condition, spec by legitimate set, acc / bal_acc / f1_phish on core originals,
                gen_sens / gen_spec, invalid rates, each with a 95% cluster-bootstrap CI;
  deltas_long   paired original-minus-variant deltas with CI, exact McNemar p and Holm p within family;
  contrasts     F-RQ2 size contrasts and F-RQ3 strategy contrasts as cluster-bootstrap differences of deltas.
Row order is fixed by construction so that a re-run reproduces every table byte for byte.
"""
import numpy as np
import pandas as pd

from scoring.ensemble import ENSEMBLE, ensemble_rows
from scoring.stats import (B_DEFAULT, bootstrap_p, holm, mcnemar_exact, mcnemar_power, point_and_ci,
                           stat_bal_acc, stat_contrast, stat_delta, stat_f1, stat_rate)

MODELS = ["llama31-8b", "mistral-7b", "gemma2-9b", "qwen25-7b", "qwen25-14b", "gemma2-27b"]
STRATEGIES = ["zero_shot", "few_shot", "cot", "role"]
BASELINES = ["baseline_tfidf_lr", "baseline_tfidf_svm", "baseline_distilbert"]
PHISH_CONDITIONS = ["para_low", "para_high", "obf_low", "obf_high"]
CONTROL = "para_high_ctrl"
SIZE_PAIRS = [("qwen25-7b", "qwen25-14b"), ("gemma2-9b", "gemma2-27b")]
CONTRAST_CONDITIONS = ["para_high", "obf_high"]
ANALYSES = ["primary", "no_invalid"]
CORE_GROUPS = ["phish_original", "legit_core_neg", "legit_ctrl_modern"]
GROUPS = ["phish_original", "phish_para_low", "phish_para_high", "phish_obf_low", "phish_obf_high",
          "legit_core_neg", "legit_ctrl_modern", "legit_ctrl_para", "gen_phish", "gen_legit"]
RATE_METRICS = [  # metric, condition label, item group, partition set
    ("sens", "original", "phish_original", "core"),
    *[("sens", c, f"phish_{c}", "core") for c in PHISH_CONDITIONS],
    ("spec", "original_core_neg", "legit_core_neg", "core"),
    ("spec", "original_ctrl_modern", "legit_ctrl_modern", "core"),
    ("spec", CONTROL, "legit_ctrl_para", "core"),
    ("gen_sens", "gen_phish", "gen_phish", "generalisation"),
    ("gen_spec", "gen_legit", "gen_legit", "generalisation"),
]
POWER_NOTE = {"n_pairs": 334, "discordant": 0.10, "drop": 0.05, "alpha": 0.05}


def group_of(item_class: str, condition: str) -> str:
    return f"phish_{condition}" if item_class == "phish_variant" else item_class


def prepare(items: pd.DataFrame) -> pd.DataFrame:
    """Add the ensemble rows, the item group and the primary correctness flag (invalid = incorrect)."""
    items = pd.concat([items, ensemble_rows(items, MODELS)], ignore_index=True)
    items["group"] = [group_of(a, b) for a, b in zip(items["item_class"], items["condition"])]
    items["correct"] = (items["label_pred"] == items["label_true"]) & ~items["invalid"]
    return items


def cell_order(items: pd.DataFrame) -> list:
    """(detector, kind, strategy) in report order: six models x four strategies, ensemble x four, baselines."""
    cells = [(m, "llm", s) for s in STRATEGIES for m in MODELS]
    cells += [(ENSEMBLE, ENSEMBLE, s) for s in STRATEGIES]
    cells += [(b, "baseline", "supervised") for b in BASELINES]
    have = set(zip(items["detector"], items["kind"], items["strategy"]))
    missing = [c for c in cells if c not in have]
    if missing:
        raise SystemExit(f"cells missing from the item table: {missing}")
    return cells


def family_of(kind: str, strategy: str) -> str:
    if kind == "llm":
        return "F-RQ4" if strategy == "zero_shot" else f"S-{strategy}"
    return "S-ensemble" if kind == ENSEMBLE else "S-baselines"


def cluster_counts(d: pd.DataFrame, cols: list) -> np.ndarray:
    """k x len(cols) matrix of per-cluster sums (clusters sorted by id, so the order is reproducible)."""
    if len(d) == 0:
        return np.zeros((0, len(cols)), dtype=np.int64)
    return d.groupby("cluster", sort=True)[cols].sum().to_numpy(dtype=np.int64)


def _row(cell, analysis, pset, condition, metric, d, res, n_clusters):
    det, kind, strat = cell
    return {"detector": det, "kind": kind, "strategy": strat, "analysis": analysis, "partition_set": pset,
            "condition": condition, "metric": metric, "n": int(len(d)), "n_clusters": int(n_clusters),
            "value": res["value"], "ci_lo": res["ci_lo"], "ci_hi": res["ci_hi"]}


def cell_metrics(cell, df: pd.DataFrame, analysis: str, seed: int, B: int) -> list:
    det, kind, strat = cell
    d = df[~df["invalid"]] if analysis == "no_invalid" else df
    d = d.assign(one=1)
    rows = []
    for metric, cond, grp, pset in RATE_METRICS:
        sub = d[d["group"] == grp]
        counts = cluster_counts(sub, ["correct", "one"])
        res = point_and_ci(counts, stat_rate, seed, f"{det}/{strat}/{analysis}/{metric}/{cond}", B)
        rows.append(_row(cell, analysis, pset, cond, metric, sub, res, counts.shape[0]))
    core = d[d["group"].isin(CORE_GROUPS)].copy()
    pos = core["label_true"] == "phish"
    core["cp"], core["np_"] = (core["correct"] & pos).astype(int), pos.astype(int)
    core["cn"], core["nn"] = (core["correct"] & ~pos).astype(int), (~pos).astype(int)
    pred_phish = core["label_pred"] == "phish"
    core["tp"] = (pred_phish & pos).astype(int)
    core["fp"] = (pred_phish & ~pos).astype(int)
    core["fn"] = (~pred_phish & pos).astype(int)
    for metric, cols, stat in (("acc", ["correct", "one"], stat_rate), ("bal_acc", ["cp", "np_", "cn", "nn"], stat_bal_acc),
                               ("f1_phish", ["tp", "fp", "fn"], stat_f1)):
        counts = cluster_counts(core, cols)
        res = point_and_ci(counts, stat, seed, f"{det}/{strat}/{analysis}/{metric}/core_originals", B)
        rows.append(_row(cell, analysis, "core", "core_originals", metric, core, res, counts.shape[0]))
    if analysis == "primary":
        dd = df.assign(one=1, inv=df["invalid"].astype(int))
        for cond in ["all"] + GROUPS:
            sub = dd if cond == "all" else dd[dd["group"] == cond]
            counts = cluster_counts(sub, ["inv", "one"])
            res = point_and_ci(counts, stat_rate, seed, f"{det}/{strat}/{analysis}/invalid_rate/{cond}", B)
            pset = "all" if cond == "all" else ("generalisation" if cond.startswith("gen_") else "core")
            rows.append(_row(cell, analysis, pset, cond, "invalid_rate", sub, res, counts.shape[0]))
    return rows


def paired_arrays(df: pd.DataFrame, pairs: pd.DataFrame, condition: str):
    """(orig_correct, var_correct, orig_invalid, var_invalid) for the pairs of one condition, in pairs order."""
    if condition == CONTROL:
        pp = pairs[pairs["item_class"] == "legit_ctrl_para"]
    else:
        pp = pairs[(pairs["item_class"] == "phish_variant") & (pairs["condition"] == condition)]
    o, v = df.loc[pp["cluster"].values], df.loc[pp["variant_id"].values]
    return (o["correct"].to_numpy(bool), v["correct"].to_numpy(bool), o["invalid"].to_numpy(bool), v["invalid"].to_numpy(bool))


def cell_deltas(cell, df: pd.DataFrame, pairs: pd.DataFrame, analysis: str, seed: int, B: int) -> list:
    det, kind, strat = cell
    rows = []
    for cond in PHISH_CONDITIONS + [CONTROL]:
        oc, vc, oi, vi = paired_arrays(df, pairs, cond)
        if analysis == "no_invalid":
            keep = ~(oi | vi)
            oc, vc = oc[keep], vc[keep]
        n = len(oc)
        counts = np.column_stack([oc.astype(np.int64), vc.astype(np.int64), np.ones(n, dtype=np.int64)])
        res = point_and_ci(counts, stat_delta, seed, f"{det}/{strat}/{analysis}/delta/{cond}", B)
        b, c = int(np.sum(oc & ~vc)), int(np.sum(~oc & vc))
        rows.append({"detector": det, "kind": kind, "strategy": strat, "analysis": analysis, "condition": cond,
                     "metric": "spec" if cond == CONTROL else "sens", "n_pairs": n,
                     "rate_original": float(oc.mean()) if n else np.nan, "rate_variant": float(vc.mean()) if n else np.nan,
                     "delta": res["value"], "ci_lo": res["ci_lo"], "ci_hi": res["ci_hi"],
                     "b_orig_only": b, "c_var_only": c, "discordant": (b + c) / n if n else np.nan,
                     "mcnemar_p": mcnemar_exact(b, c), "holm_p": np.nan, "family": family_of(kind, strat)})
    return rows


def contrast_specs() -> list:
    specs = []
    for small, large in SIZE_PAIRS:
        for cond in PHISH_CONDITIONS:
            specs.append({"family": "F-RQ2", "rq": "RQ2", "contrast": f"{large} vs {small}", "model": f"{small}|{large}",
                          "strategy": "zero_shot", "condition": cond, "arm_a": f"{small}/zero_shot", "arm_b": f"{large}/zero_shot"})
    for m in MODELS:
        for s in STRATEGIES[1:]:
            for cond in CONTRAST_CONDITIONS:
                specs.append({"family": "F-RQ3", "rq": "RQ3", "contrast": f"{s} vs zero_shot", "model": m, "strategy": s,
                              "condition": cond, "arm_a": f"{m}/zero_shot", "arm_b": f"{m}/{s}"})
    return specs


def contrasts(cells: dict, pairs: pd.DataFrame, analysis: str, seed: int, B: int) -> list:
    rows = []
    for sp in contrast_specs():
        a, b = cells[tuple(sp["arm_a"].split("/"))], cells[tuple(sp["arm_b"].split("/"))]
        oa, va, ia, iva = paired_arrays(a, pairs, sp["condition"])
        ob, vb, ib, ivb = paired_arrays(b, pairs, sp["condition"])
        if analysis == "no_invalid":
            keep = ~(ia | iva | ib | ivb)
            oa, va, ob, vb = oa[keep], va[keep], ob[keep], vb[keep]
        n = len(oa)
        counts = np.column_stack([oa, va, ob, vb, np.ones(n, dtype=bool)]).astype(np.int64)
        table = f"contrast/{sp['arm_a']}/{sp['arm_b']}/{analysis}/{sp['condition']}"
        res = point_and_ci(counts, stat_contrast, seed, table, B)
        rows.append({**sp, "analysis": analysis, "n_pairs": n,
                     "delta_a": float(np.mean(oa) - np.mean(va)) if n else np.nan,
                     "delta_b": float(np.mean(ob) - np.mean(vb)) if n else np.nan,
                     "value": res["value"], "ci_lo": res["ci_lo"], "ci_hi": res["ci_hi"],
                     "boot_p": bootstrap_p(res["boot"], B), "holm_p": np.nan})
    return rows


def apply_holm(df: pd.DataFrame, pcol: str, keys: list) -> pd.DataFrame:
    df = df.copy()
    for _, idx in df.groupby(keys, sort=False).groups.items():
        df.loc[idx, "holm_p"] = holm(df.loc[idx, pcol].tolist())
    return df


def run(items: pd.DataFrame, pairs: pd.DataFrame, seed: int, B: int = B_DEFAULT, log=print) -> dict:
    """All tables of TASK_07 sections 2 and 3 plus the structural information for the report."""
    items = prepare(items)
    order = cell_order(items)
    cells = {}
    for det, kind, strat in order:
        d = items[(items["detector"] == det) & (items["strategy"] == strat)].set_index("item_id", drop=False)
        cells[(det, strat)] = d
    metrics, deltas, cons = [], [], []
    for analysis in ANALYSES:
        for cell in order:
            d = cells[(cell[0], cell[2])]
            metrics += cell_metrics(cell, d, analysis, seed, B)
            deltas += cell_deltas(cell, d, pairs, analysis, seed, B)
            log(f"  {analysis:<10} {cell[0]}/{cell[2]}")
        cons += contrasts(cells, pairs, analysis, seed, B)
        log(f"  {analysis:<10} contrasts")
    metrics = pd.DataFrame(metrics)
    deltas = apply_holm(pd.DataFrame(deltas), "mcnemar_p", ["analysis", "family"])
    cons = apply_holm(pd.DataFrame(cons), "boot_p", ["analysis", "family"])
    cons = cons[["family", "rq", "contrast", "model", "strategy", "condition", "arm_a", "arm_b", "analysis", "n_pairs",
                 "delta_a", "delta_b", "value", "ci_lo", "ci_hi", "boot_p", "holm_p"]]
    ens = items[items["kind"] == ENSEMBLE][["strategy", "item_id", "label_pred", "invalid", "n_valid_votes",
                                             "n_phish_votes", "n_legit_votes"]].sort_values(["strategy", "item_id"])
    prim = deltas[deltas["analysis"] == "primary"]
    fam_sizes = prim.groupby("family").size().to_dict()
    fam_sizes.update(cons[cons["analysis"] == "primary"].groupby("family").size().to_dict())
    rq4 = prim[prim["family"] == "F-RQ4"]
    info = {"n_cells": len(order), "cells": [f"{d}/{s}" for d, _, s in order], "B": B, "seed": seed,
            "families": {k: int(v) for k, v in sorted(fam_sizes.items())},
            "power_note": {**POWER_NOTE, "power": mcnemar_power(**POWER_NOTE), "basis": "a priori (item 12 refinement 5)"},
            "observed_discordance_F_RQ4": {"min": float(rq4["discordant"].min()), "median": float(rq4["discordant"].median()),
                                           "max": float(rq4["discordant"].max()), "basis": "post hoc descriptive check"}}
    return {"metrics_long": metrics, "deltas_long": deltas, "contrasts": cons, "ensemble_predictions": ens.reset_index(drop=True),
            "info": info, "items": items}
