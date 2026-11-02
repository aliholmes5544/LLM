#!/usr/bin/env python3
"""
07_tables_figures.py — step 07, step 3 (TASK_07 sections 5 and 6): LaTeX tables T1 to T11 and A1 under
results/tables/tab_*.tex (booktabs, no caption, no label; the author sets labels) and figures F1 to F7 under
figures/ch04_*_eng.png (300 dpi, colour-blind-safe categorical palette in fixed model order, no title inside
the image). Reads only the CSVs written by 07_score.py and 07_secondary.py; computes nothing new except
pooling over models for the cue table and figure, and never touches results/raw.

Usage: python scripts/07_tables_figures.py
"""
import json
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402

from common import ROOT, write_json, write_text  # noqa: E402
from scoring.cues import CATEGORIES  # noqa: E402
from scoring.output import sha256_file  # noqa: E402
from scoring.score import MODELS, STRATEGIES, PHISH_CONDITIONS, CONTROL, BASELINES, GROUPS  # noqa: E402

SCORES, TABLES, FIGS = ROOT / "results" / "scores", ROOT / "results" / "tables", ROOT / "figures"
REPORT = ROOT / "reports" / "tables_figures_report.json"
NAME = {"llama31-8b": "Llama-3.1-8B", "mistral-7b": "Mistral-7B", "gemma2-9b": "Gemma-2-9B", "qwen25-7b": "Qwen2.5-7B",
        "qwen25-14b": "Qwen2.5-14B", "gemma2-27b": "Gemma-2-27B", "ensemble": "Ensemble (majority)",
        "baseline_tfidf_lr": "TF-IDF + LR", "baseline_tfidf_svm": "TF-IDF + SVM", "baseline_distilbert": "DistilBERT"}
STRAT = {"zero_shot": "zero-shot", "few_shot": "few-shot", "cot": "CoT", "role": "role", "supervised": "supervised"}
COND = {"original": "original", "para_low": "para. low", "para_high": "para. high", "obf_low": "obf. low",
        "obf_high": "obf. high", CONTROL: "para. high (legit. control)"}
CAT = {"urgency": "urgency", "link_url": "link / URL", "sender_mismatch": "sender / domain", "credential_payment": "credential / payment",
       "grammar_spelling": "grammar / spelling", "impersonation_authority": "impersonation / authority", "attachment": "attachment",
       "generic_greeting": "generic greeting"}
# validated categorical palette (dataviz reference instance, adjacent pairs CVD-safe in this order), one slot per model
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
COLOR = dict(zip(MODELS, PALETTE))
GREY = "#6f6e6a"
DETECTOR_ORDER = MODELS + ["ensemble"] + BASELINES
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e3e2de", "grid.linewidth": 0.6, "axes.axisbelow": True,
                     "legend.frameon": False, "savefig.dpi": 300, "figure.dpi": 100})


def git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


# ---------------------------------------------------------------- helpers

def f3(x) -> str:
    return "" if pd.isna(x) else f"{x:.3f}"


def ci(v, lo, hi) -> str:
    return "" if pd.isna(v) else f"{v:.3f} [{lo:.3f}, {hi:.3f}]"


def pval(p) -> str:
    if pd.isna(p):
        return ""
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def pct(x) -> str:
    return "" if pd.isna(x) else f"{100 * x:.1f}"


def tex_table(header: list, rows: list, align: str, groups: list = None) -> str:
    """booktabs tabular; `groups` = optional list of (title, n_rows) blocks separated by midrules."""
    esc = lambda s: str(s).replace("_", "\\_").replace("%", "\\%").replace("&", "\\&")
    lines = [f"\\begin{{tabular}}{{{align}}}", "\\toprule", " & ".join(esc(h) for h in header) + " \\\\", "\\midrule"]
    i = 0
    blocks = groups or [(None, len(rows))]
    for bi, (title, n) in enumerate(blocks):
        if title:
            lines.append(f"\\multicolumn{{{len(header)}}}{{l}}{{\\textit{{{esc(title)}}}}} \\\\")
        for r in rows[i:i + n]:
            lines.append(" & ".join(esc(c) for c in r) + " \\\\")
        i += n
        if bi < len(blocks) - 1:
            lines.append("\\midrule")
    lines += ["\\bottomrule", "\\end{tabular}", ""]
    return "\n".join(lines)


