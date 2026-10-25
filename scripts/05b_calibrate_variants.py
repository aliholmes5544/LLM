#!/usr/bin/env python3
"""
05b_calibrate_variants.py — calibrate the meaning checks against the three-rater dev sample (Section 3.2.3).

Reads reports/manual_review_sample_dev.csv as merged by scripts/05a_merge_ratings.py (rating_A/B/C,
rating_majority; readability_A/B/C and readability_majority for the obfuscated rows once rated) and
data/processed/variants_dev.jsonl for the automatic scores of the same variants.

  * Inter-rater agreement, overall and per family: pairwise percent agreement, Cohen's kappa and
    PABAK (2 p_o - 1, Byrt et al., 1993) for each pair of raters, and Fleiss' kappa over the three.
  * Human label = rating_majority (label given by at least two raters); "split" rows are counted and
    left out of the label-based analyses.
  * thr_cos / thr_nli: the highest grid value at which at least 95% of the paraphrases labelled
    "preserved" still pass (the 5th percentile of their scores rounded down to the grid).
  * For each automatic test (cosine, NLI, length, protected spans, achieved fraction): the
    false-rejection rate against the human label among the items that test alone rejected, both as
    the final decision (excluded with that test as the only failed test) and at the first attempt
    (flagged by that test only, whatever happened after the retry; the rating refers to the final
    body, so a "preserved" there shows the retry repaired the variant, not that the flag was wrong).
  * Every cosine-only exclusion with its cosine (and the other scores) beside the human label.
  * Residual error among accepted items (auto_outcome pass or regenerated): share whose human label
    is not "preserved", with a Wilson 95% interval, plus the strict "not" share and an estimate
    reweighted to the population counts of pass / regenerated variants.
  * Sample failure rate per condition (majority "not") with a Wilson 95% interval; conditions above
    5% are flagged for full review (a manual gate, not automated here).
  * Readability (2 / 1 / 0) agreement and distribution for the obfuscated rows, when rated.

The YAML snippet for configs/variants.yaml and the lines for docs/CHANGES_FOR_THESIS.md are
printed for the author to paste; the config is deliberately not rewritten by the script.

Usage:  python scripts/05b_calibrate_variants.py [--selftest]
Output: reports/variants_calibration.json
"""
import argparse
import csv
import json
import math
import sys
from collections import Counter
from itertools import combinations

from common import ROOT, open_utf8, write_json

PROC = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
GRID_COS = [round(0.60 + 0.01 * i, 2) for i in range(36)]      # 0.60 .. 0.95
GRID_NLI = [round(0.50 + 0.01 * i, 2) for i in range(41)]      # 0.50 .. 0.90
RATERS = ("A", "B", "C")
LABELS = ("preserved", "partly", "not")
READABILITY_LABELS = ("2", "1", "0")
TESTS = ("cosine", "nli", "length", "spans", "fraction")
ACCEPTED = ("pass", "regenerated")


# ---- statistics ---------------------------------------------------------------
def percent_agreement(a: list, b: list) -> float:
    return sum(x == y for x, y in zip(a, b)) / len(a) if a else float("nan")


def cohen_kappa(a: list, b: list) -> float:
    """Cohen's kappa (Cohen, 1960) for two raters over the same items."""
    n = len(a)
    if n == 0:
        return float("nan")
    po = percent_agreement(a, b)
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def pabak(a: list, b: list) -> float:
    """Prevalence- and bias-adjusted kappa (Byrt, Bishop & Carlin, 1993): 2 p_o - 1."""
    return 2 * percent_agreement(a, b) - 1 if a else float("nan")


def fleiss_kappa(ratings: list, categories: tuple) -> float:
    """Fleiss' kappa (Fleiss, 1971): `ratings` is one list of labels per item, all of equal length."""
    n_items = len(ratings)
    if n_items == 0:
        return float("nan")
    n_raters = len(ratings[0])
    counts = [Counter(r) for r in ratings]
    p_j = [sum(c[k] for c in counts) / (n_items * n_raters) for k in categories]
    p_i = [(sum(c[k] ** 2 for k in categories) - n_raters) / (n_raters * (n_raters - 1)) for c in counts]
    p_bar, pe = sum(p_i) / n_items, sum(p * p for p in p_j)
    return 1.0 if pe == 1 else (p_bar - pe) / (1 - pe)


