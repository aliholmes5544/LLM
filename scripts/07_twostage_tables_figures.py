#!/usr/bin/env python3
"""
07_twostage_tables_figures.py — TASK_08 section 8: table T12 (results/tables/tab_t12_twostage.tex) and figure F8
(figures/ch04_f8_twostage_eng.png) of the two-stage indicator detector (QUESTIONS.md item 18; exploratory, post hoc;
Chapter 4 Section 4.5). Reads only CSVs: the frozen results/scores/{metrics_long,deltas_long}.csv for the direct zero-shot
rows of the three models, results/scores/additional/twostage_<model>/{metrics_long,deltas_long}.csv for the two stage-2
fits and results/scores/additional/twostage_compare/contrasts.csv for the difference of deltas. Computes nothing new;
never touches results/raw, the frozen CSVs or tables T1 to T11 and figures F1 to F7.

T12 is one file with three booktabs tabulars (no caption, no label; the author sets them), separated by comment lines:
  (a) capability on the core originals in the T1 format, per model: direct zero-shot, two-stage clean fit (the primary),
      two-stage attack-aware fit;
  (b) robustness per model and condition: the paired delta of the direct verdict, of the clean fit and of the attack-aware
      fit, with the difference of deltas (two-stage minus direct), bootstrap p and Holm p from contrasts.csv;
  (c) generalisation and specificity in the T8 format plus the paraphrased legitimate control.
F8: three panels (one per model), delta per condition with 95 % CIs, three series: direct zero-shot, two-stage clean fit
(the headline), two-stage attack-aware fit. The helpers, palette and rcParams are those of 07_tables_figures.py.

Usage: python scripts/07_twostage_tables_figures.py
"""
import importlib
import sys

import numpy as np
import pandas as pd

from common import ROOT, load_config, write_json, write_text
from scoring.output import sha256_file
from scoring.score import CONTROL, PHISH_CONDITIONS

tf = importlib.import_module("07_tables_figures")
plt, matplotlib = tf.plt, tf.matplotlib
NAME, COND, STRAT, ci, f3, pct, pval, tex_table, save_fig = tf.NAME, tf.COND, tf.STRAT, tf.ci, tf.f3, tf.pct, tf.pval, tf.tex_table, tf.save_fig

SCORES, ADDITIONAL, TABLES = tf.SCORES, tf.SCORES / "additional", tf.TABLES
REPORT = ROOT / "reports" / "twostage_tables_figures_report.json"
TABLE, FIGURE = "tab_t12_twostage.tex", "f8_twostage"
DIRECT = "zero_shot"
CONDITIONS = PHISH_CONDITIONS + [CONTROL]
PIPELINE = {DIRECT: "direct zero-shot", "lr_clean": "two-stage, clean fit", "lr_all": "two-stage, attack-aware fit"}
SHORT = {DIRECT: "direct", "lr_clean": "clean", "lr_all": "attack-aware"}
# series colours: the direct verdict in ink as in F4, the two fits on the first two slots of the validated palette
SERIES = {DIRECT: ("#0b0b0b", "o", True), "lr_clean": (tf.PALETTE[0], "s", True), "lr_all": (tf.PALETTE[1], "^", False)}
TWOSTAGE_PREFIX = "twostage_"