def save_fig(fig, name: str) -> str:
    FIGS.mkdir(exist_ok=True)
    p = FIGS / f"ch04_{name}_eng.png"
    fig.savefig(p, bbox_inches="tight", facecolor="white", metadata={"Software": None})
    plt.close(fig)
    return p.name


def ref_cells():
    """(detector, strategy) rows for the 'reference' tables: six models zero_shot, ensemble zero_shot, baselines."""
    return [(m, "zero_shot") for m in MODELS] + [("ensemble", "zero_shot")] + [(b, "supervised") for b in BASELINES]


# ---------------------------------------------------------------- tables

def tables(M, D, C, cues_f, cues_c, cues_p, hc_sum, ens_votes, frontier) -> dict:
    out = {}
    P = M[M["analysis"] == "primary"].set_index(["detector", "strategy", "metric", "condition"])
    DP = D[D["analysis"] == "primary"].set_index(["detector", "strategy", "condition"])

    def g(det, strat, metric, cond, col="value"):
        return P.at[(det, strat, metric, cond), col]

    # T1 capability on core originals
    rows = []
    for det, s in ref_cells():
        rows.append([NAME[det], STRAT[s], ci(g(det, s, "acc", "core_originals"), g(det, s, "acc", "core_originals", "ci_lo"), g(det, s, "acc", "core_originals", "ci_hi")),
                     ci(g(det, s, "bal_acc", "core_originals"), g(det, s, "bal_acc", "core_originals", "ci_lo"), g(det, s, "bal_acc", "core_originals", "ci_hi")),
                     ci(g(det, s, "f1_phish", "core_originals"), g(det, s, "f1_phish", "core_originals", "ci_lo"), g(det, s, "f1_phish", "core_originals", "ci_hi")),
                     f3(g(det, s, "sens", "original")), f3(g(det, s, "spec", "original_core_neg")), f3(g(det, s, "spec", "original_ctrl_modern")),
                     pct(g(det, s, "invalid_rate", "all"))])
    out["tab_t1_capability.tex"] = tex_table(["Detector", "Strategy", "Accuracy [95% CI]", "Balanced acc. [95% CI]", "F1 (phishing) [95% CI]",
                                              "Sens. (334)", "Spec. core (1,002)", "Spec. modern (334)", "Invalid %"], rows, "llllllrrr",
                                             [("Language models, zero-shot", 6), ("Ensemble", 1), ("Supervised baselines", 3)])
    # T2 sensitivity by condition
    rows = []
    for det, s in ref_cells():
        r = [NAME[det]]
        for cond in ["original"] + PHISH_CONDITIONS:
            r.append(ci(g(det, s, "sens", cond), g(det, s, "sens", cond, "ci_lo"), g(det, s, "sens", cond, "ci_hi")))
        r.append(ci(g(det, s, "spec", CONTROL), g(det, s, "spec", CONTROL, "ci_lo"), g(det, s, "spec", CONTROL, "ci_hi")))
        rows.append(r)
    out["tab_t2_sens_by_condition.tex"] = tex_table(["Detector", "Original (334)", "Para. low (334)", "Para. high (325)", "Obf. low (334)",
                                                     "Obf. high (334)", "Spec. para. high control (210)"], rows, "lllllll",
                                                    [("Language models, zero-shot", 6), ("Ensemble", 1), ("Supervised baselines", 3)])

    # T3 / T4 deltas
    def delta_rows(det, s):
        rows = []
        for cond in PHISH_CONDITIONS + [CONTROL]:
            r = DP.loc[(det, s, cond)]
            rows.append([NAME[det], COND[cond], int(r["n_pairs"]), f3(r["rate_original"]), f3(r["rate_variant"]),
                         ci(r["delta"], r["ci_lo"], r["ci_hi"]), f"{int(r['b_orig_only'])} / {int(r['c_var_only'])}", pval(r["mcnemar_p"]), pval(r["holm_p"])])
        return rows
    hdr = ["Detector", "Condition", "Pairs", "Rate orig.", "Rate variant", "$\\Delta$ (orig. $-$ variant) [95% CI]", "Discordant b / c", "McNemar p", "Holm p"]
    rows, grp = [], []
    for det in MODELS:
        rows += delta_rows(det, "zero_shot")
    grp.append(("Family F-RQ4: language models, zero-shot (30 tests)", len(rows))); n0 = len(rows)
    rows += delta_rows("ensemble", "zero_shot"); grp.append(("Ensemble, zero-shot (secondary family S-ensemble, Holm over its 20 tests)", len(rows) - n0)); n0 = len(rows)
    for b in BASELINES:
        rows += delta_rows(b, "supervised")
    grp.append(("Supervised baselines (secondary family S-baselines, 15 tests)", len(rows) - n0))
    out["tab_t3_deltas_zero_shot.tex"] = tex_table(hdr, rows, "llrrrlrrr", grp)
    rows, grp = [], []
    for s in STRATEGIES[1:]:
        n0 = len(rows)
        for det in MODELS:
            rows += delta_rows(det, s)
        grp.append((f"Strategy {STRAT[s]} (secondary family S-{s}, 30 tests)", len(rows) - n0))
    out["tab_t4_deltas_by_strategy.tex"] = tex_table(hdr, rows, "llrrrlrrr", grp)

    # T5 / T6 contrasts
    CP = C[C["analysis"] == "primary"]
    rows = [[r["contrast"].replace("qwen25-14b vs qwen25-7b", "Qwen2.5 14B vs 7B").replace("gemma2-27b vs gemma2-9b", "Gemma-2 27B vs 9B"), COND[r["condition"]],
             int(r["n_pairs"]), f3(r["delta_a"]), f3(r["delta_b"]), ci(r["value"], r["ci_lo"], r["ci_hi"]), pval(r["boot_p"]), pval(r["holm_p"])]
            for _, r in CP[CP["family"] == "F-RQ2"].iterrows()]
    out["tab_t5_size_contrasts.tex"] = tex_table(["Contrast (larger vs smaller)", "Condition", "Pairs", "$\\Delta$ smaller", "$\\Delta$ larger",
                                                  "Difference (larger $-$ smaller) [95% CI]", "Bootstrap p", "Holm p"], rows, "llrrrlrr")
    rows, grp = [], []
    for s in STRATEGIES[1:]:
        n0 = len(rows)
        for _, r in CP[(CP["family"] == "F-RQ3") & (CP["strategy"] == s)].iterrows():
            rows.append([NAME[r["model"]], COND[r["condition"]], int(r["n_pairs"]), f3(r["delta_a"]), f3(r["delta_b"]),
                         ci(r["value"], r["ci_lo"], r["ci_hi"]), pval(r["boot_p"]), pval(r["holm_p"])])
        grp.append((f"{STRAT[s]} vs zero-shot", len(rows) - n0))
    out["tab_t6_strategy_contrasts.tex"] = tex_table(["Model", "Condition", "Pairs", "$\\Delta$ zero-shot", "$\\Delta$ strategy",
                                                      "Difference (strategy $-$ zero-shot) [95% CI]", "Bootstrap p", "Holm p"], rows, "llrrrlrr", grp)
    # T7 invalid rates
    rows = []
    for det in MODELS + ["ensemble"]:
        for s in STRATEGIES:
            rows.append([NAME[det], STRAT[s]] + [pct(g(det, s, "invalid_rate", c)) for c in ["all"] + GROUPS])
    out["tab_t7_invalid_rates.tex"] = tex_table(["Detector", "Strategy", "All"] + [c.replace("_", " ") for c in GROUPS], rows, "ll" + "r" * 11)
    # T8 generalisation
    rows, grp = [], []
    for s in STRATEGIES:
        n0 = len(rows)
        for det in MODELS + ["ensemble"]:
            rows.append([NAME[det], STRAT[s], ci(g(det, s, "sens", "original"), g(det, s, "sens", "original", "ci_lo"), g(det, s, "sens", "original", "ci_hi")),
                         ci(g(det, s, "gen_sens", "gen_phish"), g(det, s, "gen_sens", "gen_phish", "ci_lo"), g(det, s, "gen_sens", "gen_phish", "ci_hi")),
                         ci(g(det, s, "spec", "original_core_neg"), g(det, s, "spec", "original_core_neg", "ci_lo"), g(det, s, "spec", "original_core_neg", "ci_hi")),
                         ci(g(det, s, "gen_spec", "gen_legit"), g(det, s, "gen_spec", "gen_legit", "ci_lo"), g(det, s, "gen_spec", "gen_legit", "ci_hi"))])
        grp.append((STRAT[s], len(rows) - n0))
    n0 = len(rows)
    for b in BASELINES:
        rows.append([NAME[b], "supervised", ci(g(b, "supervised", "sens", "original"), g(b, "supervised", "sens", "original", "ci_lo"), g(b, "supervised", "sens", "original", "ci_hi")),
                     ci(g(b, "supervised", "gen_sens", "gen_phish"), g(b, "supervised", "gen_sens", "gen_phish", "ci_lo"), g(b, "supervised", "gen_sens", "gen_phish", "ci_hi")),
                     ci(g(b, "supervised", "spec", "original_core_neg"), g(b, "supervised", "spec", "original_core_neg", "ci_lo"), g(b, "supervised", "spec", "original_core_neg", "ci_hi")),
                     ci(g(b, "supervised", "gen_spec", "gen_legit"), g(b, "supervised", "gen_spec", "gen_legit", "ci_lo"), g(b, "supervised", "gen_spec", "gen_legit", "ci_hi"))])
    grp.append(("Supervised baselines", len(rows) - n0))
    out["tab_t8_generalisation.tex"] = tex_table(["Detector", "Strategy", "Core sens. (334)", "Gen. sens. (1,000)", "Core spec. (1,002)", "Gen. spec. (1,000)"], rows, "llllll", grp)
    # T9 ensemble
    rows = []
    for _, r in ens_votes.iterrows():
        s = r["strategy"]
        rows.append([STRAT[s], int(r["n_items"]), int(r["unanimous"]), int(r["valid_votes_6"]), int(r["ensemble_invalid"]), pct(r["ensemble_invalid"] / r["n_items"]),
                     ci(g("ensemble", s, "sens", "original"), g("ensemble", s, "sens", "original", "ci_lo"), g("ensemble", s, "sens", "original", "ci_hi")),
                     ci(g("ensemble", s, "spec", "original_core_neg"), g("ensemble", s, "spec", "original_core_neg", "ci_lo"), g("ensemble", s, "spec", "original_core_neg", "ci_hi")),
                     ci(DP.at[("ensemble", s, "para_high"), "delta"], DP.at[("ensemble", s, "para_high"), "ci_lo"], DP.at[("ensemble", s, "para_high"), "ci_hi"]),
                     ci(DP.at[("ensemble", s, "obf_high"), "delta"], DP.at[("ensemble", s, "obf_high"), "ci_lo"], DP.at[("ensemble", s, "obf_high"), "ci_hi"])])
    out["tab_t9_ensemble.tex"] = tex_table(["Strategy", "Items", "Unanimous", "6 valid votes", "Invalid (tie or $<$4 votes)", "Invalid %", "Sens. orig. [95% CI]",
                                            "Spec. core [95% CI]", "$\\Delta$ sens. para. high", "$\\Delta$ sens. obf. high"], rows, "lrrrrrllll")
    # T10 cues: pooled over the six models (CoT), asserted frequency by item group; cue lost / gained by outcome (para_high, obf_high)
    pooled = cues_f.groupby(["group", "category"], sort=False)[["n_text", "n_asserted", "n_empty", "n_rows"]].sum().reset_index()
    pooled["freq"] = pooled["n_asserted"] / pooled["n_text"]
    PF = pooled.set_index(["group", "category"])
    chg = cues_c.groupby(["condition", "category", "outcome"], sort=False)[["n_pairs", "lost", "gained", "kept", "never"]].sum().reset_index()
    CH = chg.set_index(["condition", "category", "outcome"])
    rows = []
    for c in CATEGORIES:
        r = [CAT[c]] + [pct(PF.at[(grp_, c), "freq"]) for grp_ in ["phish_original", "phish_para_high", "phish_obf_high", "legit_core_neg", "legit_ctrl_para"]]
        for cond in ("para_high", "obf_high"):
            for oc in ("stayed_correct", "flipped_to_incorrect", "flipped_to_correct"):
                x = CH.loc[(cond, c, oc)]
                r.append(f"{pct(x['lost'] / x['n_pairs'])} / {pct(x['gained'] / x['n_pairs'])}" if x["n_pairs"] else "")
        rows.append(r)
    out["tab_t10_cues.tex"] = tex_table(["Cue category", "Phish orig. %", "Para. high %", "Obf. high %", "Legit core %", "Legit para. ctrl %",
                                         "PH stayed correct lost/gained %", "PH flipped to incorrect", "PH flipped to correct",
                                         "OH stayed correct", "OH flipped to incorrect", "OH flipped to correct"], rows, "l" + "r" * 11)
    # T11 hard core
    rows = []
    for grp_ in GROUPS:
        d = hc_sum[hc_sum["group"] == grp_].set_index("hard_group")
        n = int(d["n"].sum())
        rows.append([grp_.replace("_", " "), n, int(d.at["all_six", "n"]), pct(d.at["all_six", "share"]), int(d.at["none", "n"]), pct(d.at["none", "share"]),
                     f3(d.at["all_six", "body_words_median"]).replace(".000", ""), f3(d.at["none", "body_words_median"]).replace(".000", "")])
    out["tab_t11_hardcore.tex"] = tex_table(["Item group", "Items", "Missed by all six", "%", "Missed by none", "%", "Body words, median (all six)", "Body words, median (none)"], rows, "lrrrrrrr")
    # A1 sensitivity analysis without invalid outputs (zero_shot / supervised): sens by condition and deltas
    MN = M[M["analysis"] == "no_invalid"].set_index(["detector", "strategy", "metric", "condition"])
    DN = D[D["analysis"] == "no_invalid"].set_index(["detector", "strategy", "condition"])
    rows = []
    for det, s in ref_cells():
        r = [NAME[det]]
        for cond in ["original"] + PHISH_CONDITIONS:
            x = MN.loc[(det, s, "sens", cond)]
            r.append(f"{ci(x['value'], x['ci_lo'], x['ci_hi'])} (n={int(x['n'])})")
        for cond in ("para_high", "obf_high", CONTROL):
            x = DN.loc[(det, s, cond)]
            r.append(f"{ci(x['delta'], x['ci_lo'], x['ci_hi'])} (n={int(x['n_pairs'])}, Holm p {pval(x['holm_p'])})")
        rows.append(r)
    out["tab_a1_sensitivity_no_invalid.tex"] = tex_table(["Detector", "Original", "Para. low", "Para. high", "Obf. low", "Obf. high",
                                                          "$\\Delta$ para. high", "$\\Delta$ obf. high", "$\\Delta$ spec. control"], rows, "lllllllll",
                                                         [("Language models, zero-shot", 6), ("Ensemble", 1), ("Supervised baselines", 3)])
    # frontier as a CSV-backed table is not required; the figure carries it
    return out