def wilson(k: int, n: int, z: float = 1.959964) -> tuple:
    """Wilson score interval for a proportion k/n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def rate_ci(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "rate": round(k / n, 4) if n else None,
            "ci95": [round(lo, 4), round(hi, 4)] if n else None}


def pick_threshold(scores: list, grid: list, target: float = 0.95) -> dict:
    """Highest grid value at which >= target of `scores` are still >= the value. Falls back to the grid
    minimum, flagged target_met False, when no grid value reaches the target; a value on either grid
    bound is flagged so the grid can be extended rather than read as a calibrated optimum."""
    best, met = grid[0], False
    for t in grid:
        if sum(s >= t for s in scores) / len(scores) >= target:
            best, met = t, True
    return {"value": best, "target_met": met, "pass_rate": round(sum(s >= best for s in scores) / len(scores), 4),
            "at_grid_bound": best in (grid[0], grid[-1]), "grid": [grid[0], grid[-1]]}


def agreement(rows: list, prefix: str, categories: tuple, majority_col: str) -> dict:
    """Pairwise agreement statistics for the three raters plus Fleiss' kappa over `rows`."""
    cols = {r: f"{prefix}_{r}" for r in RATERS}
    out = {"n": len(rows), "pairwise": {}, "per_rater": {r: dict(Counter(x[cols[r]] for x in rows)) for r in RATERS},
           "majority": dict(Counter(x[majority_col] for x in rows)),
           "n_split": sum(x[majority_col] == "split" for x in rows),
           "n_unanimous": sum(len({x[cols[r]] for r in RATERS}) == 1 for x in rows)}
    for r1, r2 in combinations(RATERS, 2):
        a = [x[cols[r1]] for x in rows]
        b = [x[cols[r2]] for x in rows]
        out["pairwise"][r1 + r2] = {"percent_agreement": round(percent_agreement(a, b), 4),
                                    "cohen_kappa": round(cohen_kappa(a, b), 4), "pabak": round(pabak(a, b), 4)}
    out["fleiss_kappa"] = round(fleiss_kappa([[x[cols[r]] for r in RATERS] for x in rows], categories), 4)
    return out