def load(models: list, fits: list) -> tuple:
    """(metrics, deltas, contrasts): the direct zero-shot rows of the three models from the frozen CSVs, the two-stage rows
    from the additional CSVs, the differences of deltas from the comparison CSV."""
    M = pd.read_csv(SCORES / "metrics_long.csv"); D = pd.read_csv(SCORES / "deltas_long.csv")
    M = M[(M["kind"] == "llm") & (M["strategy"] == DIRECT) & M["detector"].isin(models)]
    D = D[(D["kind"] == "llm") & (D["strategy"] == DIRECT) & D["detector"].isin(models)]
    ms, ds = [M], [D]
    for m in models:
        d = ADDITIONAL / f"{TWOSTAGE_PREFIX}{m}"
        ms.append(pd.read_csv(d / "metrics_long.csv")); ds.append(pd.read_csv(d / "deltas_long.csv"))
    M, D = pd.concat(ms, ignore_index=True), pd.concat(ds, ignore_index=True)
    M["model"] = M["detector"].str.replace(TWOSTAGE_PREFIX, "", regex=False)
    D["model"] = D["detector"].str.replace(TWOSTAGE_PREFIX, "", regex=False)
    C = pd.read_csv(ADDITIONAL / "twostage_compare" / "contrasts.csv")
    have = {(r.model, r.strategy) for r in M[["model", "strategy"]].drop_duplicates().itertuples()}
    need = {(m, s) for m in models for s in [DIRECT] + fits}
    if need - have:
        raise SystemExit(f"rows missing: {sorted(need - have)}")
    return M, D, C


def table_t12(M: pd.DataFrame, D: pd.DataFrame, C: pd.DataFrame, models: list, fits: list) -> str:
    P = M[M["analysis"] == "primary"].set_index(["model", "strategy", "metric", "condition"])
    DP = D[D["analysis"] == "primary"].set_index(["model", "strategy", "condition"])
    CP = C[C["analysis"] == "primary"].set_index(["model", "strategy", "condition"])
    pipelines = [DIRECT] + fits

    def g(m, s, metric, cond, col="value"):
        return P.at[(m, s, metric, cond), col]

    def gci(m, s, metric, cond):
        return ci(g(m, s, metric, cond), g(m, s, metric, cond, "ci_lo"), g(m, s, metric, cond, "ci_hi"))

    # (a) capability block in the T1 format
    rows, grp = [], []
    for m in models:
        for s in pipelines:
            rows.append([NAME[m], PIPELINE[s], gci(m, s, "acc", "core_originals"), gci(m, s, "bal_acc", "core_originals"), gci(m, s, "f1_phish", "core_originals"),
                         f3(g(m, s, "sens", "original")), f3(g(m, s, "spec", "original_core_neg")), f3(g(m, s, "spec", "original_ctrl_modern")),
                         pct(g(m, s, "invalid_rate", "all"))])
        grp.append((NAME[m], len(pipelines)))
    a = tex_table(["Model", "Pipeline", "Accuracy [95% CI]", "Balanced acc. [95% CI]", "F1 (phishing) [95% CI]", "Sens. (334)", "Spec. core (1,002)",
                   "Spec. modern (334)", "Invalid %"], rows, "lllllrrrr", grp)
    # (b) robustness block: deltas of the three pipelines and the differences of deltas
    rows, grp = [], []
    for m in models:
        for cond in CONDITIONS:
            r = [NAME[m], COND[cond], int(DP.at[(m, DIRECT, cond), "n_pairs"]),
                 ci(DP.at[(m, DIRECT, cond), "delta"], DP.at[(m, DIRECT, cond), "ci_lo"], DP.at[(m, DIRECT, cond), "ci_hi"])]
            for s in fits:
                d, c = DP.loc[(m, s, cond)], CP.loc[(m, s, cond)]
                r += [ci(d["delta"], d["ci_lo"], d["ci_hi"]), ci(c["value"], c["ci_lo"], c["ci_hi"]), pval(c["boot_p"]), pval(c["holm_p"])]
            rows.append(r)
        grp.append((NAME[m], len(CONDITIONS)))
    hdr = ["Model", "Condition", "Pairs", "$\\Delta$ direct [95% CI]"]
    for s in fits:
        hdr += [f"$\\Delta$ two-stage, {SHORT[s]} [95% CI]", f"Difference ({SHORT[s]} $-$ direct) [95% CI]", "Bootstrap p", "Holm p"]
    b = tex_table(hdr, rows, "llrl" + "llrr" * len(fits), grp)
    # (c) generalisation and specificity block in the T8 format plus the paraphrased legitimate control
    rows, grp = [], []
    for m in models:
        for s in pipelines:
            rows.append([NAME[m], PIPELINE[s], gci(m, s, "sens", "original"), gci(m, s, "gen_sens", "gen_phish"), gci(m, s, "spec", "original_core_neg"),
                         gci(m, s, "gen_spec", "gen_legit"), gci(m, s, "spec", CONTROL)])
        grp.append((NAME[m], len(pipelines)))
    c = tex_table(["Model", "Pipeline", "Core sens. (334)", "Gen. sens. (1,000)", "Core spec. (1,002)", "Gen. spec. (1,000)", "Spec. para. high control (210)"],
                  rows, "lllllll", grp)
    return ("% T12 (a): capability on the core originals (T1 format); the clean fit is the primary two-stage detector\n" + a +
            "\n% T12 (b): robustness per condition; delta = rate(original) - rate(variant); difference = two-stage minus direct, "
            "cluster bootstrap CI, two-sided bootstrap p, Holm within the fit's family (five tests)\n" + b +
            "\n% T12 (c): generalisation (E-PhishLLM) and specificity (T8 format plus the paraphrased legitimate control)\n" + c)