# ---------------------------------------------------------------- figures

def fig_f1(M):
    P = M[(M["analysis"] == "primary") & (M["strategy"] == "zero_shot") & (M["metric"] == "sens")]
    conds = ["original"] + PHISH_CONDITIONS
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    w = 0.13
    x = np.arange(len(conds))
    for i, m in enumerate(MODELS):
        d = P[P["detector"] == m].set_index("condition").loc[conds]
        xs = x + (i - 2.5) * w
        ax.bar(xs, d["value"], width=w * 0.92, color=COLOR[m], label=NAME[m], edgecolor="white", linewidth=0.6)
        ax.errorbar(xs, d["value"], yerr=[d["value"] - d["ci_lo"], d["ci_hi"] - d["value"]], fmt="none", ecolor="#333333", elinewidth=0.7, capsize=1.5)
    ax.set_xticks(x)
    ax.set_xticklabels([COND[c] for c in conds])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Sensitivity (recall on phishing), zero-shot")
    ax.set_xlabel("Input condition (core phishing e-mails)")
    ax.legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=8)
    return save_fig(fig, "f1_sens_by_condition")


def fig_f2(D):
    DP = D[(D["analysis"] == "primary") & (D["kind"] == "llm")]
    cmap = LinearSegmentedColormap.from_list("div", ["#2a78d6", "#f1f0ec", "#eb6834"])
    fig, axes = plt.subplots(1, 5, figsize=(11, 3.4), sharey=True)
    vmax = max(abs(DP["delta"].min()), abs(DP["delta"].max()))
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)
    for ax, cond in zip(axes, PHISH_CONDITIONS + [CONTROL]):
        mat = DP[DP["condition"] == cond].pivot(index="detector", columns="strategy", values="delta").loc[MODELS, STRATEGIES]
        im = ax.imshow(mat.values, cmap=cmap, norm=norm, aspect="auto")
        ax.set_xticks(range(4)); ax.set_xticklabels([STRAT[s] for s in STRATEGIES], rotation=45, ha="right")
        ax.set_yticks(range(6)); ax.set_yticklabels([NAME[m] for m in MODELS])
        ax.set_title(COND[cond] if cond != CONTROL else "control: para. high, legit.", fontsize=9, fontweight="normal")
        ax.grid(False)
        for i in range(6):
            for j in range(4):
                v = mat.values[i, j]
                ax.text(j, i, f"{v:+.2f}", ha="center", va="center", fontsize=6.5, color="#0b0b0b" if abs(v) < 0.45 * vmax else "white")
    cb = fig.colorbar(im, ax=axes, fraction=0.02, pad=0.01)
    cb.set_label("$\\Delta$ = rate(original) $-$ rate(variant)")
    return save_fig(fig, "f2_delta_heatmap")