# ---- calibration ---------------------------------------------------------------
def calibrate(sample: list, variants: dict, population: dict) -> dict:
    fam = lambda r: variants[r["variant_id"]]["family"]
    para = [r for r in sample if fam(r) == "paraphrase"]
    obf = [r for r in sample if fam(r) == "obfuscation"]
    lab = lambda rs: [r for r in rs if r["rating_majority"] in LABELS]          # drop "split" rows

    preserved = [variants[r["variant_id"]] for r in lab(para) if r["rating_majority"] == "preserved"]
    if not preserved:
        raise SystemExit("no paraphrase row has majority label 'preserved'; cannot calibrate")
    pick_cos = pick_threshold([v["sim_cos"] for v in preserved], GRID_COS)
    pick_nli = pick_threshold([v["nli_min"] for v in preserved], GRID_NLI)
    thr_cos, thr_nli = pick_cos["value"], pick_nli["value"]
    joint = sum(v["sim_cos"] >= thr_cos and v["nli_min"] >= thr_nli and v["len_ok"] and v["spans_ok"] for v in preserved)
    grid = [{"thr_cos": c, "pass_rate": round(sum(v["sim_cos"] >= c for v in preserved) / len(preserved), 4)} for c in GRID_COS]
    grid_n = [{"thr_nli": t, "pass_rate": round(sum(v["nli_min"] >= t for v in preserved) / len(preserved), 4)} for t in GRID_NLI]

    agree = {"all": agreement(sample, "rating", LABELS, "rating_majority"),
             "paraphrase": agreement(para, "rating", LABELS, "rating_majority"),
             "obfuscation": agreement(obf, "rating", LABELS, "rating_majority")}

    per_condition = {}
    for c in sorted({r["condition"] for r in sample}):
        rs = lab([r for r in sample if r["condition"] == c])
        k_not = sum(r["rating_majority"] == "not" for r in rs)
        k_np = sum(r["rating_majority"] != "preserved" for r in rs)
        per_condition[c] = {"n": len(rs), "not": rate_ci(k_not, len(rs)), "not_preserved": rate_ci(k_np, len(rs)),
                            "review_whole_condition": bool(rs) and k_not / len(rs) > 0.05,
                            "labels": dict(Counter(r["rating_majority"] for r in rs))}

    # false rejection per automatic test, among the items that test alone rejected
    def label_block(rs: list) -> dict:
        rs = lab(rs)
        return {**rate_ci(sum(r["rating_majority"] == "preserved" for r in rs), len(rs)),
                "labels": dict(Counter(r["rating_majority"] for r in rs)),
                "variant_ids": [r["variant_id"] for r in rs]}
    false_rejection = {}
    for t in TESTS:
        final_alone = [r for r in para if r["auto_outcome"] == "excluded" and r["failed_tests"] == t]
        first_alone = [r for r in para if variants[r["variant_id"]]["attempt0_failed"] == {t}]
        false_rejection[t] = {"final_alone": label_block(final_alone),
                              "first_attempt_alone": None if t == "fraction" else label_block(first_alone)}
    false_rejection["any_excluded"] = label_block([r for r in para if r["auto_outcome"] == "excluded"])
    by_failed = {}
    for combo in sorted({r["failed_tests"] for r in para if r["auto_outcome"] == "excluded"}):
        by_failed[combo or "(none)"] = label_block([r for r in para if r["auto_outcome"] == "excluded" and r["failed_tests"] == combo])

    cosine_only = []
    for r in para:
        if r["auto_outcome"] == "excluded" and r["failed_tests"] == "cosine":
            v = variants[r["variant_id"]]
            cosine_only.append({"variant_id": r["variant_id"], "condition": r["condition"], "sim_cos": v["sim_cos"],
                                "nli_min": v["nli_min"], "len_ratio": v["len_ratio"], "achieved_fraction": v["achieved_fraction"],
                                "rating_A": r["rating_A"], "rating_B": r["rating_B"], "rating_C": r["rating_C"],
                                "human_label": r["rating_majority"],
                                "notes": {x: r[f"notes_{x}"] for x in RATERS if r.get(f"notes_{x}")}})
    cosine_only.sort(key=lambda d: d["sim_cos"])

    # residual error among accepted items (pass + regenerated), by family and outcome
    def residual(rs: list) -> dict:
        rs = lab([r for r in rs if r["auto_outcome"] in ACCEPTED])
        out = {"not_preserved": rate_ci(sum(r["rating_majority"] != "preserved" for r in rs), len(rs)),
               "not": rate_ci(sum(r["rating_majority"] == "not" for r in rs), len(rs)),
               "labels": dict(Counter(r["rating_majority"] for r in rs)), "by_auto_outcome": {}}
        for o in ACCEPTED:
            ro = [r for r in rs if r["auto_outcome"] == o]
            out["by_auto_outcome"][o] = {"n": len(ro), "labels": dict(Counter(r["rating_majority"] for r in ro))}
        return out
    residual_error = {"paraphrase": residual(para), "obfuscation": residual(obf), "all": residual(sample)}
    # reweight the paraphrase estimate to the population shares of pass / regenerated variants
    w_num, w_den = 0.0, 0
    for c in sorted({r["condition"] for r in para}):
        for o in ACCEPTED:
            rs = lab([r for r in para if r["condition"] == c and r["auto_outcome"] == o])
            n_pop = population.get(c, {}).get(o, 0)
            if rs and n_pop:
                w_num += n_pop * sum(r["rating_majority"] != "preserved" for r in rs) / len(rs)
                w_den += n_pop
    residual_error["paraphrase"]["not_preserved_population_weighted"] = {
        "rate": round(w_num / w_den, 4) if w_den else None, "population_accepted": w_den,
        "weights": {c: {o: population.get(c, {}).get(o, 0) for o in ACCEPTED} for c in sorted({r["condition"] for r in para})}}

    by_outcome = {o: {"n": sum(r["auto_outcome"] == o for r in para),
                      "labels": dict(Counter(r["rating_majority"] for r in para if r["auto_outcome"] == o))}
                  for o in ("pass", "regenerated", "excluded")}

    rated = [r for r in obf if all(r.get(f"readability_{x}", "") in READABILITY_LABELS for x in RATERS)]
    if obf and len(rated) == len(obf):
        readability = {"status": "rated", "agreement": agreement(rated, "readability", READABILITY_LABELS, "readability_majority"),
                       "per_condition": {}}
        for c in sorted({r["condition"] for r in rated}):
            rs = [r for r in rated if r["condition"] == c and r["readability_majority"] in READABILITY_LABELS]
            readability["per_condition"][c] = {
                "n": len(rs), "majority": dict(Counter(r["readability_majority"] for r in rs)),
                "unreadable_word (0)": rate_ci(sum(r["readability_majority"] == "0" for r in rs), len(rs)),
                "odd_or_worse (1 or 0)": rate_ci(sum(r["readability_majority"] in ("1", "0") for r in rs), len(rs))}
    else:
        readability = {"status": f"pending ({len(rated)}/{len(obf)} obfuscated rows rated by all three raters)"}

    return {"human_label": "rating_majority (label given by at least two of three raters; 'split' rows excluded)",
            "n_sample": len(sample), "n_paraphrase": len(para), "n_obfuscation": len(obf),
            "n_split": sum(r["rating_majority"] == "split" for r in sample),
            "n_paraphrase_preserved": len(preserved),
            "chosen": {"thr_cos": thr_cos, "thr_nli": thr_nli, "joint_pass_rate_preserved": round(joint / len(preserved), 4),
                       "cos": pick_cos, "nli": pick_nli,
                       "caveat_nli": "nli_min is the minimum over the retained sentences of the final body; sentences below "
                                     "the provisional 0.70 were already reverted by the fallback, so the preserved items' "
                                     "nli_min is censored at the provisional threshold and cannot calibrate a lower one"},
            "grid_cos": grid, "grid_nli": grid_n, "agreement": agree, "per_condition": per_condition,
            "false_rejection_by_test": false_rejection, "excluded_by_failed_tests": by_failed,
            "cosine_only_exclusions": cosine_only, "residual_error_accepted": residual_error,
            "paraphrase_by_auto_outcome": by_outcome, "readability": readability}