def fig_f8(D: pd.DataFrame, models: list, fits: list) -> str:
    DP = D[D["analysis"] == "primary"].set_index(["model", "strategy", "condition"])
    series = [DIRECT] + fits
    fig, axes = plt.subplots(1, len(models), figsize=(3.5 * len(models), 3.6), sharey=True)
    x = np.arange(len(CONDITIONS))
    for ax, m in zip(np.atleast_1d(axes), models):
        for j, s in enumerate(series):
            colour, marker, filled = SERIES[s]
            d = DP.loc[[(m, s, c) for c in CONDITIONS]]
            xs = x + (j - (len(series) - 1) / 2) * 0.22
            ax.errorbar(xs, d["delta"], yerr=[d["delta"] - d["ci_lo"], d["ci_hi"] - d["delta"]], fmt=marker, color=colour,
                        mfc=colour if filled else "white", ms=5, capsize=1.5, lw=0.9, label=PIPELINE[s])
        ax.axhline(0, color="#333333", lw=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels([COND[c] if c != CONTROL else "para. high\n(legit. control)" for c in CONDITIONS], rotation=30, ha="right", fontsize=8)
        ax.set_title(NAME[m], fontsize=9, fontweight="normal")
    np.atleast_1d(axes)[0].set_ylabel("$\\Delta$ = rate(original) $-$ rate(variant)")
    handles, labels = np.atleast_1d(axes)[0].get_legend_handles_labels()
    fig.legend(handles, labels, fontsize=8, ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.27))
    return save_fig(fig, FIGURE)


def main() -> int:
    tcfg = load_config("twostage.yaml")
    models = list(tcfg["models"])
    fits = [v["strategy_key"] for v in sorted(tcfg["fits"].values(), key=lambda v: not v.get("primary"))]
    M, D, C = load(models, fits)
    TABLES.mkdir(parents=True, exist_ok=True)
    write_text(TABLES / TABLE, table_t12(M, D, C, models, fits))
    fig = fig_f8(D, models, fits)
    report = {"tables": {TABLE: sha256_file(TABLES / TABLE)}, "figures": {fig: sha256_file(tf.FIGS / fig)},
              "inputs": {str(p.relative_to(ROOT)): sha256_file(p) for p in
                         [SCORES / "metrics_long.csv", SCORES / "deltas_long.csv", ADDITIONAL / "twostage_compare" / "contrasts.csv"] +
                         [ADDITIONAL / f"{TWOSTAGE_PREFIX}{m}" / n for m in models for n in ("metrics_long.csv", "deltas_long.csv")]},
              "models": models, "fits": fits, "headline": fits[0], "matplotlib": matplotlib.__version__,
              "series_colours": {s: SERIES[s][0] for s in [DIRECT] + fits}, "git_commit": tf.git("rev-parse", "--short", "HEAD")}
    write_json(REPORT, report)
    print(f"{TABLE} -> results/tables/; {fig} -> figures/; {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