def fig_f3(M):
    P = M[(M["analysis"] == "primary") & (M["strategy"] == "zero_shot") & (M["metric"] == "sens")]
    conds = ["original"] + PHISH_CONDITIONS
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.2), sharey=True)
    for ax, (small, large) in zip(axes, [("qwen25-7b", "qwen25-14b"), ("gemma2-9b", "gemma2-27b")]):
        for m, ls in ((small, "--"), (large, "-")):
            d = P[P["detector"] == m].set_index("condition").loc[conds]
            ax.errorbar(range(5), d["value"], yerr=[d["value"] - d["ci_lo"], d["ci_hi"] - d["value"]], color=COLOR[m], ls=ls, lw=1.6,
                        marker="o", ms=4, capsize=2, label=NAME[m])
        ax.set_xticks(range(5)); ax.set_xticklabels([COND[c] for c in conds], rotation=30, ha="right")
        ax.set_ylim(0, 1.05); ax.legend(loc="lower right", fontsize=8)
    axes[0].set_ylabel("Sensitivity, zero-shot")
    return save_fig(fig, "f3_size_effect")


def fig_f4(D):
    DP = D[(D["analysis"] == "primary") & (D["kind"] == "llm")]
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.3), sharey=True)
    markers = {"zero_shot": "o", "few_shot": "s", "cot": "D", "role": "^"}
    for ax, cond in zip(axes, ["para_high", "obf_high"]):
        for j, s in enumerate(STRATEGIES):
            d = DP[(DP["condition"] == cond) & (DP["strategy"] == s)].set_index("detector").loc[MODELS]
            xs = np.arange(6) + (j - 1.5) * 0.18
            ax.errorbar(xs, d["delta"], yerr=[d["delta"] - d["ci_lo"], d["ci_hi"] - d["delta"]], fmt=markers[s], color=GREY if s != "zero_shot" else "#0b0b0b",
                        mfc="white" if s != "zero_shot" else "#0b0b0b", ms=4.5, capsize=1.5, lw=0.8, label=STRAT[s])
        ax.axhline(0, color="#333333", lw=0.8)
        ax.set_xticks(range(6)); ax.set_xticklabels([NAME[m] for m in MODELS], rotation=30, ha="right")
        ax.set_title(COND[cond], fontsize=9, fontweight="normal")
    axes[0].set_ylabel("$\\Delta$ sensitivity (original $-$ variant)")
    axes[1].legend(title="strategy", fontsize=8, title_fontsize=8, loc="lower right")
    return save_fig(fig, "f4_strategy_effect")