def load_inputs() -> tuple:
    with open_utf8(REPORTS / "manual_review_sample_dev.csv") as fh:
        sample = list(csv.DictReader(fh))
    need = [f"rating_{x}" for x in RATERS] + ["rating_majority"]
    missing = [c for c in need if c not in sample[0]]
    if missing:
        raise SystemExit(f"columns {missing} missing: run scripts/05a_merge_ratings.py first")
    unrated = [r["variant_id"] for r in sample if not all(r[c].strip() for c in need)]
    if unrated:
        raise SystemExit(f"{len(unrated)} sample rows are not rated by all three raters yet, e.g. {unrated[:3]}")
    bad = [r["variant_id"] for r in sample
           if any(r[f"rating_{x}"].strip().lower() not in LABELS for x in RATERS) or r["rating_majority"] not in LABELS + ("split",)]
    if bad:
        raise SystemExit(f"ratings must be one of {LABELS}; offending rows: {bad[:5]}")
    for r in sample:
        for x in RATERS:
            r[f"rating_{x}"] = r[f"rating_{x}"].strip().lower()
            r[f"readability_{x}"] = r.get(f"readability_{x}", "").strip()
        r["readability_majority"] = r.get("readability_majority", "").strip()

    variants, population = {}, {}
    for line in open_utf8(PROC / "variants_dev.jsonl"):
        v = json.loads(line)
        ch = v["checks"]
        if "attempt_0" in ch:
            a0, fin = ch["attempt_0"], ch[f"attempt_{ch['final_attempt']}"]
            flagged = set()
            if not a0["sim_ok"]:
                flagged.add("cosine")
            if not a0["len_ok"]:
                flagged.add("length")
            if not a0["spans_ok"] or any(not s["spans_ok"] for s in a0["sentences"]):
                flagged.add("spans")
            if any(not s["nli_ok"] for s in a0["sentences"]):
                flagged.add("nli")
            variants[v["variant_id"]] = {"family": "paraphrase", "sim_cos": fin["sim_cos"], "nli_min": fin["nli_min"],
                                         "len_ratio": fin["len_ratio"], "len_ok": fin["len_ok"], "spans_ok": fin["spans_ok"],
                                         "achieved_fraction": ch["achieved_fraction"], "attempt0_failed": flagged}
            population.setdefault(v["condition"], Counter())[v["status"]] += 1
        else:
            variants[v["variant_id"]] = {"family": "obfuscation", "attempt0_failed": set()}
    return sample, variants, {c: dict(n) for c, n in population.items()}