def fig_f5(F):
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.6), sharey=True)
    markers = {"zero_shot": "o", "few_shot": "s", "cot": "D", "role": "^"}
    offsets = {"baseline_tfidf_lr": (5, 5), "baseline_tfidf_svm": (5, -9), "baseline_distilbert": (5, 2)}
    # obf. high: the LR and SVM markers almost coincide (delta +0.03 and 0.00), so LR goes above, SVM below
    offsets_obf = {**offsets, "baseline_tfidf_lr": (5, 9), "baseline_tfidf_svm": (5, -15)}
    for ax, cond in zip(axes, ["para_high", "obf_high"]):
        for _, r in F.iterrows():
            y, lo, hi = r[f"delta_sens_{cond}"], r[f"ci_lo_{cond}"], r[f"ci_hi_{cond}"]
            if r["kind"] == "llm":
                ax.errorbar(r["latency_median_s"], y, yerr=[[y - lo], [hi - y]], fmt=markers[r["strategy"]], color=COLOR[r["detector"]], ms=5, capsize=1.5, lw=0.7)
            else:
                x = max(r["latency_median_s"], 1e-3)
                ax.plot(x, y, marker="x", color=GREY, ms=6)
                off = (offsets_obf if cond == "obf_high" else offsets)[r["detector"]]
                ax.annotate(NAME[r["detector"]], (x, y), fontsize=6.5, color=GREY, xytext=off, textcoords="offset points")
        ax.set_xscale("log"); ax.axhline(0, color="#333333", lw=0.8)
        ax.set_title(COND[cond], fontsize=9, fontweight="normal")
    axes[0].set_ylabel("$\\Delta$ sensitivity (original $-$ variant)")
    fig.supxlabel("median latency per e-mail, s (language models on the GPU tier; baselines on their own backend)", fontsize=9)
    h1 = [plt.Line2D([], [], color=COLOR[m], marker="o", ls="", label=NAME[m]) for m in MODELS]
    h2 = [plt.Line2D([], [], color="#333333", marker=markers[s], ls="", mfc="white", label=STRAT[s]) for s in STRATEGIES]
    fig.legend(handles=h1 + h2, fontsize=7, ncol=5, loc="lower center", bbox_to_anchor=(0.5, -0.1))
    return save_fig(fig, "f5_frontier")