def selftest() -> int:
    ok = True
    ok &= abs(cohen_kappa(["a", "a", "b", "b"], ["a", "a", "b", "b"]) - 1.0) < 1e-9
    ok &= abs(cohen_kappa(["a", "b", "a", "b"], ["a", "a", "b", "b"]) - 0.0) < 1e-9
    ok &= abs(pabak(["a", "b", "a", "b"], ["a", "a", "b", "b"]) - 0.0) < 1e-9
    ok &= abs(pabak(["a", "a", "a", "b"], ["a", "a", "a", "a"]) - 0.5) < 1e-9
    ok &= abs(fleiss_kappa([["a", "a", "a"], ["b", "b", "b"]], ("a", "b", "c")) - 1.0) < 1e-9
    ok &= abs(fleiss_kappa([["a", "b", "c"], ["a", "b", "c"]], ("a", "b", "c")) - (-0.5)) < 1e-9
    # Fleiss (1971) worked example, Table 1 of the Wikipedia article: kappa = 0.210
    fl = [[0, 0, 0, 0, 14], [0, 2, 6, 4, 2], [0, 0, 3, 5, 6], [0, 3, 9, 2, 0], [2, 2, 8, 1, 1], [7, 7, 0, 0, 0],
          [3, 2, 6, 3, 0], [2, 5, 3, 2, 2], [6, 5, 2, 1, 0], [0, 2, 2, 3, 7]]
    ok &= abs(fleiss_kappa([[str(j) for j, n in enumerate(row) for _ in range(n)] for row in fl], tuple("01234")) - 0.2099) < 5e-4
    lo, hi = wilson(1, 10)
    ok &= 0.0 < lo < 0.1 < hi < 0.5
    ok &= wilson(0, 20)[0] == 0.0 and wilson(0, 20)[1] < 0.17
    pk = pick_threshold([0.9, 0.85, 0.8, 0.75, 0.95] * 20, GRID_COS)
    ok &= pk["value"] == 0.75 and pk["target_met"] and not pk["at_grid_bound"]
    pk = pick_threshold([0.5, 0.5, 0.9], GRID_COS)
    ok &= pk["value"] == GRID_COS[0] and not pk["target_met"] and pk["at_grid_bound"]
    rows = [{"rating_A": "preserved", "rating_B": "preserved", "rating_C": "partly", "rating_majority": "preserved"},
            {"rating_A": "not", "rating_B": "not", "rating_C": "not", "rating_majority": "not"}]
    a = agreement(rows, "rating", LABELS, "rating_majority")
    ok &= a["pairwise"]["AB"]["percent_agreement"] == 1.0 and a["pairwise"]["AC"]["percent_agreement"] == 0.5
    ok &= a["n_unanimous"] == 1 and a["n_split"] == 0
    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def fmt_rate(d: dict) -> str:
    if d["n"] == 0:
        return "n=0"
    return f"{d['k']}/{d['n']} = {d['rate']:.1%}  CI95 [{d['ci95'][0]:.1%}, {d['ci95'][1]:.1%}]"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    sample, variants, population = load_inputs()
    result = calibrate(sample, variants, population)
    write_json(REPORTS / "variants_calibration.json", result)

    ch = result["chosen"]
    print(f"sample: {result['n_sample']} rows ({result['n_paraphrase']} paraphrase, {result['n_obfuscation']} obfuscation); "
          f"human label = majority of three raters; split rows: {result['n_split']}")
    print("\n== inter-rater agreement (meaning) ==")
    for grp, a in result["agreement"].items():
        pw = "  ".join(f"{p}: agree {s['percent_agreement']:.1%} kappa {s['cohen_kappa']:.3f} PABAK {s['pabak']:.3f}"
                       for p, s in a["pairwise"].items())
        print(f"{grp:12s} n={a['n']:3d}  unanimous {a['n_unanimous']:3d}  Fleiss {a['fleiss_kappa']:.3f}  |  {pw}")
        print(f"{'':12s} per rater {a['per_rater']}  majority {a['majority']}")
    print("\n== thresholds ==")
    print(f"preserved paraphrases (majority): {result['n_paraphrase_preserved']} / {result['n_paraphrase']}")
    print(f"chosen: thr_cos {ch['thr_cos']}  thr_nli {ch['thr_nli']}  (joint pass rate of preserved {ch['joint_pass_rate_preserved']:.1%})")
    for name in ("cos", "nli"):
        p = ch[name]
        note = []
        if not p["target_met"]:
            note.append("95% target NOT met at any grid value")
        if p["at_grid_bound"]:
            note.append(f"value is on the grid bound {p['grid']}")
        print(f"  {name}: pass rate of preserved at chosen value {p['pass_rate']:.1%}" + (f"  <-- {'; '.join(note)}" if note else ""))
    print(f"  caveat: {ch['caveat_nli']}")
    print("\n== false rejection per automatic test (share labelled preserved among items the test alone rejected) ==")
    for t in TESTS:
        fr = result["false_rejection_by_test"][t]
        fa = fr["first_attempt_alone"]
        print(f"{t:9s} final exclusion: {fmt_rate(fr['final_alone']):42s} {fr['final_alone']['labels']}")
        if fa is not None:
            print(f"{'':9s} first attempt:   {fmt_rate(fa):42s} {fa['labels']}")
    print(f"{'any':9s} final exclusion: {fmt_rate(result['false_rejection_by_test']['any_excluded'])}")
    print("\n== cosine-only exclusions ==")
    for d in result["cosine_only_exclusions"]:
        print(f"{d['variant_id']:22s} cos {d['sim_cos']:.4f}  nli_min {d['nli_min']:.3f}  len {d['len_ratio']:.2f}  "
              f"frac {d['achieved_fraction']:.2f}  A/B/C {d['rating_A']}/{d['rating_B']}/{d['rating_C']}  -> {d['human_label']}"
              + (f"  {d['notes']}" if d["notes"] else ""))
    print("\n== residual error among accepted items (pass + regenerated) ==")
    for grp, s in result["residual_error_accepted"].items():
        print(f"{grp:12s} not preserved {fmt_rate(s['not_preserved']):42s} strictly not {fmt_rate(s['not'])}")
        print(f"{'':12s} by outcome {s['by_auto_outcome']}")
    pw = result["residual_error_accepted"]["paraphrase"]["not_preserved_population_weighted"]
    print(f"{'':12s} paraphrase, reweighted to population (pass/regenerated counts {pw['weights']}): "
          f"{pw['rate']:.1%}" if pw["rate"] is not None else "")
    print("\n== per condition (majority label) ==")
    for c, s in result["per_condition"].items():
        flag = "  <-- review whole condition" if s["review_whole_condition"] else ""
        print(f"{c:10s} n={s['n']:3d}  not: {fmt_rate(s['not']):40s} not preserved: {fmt_rate(s['not_preserved'])}{flag}")
    print(f"\n== readability (obfuscated rows) == {result['readability']['status']}")
    if result["readability"]["status"] == "rated":
        a = result["readability"]["agreement"]
        pw = "  ".join(f"{p}: agree {s['percent_agreement']:.1%} kappa {s['cohen_kappa']:.3f} PABAK {s['pabak']:.3f}"
                       for p, s in a["pairwise"].items())
        print(f"{'':12s} n={a['n']}  Fleiss {a['fleiss_kappa']:.3f}  |  {pw}")
        for c, s in result["readability"]["per_condition"].items():
            print(f"{c:10s} majority {s['majority']}  unreadable word {fmt_rate(s['unreadable_word (0)'])}  "
                  f"odd or worse {fmt_rate(s['odd_or_worse (1 or 0)'])}")
    print("\n--- paste into configs/variants.yaml (thresholds:) ---")
    print(f"  thr_cos: {ch['thr_cos']}\n  thr_nli: {ch['thr_nli']}")
    print("\n--- lines for docs/CHANGES_FOR_THESIS.md ---")
    print(f"- Section 3.2.3 thresholds calibrated on dev: cosine >= {ch['thr_cos']}, NLI entailment >= {ch['thr_nli']} "
          f"(human label = majority of three raters).")
    a = result["agreement"]["all"]
    print(f"- Section 3.2.3 inter-rater agreement (n={a['n']}): Fleiss' kappa {a['fleiss_kappa']}; pairwise percent agreement "
          + ", ".join(f"{p} {s['percent_agreement']:.1%}" for p, s in a["pairwise"].items())
          + "; PABAK " + ", ".join(f"{p} {s['pabak']:.2f}" for p, s in a["pairwise"].items()) + ".")
    for c, s in result["per_condition"].items():
        print(f"- {c}: manual-sample failure rate {s['not']['rate']:.1%} (95% CI {s['not']['ci95'][0]:.1%}-{s['not']['ci95'][1]:.1%}, n={s['n']}).")
    r = result["residual_error_accepted"]["paraphrase"]["not_preserved"]
    print(f"- Residual error among accepted paraphrases: {r['k']}/{r['n']} not fully preserved "
          f"(95% CI {r['ci95'][0]:.1%}-{r['ci95'][1]:.1%}).")
    print(f"\nwritten to {(REPORTS / 'variants_calibration.json').relative_to(ROOT)}")
    print("NOTE: rerun scripts/05_derive_variants.py after updating the thresholds so statuses reflect them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