def fig_f6(cues_c):
    chg = cues_c.groupby(["condition", "category", "outcome"], sort=False)[["n_pairs", "lost", "gained"]].sum().reset_index()
    chg["net"] = (chg["gained"] - chg["lost"]) / chg["n_pairs"]
    oc_colors = {"stayed_correct": "#2a78d6", "flipped_to_incorrect": "#eb6834", "stayed_incorrect": "#1baf7a", "flipped_to_correct": "#eda100"}
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    w = 0.2
    for ax, cond in zip(axes, ["para_high", "obf_high"]):
        for j, oc in enumerate(["stayed_correct", "flipped_to_incorrect", "stayed_incorrect", "flipped_to_correct"]):
            d = chg[(chg["condition"] == cond) & (chg["outcome"] == oc)].set_index("category").loc[list(CATEGORIES)]
            n = int(d["n_pairs"].iloc[0])
            ax.bar(np.arange(8) + (j - 1.5) * w, d["net"], width=w * 0.9, color=oc_colors[oc], edgecolor="white", linewidth=0.5,
                   label=f"{oc.replace('_', ' ')} (n={n})")
        ax.axhline(0, color="#333333", lw=0.8)
        ax.set_xticks(range(8)); ax.set_xticklabels([CAT[c] for c in CATEGORIES], rotation=35, ha="right")
        ax.set_title(COND[cond], fontsize=9, fontweight="normal")
        ax.legend(fontsize=7, loc="upper left")
    top = float(chg[chg["condition"].isin(["para_high", "obf_high"])]["net"].max())
    axes[0].set_ylim(top=top * 1.10)                      # 10% headroom so the tallest bar is not clipped
    axes[0].set_ylabel("net change in cue assertion\n(share gained $-$ share lost)")
    return save_fig(fig, "f6_cue_change")


def fig_f7(M):
    P = M[(M["analysis"] == "primary")].set_index(["detector", "strategy", "metric", "condition"])
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.6))
    for ax, (xm, xc, ym, yc, lab) in zip(axes, [("sens", "original", "gen_sens", "gen_phish", "sensitivity"), ("spec", "original_core_neg", "gen_spec", "gen_legit", "specificity")]):
        for det, s in ref_cells():
            x, y = P.at[(det, s, xm, xc), "value"], P.at[(det, s, ym, yc), "value"]
            col = COLOR.get(det, GREY)
            ax.plot(x, y, marker="o" if det in COLOR else ("D" if det == "ensemble" else "s"), color=col, ms=6, ls="")
            ax.annotate(NAME[det], (x, y), fontsize=6.5, xytext=(4, -2), textcoords="offset points", color="#333333")
        ax.plot([0, 1], [0, 1], color="#bbbbbb", lw=0.8, ls=":")
        ax.set_xlim(0, 1.02); ax.set_ylim(0, 1.02)
        ax.set_xlabel(f"core {lab} (originals)"); ax.set_ylabel(f"generalisation {lab} (E-PhishLLM)")
    return save_fig(fig, "f7_generalisation")


def main() -> int:
    M = pd.read_csv(SCORES / "metrics_long.csv"); D = pd.read_csv(SCORES / "deltas_long.csv"); C = pd.read_csv(SCORES / "contrasts.csv")
    cues_f = pd.read_csv(SCORES / "cues_frequency.csv"); cues_c = pd.read_csv(SCORES / "cues_change.csv"); cues_p = pd.read_csv(SCORES / "cues_pairs.csv")
    hc_sum = pd.read_csv(SCORES / "hardcore_summary.csv"); ens_votes = pd.read_csv(SCORES / "ensemble_votes.csv"); F = pd.read_csv(SCORES / "frontier.csv")
    TABLES.mkdir(parents=True, exist_ok=True)
    tabs = tables(M, D, C, cues_f, cues_c, cues_p, hc_sum, ens_votes, F)
    for name, tex in tabs.items():
        write_text(TABLES / name, tex)
    figs = [fig_f1(M), fig_f2(D), fig_f3(M), fig_f4(D), fig_f5(F), fig_f6(cues_c), fig_f7(M)]
    report = {"tables": {n: sha256_file(TABLES / n) for n in tabs}, "figures": {f: sha256_file(FIGS / f) for f in figs},
              "inputs": {n: sha256_file(SCORES / n) for n in ("metrics_long.csv", "deltas_long.csv", "contrasts.csv", "cues_frequency.csv",
                                                               "cues_change.csv", "hardcore_summary.csv", "ensemble_votes.csv", "frontier.csv")},
              "matplotlib": matplotlib.__version__, "palette": PALETTE, "git_commit": git("rev-parse", "--short", "HEAD")}
    write_json(REPORT, report)
    print(f"{len(tabs)} tables -> results/tables/; {len(figs)} figures -> figures/: {', '.join(figs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
