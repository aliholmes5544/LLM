#!/usr/bin/env python3
"""
05b_calibrate_variants.py — final dev-set statistics of the meaning checks (Section 3.2.3).

Two runs of scripts/05_derive_variants.py are involved and are kept apart:

  * the PROVISIONAL run (cosine 0.80, NLI 0.70) on which the thresholds were chosen. Its score-based
    analyses (threshold calibration, false rejection per automatic test, cosine-only exclusions) are
    taken verbatim from reports/variants_calibration_provisional.json, the committed output of this
    script on that run, and the label-based parts of them are recomputed from the *_prov /
    *_cp1256 columns of the sample as a consistency check;
  * the FROZEN run (cosine 0.68, NLI 0.70) whose accepted bodies are the ones in
    data/processed/variants_dev.jsonl. Inter-rater agreement, the residual error among accepted
    items (Wilson 95 % interval), the per-condition failure rates and the readability statistics
    are computed from the current columns of reports/manual_review_sample_dev.csv as merged by
    scripts/05a_merge_ratings.py --readability (obfuscated rows re-rated from clean text, the
    paraphrases whose accepted body changed re-rated on the new body, three of them appended).

Human label = rating_majority (label given by at least two raters; "split" rows are counted and
left out of the label-based analyses). Agreement: pairwise percent agreement, Cohen's kappa and
PABAK (2 p_o - 1, Byrt et al., 1993), and Fleiss' kappa over the three raters. Readability (2 / 1 / 0)
of the obfuscated rows: distribution per condition and rater, agreement, and a flag when the majority
value is 0 for more than 10 % of a condition's rows.

Usage:  python scripts/05b_calibrate_variants.py [--selftest]
Input:  reports/manual_review_sample_dev.csv, data/processed/variants_dev.jsonl,
        reports/variants_dev_report.json, reports/variants_calibration_provisional.json
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
PROVISIONAL = REPORTS / "variants_calibration_provisional.json"
RATERS = ("A", "B", "C")
LABELS = ("preserved", "partly", "not")
READABILITY_LABELS = ("2", "1", "0")
TESTS = ("cosine", "nli", "length", "spans", "fraction")
ACCEPTED = ("pass", "regenerated")
OBF_CONDITIONS = ("obf_low", "obf_high")
UNREADABLE_FLAG = 0.10          # flag a condition when majority readability 0 exceeds this share


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


def majority(values: list) -> str:
    top, n = Counter(values).most_common(1)[0]
    return top if n >= 2 else "split"


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


# ---- frozen-run analyses (current columns) ---------------------------------------
def labelled(rows: list) -> list:
    return [r for r in rows if r["rating_majority"] in LABELS]


def per_condition(sample: list) -> dict:
    out = {}
    for c in sorted({r["condition"] for r in sample}):
        rs = labelled([r for r in sample if r["condition"] == c])
        k_not = sum(r["rating_majority"] == "not" for r in rs)
        out[c] = {"n": len(rs), "not": rate_ci(k_not, len(rs)),
                  "not_preserved": rate_ci(sum(r["rating_majority"] != "preserved" for r in rs), len(rs)),
                  "review_whole_condition": bool(rs) and k_not / len(rs) > 0.05,
                  "labels": dict(Counter(r["rating_majority"] for r in rs))}
    return out


def residual(rows: list, population: dict = None) -> dict:
    """Share of accepted items (pass + regenerated) whose human label is not 'preserved'."""
    rs = labelled([r for r in rows if r["auto_outcome"] in ACCEPTED])
    out = {"not_preserved": rate_ci(sum(r["rating_majority"] != "preserved" for r in rs), len(rs)),
           "not": rate_ci(sum(r["rating_majority"] == "not" for r in rs), len(rs)),
           "labels": dict(Counter(r["rating_majority"] for r in rs)),
           "by_auto_outcome": {o: {"n": sum(r["auto_outcome"] == o for r in rs),
                                   "labels": dict(Counter(r["rating_majority"] for r in rs if r["auto_outcome"] == o))}
                               for o in ACCEPTED},
           "not_preserved_ids": [r["variant_id"] for r in rs if r["rating_majority"] != "preserved"]}
    if population:
        w_num, w_den = 0.0, 0
        for c in sorted({r["condition"] for r in rs}):
            for o in ACCEPTED:
                ro = [r for r in rs if r["condition"] == c and r["auto_outcome"] == o]
                n_pop = population.get(c, {}).get(o, 0)
                if ro and n_pop:
                    w_num += n_pop * sum(r["rating_majority"] != "preserved" for r in ro) / len(ro)
                    w_den += n_pop
        out["not_preserved_population_weighted"] = {
            "rate": round(w_num / w_den, 4) if w_den else None, "population_accepted": w_den,
            "weights": {c: {o: population.get(c, {}).get(o, 0) for o in ACCEPTED} for c in sorted({r["condition"] for r in rs})}}
    return out


def readability_stats(obf: list) -> dict:
    rated = [r for r in obf if all(r[f"readability_{x}"] in READABILITY_LABELS for x in RATERS)]
    if not obf or len(rated) < len(obf):
        return {"status": f"pending ({len(rated)}/{len(obf)} obfuscated rows rated by all three raters)"}
    out = {"status": "rated", "scale": {"2": "reads normally", "1": "noticeably odd but every word readable",
                                        "0": "at least one word unrecognisable"},
           "agreement": agreement(rated, "readability", READABILITY_LABELS, "readability_majority"), "per_condition": {}}
    for c in OBF_CONDITIONS:
        rs = [r for r in rated if r["condition"] == c]
        maj = [r for r in rs if r["readability_majority"] in READABILITY_LABELS]
        unreadable = rate_ci(sum(r["readability_majority"] == "0" for r in maj), len(maj))
        out["per_condition"][c] = {
            "n": len(rs),
            "per_rater": {x: {k: sum(r[f"readability_{x}"] == k for r in rs) for k in READABILITY_LABELS} for x in RATERS},
            "majority": {k: sum(r["readability_majority"] == k for r in rs) for k in READABILITY_LABELS},
            "n_split": sum(r["readability_majority"] == "split" for r in rs),
            "unreadable_word (majority 0)": unreadable,
            "odd_or_worse (majority 1 or 0)": rate_ci(sum(r["readability_majority"] in ("1", "0") for r in maj), len(maj)),
            "flag_unreadable_above_10pct": bool(maj) and unreadable["rate"] > UNREADABLE_FLAG}
    return out


def obfuscation_rerating(obf: list) -> dict:
    """Meaning ratings of the obfuscated rows from clean text versus the first round (cp1256 display)."""
    out = {"n": len(obf), "changed_per_rater": {}, "majority_clean": dict(Counter(r["rating_majority"] for r in obf))}
    for x in RATERS:
        out["changed_per_rater"][x] = sum(r[f"rating_{x}"] != r[f"rating_{x}_cp1256"] for r in obf)
    out["majority_cp1256"] = dict(Counter(majority([r[f"rating_{x}_cp1256"] for x in RATERS]) for r in obf))
    return out


# ---- provisional-run analyses (carried over + consistency check) ------------------
def provisional_view(sample: list) -> list:
    """The sample as it was in the provisional run: superseded outcomes, bodies' first-round ratings
    (rating_*_prov for the re-rated paraphrases, rating_*_cp1256 for the obfuscated rows); rows that
    were not in the first-round sample are dropped."""
    out = []
    for r in sample:
        p = dict(r)
        p["auto_outcome"] = r["auto_outcome_prov"] or r["auto_outcome"]
        p["failed_tests"] = r["failed_tests_prov"] if r["auto_outcome_prov"] else r["failed_tests"]
        for x in RATERS:
            if r[f"rating_{x}_prov"]:
                p[f"rating_{x}"] = r[f"rating_{x}_prov"]
            elif r[f"rating_{x}_cp1256"] not in ("", "n/a"):
                p[f"rating_{x}"] = r[f"rating_{x}_cp1256"]
        p["rating_majority"] = majority([p[f"rating_{x}"] for x in RATERS])
        out.append(p)
    return out


def first_round_rows(sample: list) -> list:
    """Rows of the provisional view that belonged to the first-round sample (appended rows excluded)."""
    view = provisional_view(sample)
    appended = {r["variant_id"] for r in sample
                if r["auto_outcome_prov"] and r["variant_body_prov"] == "" and r["rating_A_prov"] == ""
                and r["variant_id"] in PARA_CHANGED_IDS}
    return [r for r in view if r["variant_id"] not in appended]


PARA_CHANGED_IDS = None          # filled from 05a at import time (single source of truth)


def provisional_block(sample: list, prov: dict) -> dict:
    """Score-based analyses copied from the provisional report; label-based parts recomputed from the
    *_prov / *_cp1256 columns and compared with it."""
    rows = first_round_rows(sample)
    para = [r for r in rows if r["condition"].startswith("para")]
    checks = {}
    # (a) per-condition label counts
    pc = per_condition(rows)
    checks["per_condition_labels"] = all(pc[c]["labels"] == prov["per_condition"][c]["labels"] for c in pc)
    # (b) false rejection, final exclusion by a single test
    fr = {}
    for t in TESTS:
        rs = labelled([r for r in para if r["auto_outcome"] == "excluded" and r["failed_tests"] == t])
        fr[t] = rate_ci(sum(r["rating_majority"] == "preserved" for r in rs), len(rs))
    checks["false_rejection_final_alone"] = all(
        (fr[t]["k"], fr[t]["n"]) == (prov["false_rejection_by_test"][t]["final_alone"]["k"], prov["false_rejection_by_test"][t]["final_alone"]["n"])
        for t in TESTS)
    # (c) cosine-only exclusions' human labels
    lab = {r["variant_id"]: r["rating_majority"] for r in para}
    checks["cosine_only_labels"] = all(lab.get(d["variant_id"]) == d["human_label"] for d in prov["cosine_only_exclusions"])
    # (d) residual error and agreement in the provisional view
    res = residual(para)
    checks["residual_error_paraphrase"] = (res["not_preserved"]["k"], res["not_preserved"]["n"]) == (
        prov["residual_error_accepted"]["paraphrase"]["not_preserved"]["k"], prov["residual_error_accepted"]["paraphrase"]["not_preserved"]["n"])
    agr = agreement(rows, "rating", LABELS, "rating_majority")
    checks["agreement_all"] = agr["pairwise"] == prov["agreement"]["all"]["pairwise"]
    return {"source": str(PROVISIONAL.relative_to(ROOT)), "thresholds": {"thr_cos": 0.80, "thr_nli": 0.70},
            "n_sample": prov["n_sample"], "n_paraphrase_preserved": prov["n_paraphrase_preserved"],
            "chosen": prov["chosen"], "grid_cos": prov["grid_cos"], "grid_nli": prov["grid_nli"],
            "false_rejection_by_test": prov["false_rejection_by_test"],
            "excluded_by_failed_tests": prov["excluded_by_failed_tests"],
            "cosine_only_exclusions": prov["cosine_only_exclusions"],
            "agreement": prov["agreement"], "per_condition": prov["per_condition"],
            "residual_error_accepted": prov["residual_error_accepted"],
            "recomputed_from_prov_columns": {"n_rows": len(rows), "false_rejection_final_alone": fr,
                                             "residual_error_paraphrase": res["not_preserved"],
                                             "agreement_all_pairwise": agr["pairwise"]},
            "consistency": checks, "consistent": all(checks.values())}


# ---- inputs -----------------------------------------------------------------------
def load_inputs() -> tuple:
    global PARA_CHANGED_IDS
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("m05a", ROOT / "scripts" / "05a_merge_ratings.py")
    m05a = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m05a)
    PARA_CHANGED_IDS = set(m05a.PARA_CHANGED)

    with open_utf8(REPORTS / "manual_review_sample_dev.csv") as fh:
        sample = list(csv.DictReader(fh))
    need = [f"rating_{x}" for x in RATERS] + ["rating_majority"]
    missing = [c for c in need + ["rating_A_prov", "auto_outcome_prov", "readability_A"] if c not in sample[0]]
    if missing:
        raise SystemExit(f"columns {missing} missing: run scripts/05a_merge_ratings.py --readability first")
    unrated = [r["variant_id"] for r in sample if not all(r[c].strip() for c in need)]
    if unrated:
        raise SystemExit(f"{len(unrated)} sample rows are not rated by all three raters yet, e.g. {unrated[:3]}")
    bad = [r["variant_id"] for r in sample
           if any(r[f"rating_{x}"].strip().lower() not in LABELS for x in RATERS) or r["rating_majority"] not in LABELS + ("split",)]
    if bad:
        raise SystemExit(f"ratings must be one of {LABELS}; offending rows: {bad[:5]}")
    for r in sample:
        for c in r:
            r[c] = r[c].strip()
        for x in RATERS:
            r[f"rating_{x}"] = r[f"rating_{x}"].lower()

    variants, population = {}, {}
    for line in open_utf8(PROC / "variants_dev.jsonl"):
        v = json.loads(line)
        variants[v["variant_id"]] = v
        if "attempt_0" in v["checks"]:
            population.setdefault(v["condition"], Counter())[v["status"]] += 1
    # the sample must describe the bodies and statuses of the frozen run
    for r in sample:
        v = variants[r["variant_id"]]
        if r["variant_body"].strip() != v["body"].strip():
            raise SystemExit(f"{r['variant_id']}: sample body differs from data/processed/variants_dev.jsonl")
        if r["auto_outcome"] != v["status"]:
            raise SystemExit(f"{r['variant_id']}: sample auto_outcome {r['auto_outcome']} differs from the current status {v['status']}")
    dev_report = json.loads((REPORTS / "variants_dev_report.json").read_text(encoding="utf-8"))
    if not PROVISIONAL.exists():
        raise SystemExit(f"{PROVISIONAL.relative_to(ROOT)} missing: the committed calibration of the provisional run is required")
    prov = json.loads(PROVISIONAL.read_text(encoding="utf-8"))
    return sample, {c: dict(n) for c, n in population.items()}, dev_report["thresholds"], prov


def selftest() -> int:
    ok = True
    ok &= abs(cohen_kappa(["a", "a", "b", "b"], ["a", "a", "b", "b"]) - 1.0) < 1e-9
    ok &= abs(cohen_kappa(["a", "b", "a", "b"], ["a", "a", "b", "b"]) - 0.0) < 1e-9
    ok &= abs(pabak(["a", "b", "a", "b"], ["a", "a", "b", "b"]) - 0.0) < 1e-9
    ok &= abs(pabak(["a", "a", "a", "b"], ["a", "a", "a", "a"]) - 0.5) < 1e-9
    ok &= abs(fleiss_kappa([["a", "a", "a"], ["b", "b", "b"]], ("a", "b", "c")) - 1.0) < 1e-9
    ok &= abs(fleiss_kappa([["a", "b", "c"], ["a", "b", "c"]], ("a", "b", "c")) - (-0.5)) < 1e-9
    # Fleiss (1971) worked example (Wikipedia, Table 1): kappa = 0.210
    fl = [[0, 0, 0, 0, 14], [0, 2, 6, 4, 2], [0, 0, 3, 5, 6], [0, 3, 9, 2, 0], [2, 2, 8, 1, 1], [7, 7, 0, 0, 0],
          [3, 2, 6, 3, 0], [2, 5, 3, 2, 2], [6, 5, 2, 1, 0], [0, 2, 2, 3, 7]]
    ok &= abs(fleiss_kappa([[str(j) for j, n in enumerate(row) for _ in range(n)] for row in fl], tuple("01234")) - 0.2099) < 5e-4
    lo, hi = wilson(1, 10)
    ok &= 0.0 < lo < 0.1 < hi < 0.5
    ok &= wilson(0, 20)[0] == 0.0 and wilson(0, 20)[1] < 0.17
    ok &= majority(["a", "a", "b"]) == "a" and majority(["a", "b", "c"]) == "split"
    rows = [{"rating_A": "preserved", "rating_B": "preserved", "rating_C": "partly", "rating_majority": "preserved"},
            {"rating_A": "not", "rating_B": "not", "rating_C": "not", "rating_majority": "not"}]
    a = agreement(rows, "rating", LABELS, "rating_majority")
    ok &= a["pairwise"]["AB"]["percent_agreement"] == 1.0 and a["pairwise"]["AC"]["percent_agreement"] == 0.5
    ok &= a["n_unanimous"] == 1 and a["n_split"] == 0
    obf = [{"condition": "obf_low", "readability_A": "0", "readability_B": "0", "readability_C": "1", "readability_majority": "0"}] + \
          [{"condition": "obf_low", "readability_A": "1", "readability_B": "1", "readability_C": "2", "readability_majority": "1"}] * 4 + \
          [{"condition": "obf_high", "readability_A": "2", "readability_B": "2", "readability_C": "2", "readability_majority": "2"}] * 3
    rd = readability_stats(obf)
    ok &= rd["per_condition"]["obf_low"]["flag_unreadable_above_10pct"] and not rd["per_condition"]["obf_high"]["flag_unreadable_above_10pct"]
    ok &= rd["per_condition"]["obf_low"]["unreadable_word (majority 0)"]["k"] == 1
    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def fmt_rate(d: dict) -> str:
    if d["n"] == 0:
        return "n=0"
    return f"{d['k']}/{d['n']} = {d['rate']:.1%}  CI95 [{d['ci95'][0]:.1%}, {d['ci95'][1]:.1%}]"


def print_agreement(agree: dict) -> None:
    for grp, a in agree.items():
        pw = "  ".join(f"{p}: agree {s['percent_agreement']:.1%} kappa {s['cohen_kappa']:.3f} PABAK {s['pabak']:.3f}"
                       for p, s in a["pairwise"].items())
        print(f"{grp:12s} n={a['n']:3d}  unanimous {a['n_unanimous']:3d}  split {a['n_split']}  Fleiss {a['fleiss_kappa']:.3f}  |  {pw}")
        print(f"{'':12s} per rater {a['per_rater']}  majority {a['majority']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    sample, population, thresholds, prov = load_inputs()
    para = [r for r in sample if r["condition"].startswith("para")]
    obf = [r for r in sample if r["condition"] in OBF_CONDITIONS]
    frozen = {"thresholds": thresholds, "n_sample": len(sample), "n_paraphrase": len(para), "n_obfuscation": len(obf),
              "n_split": sum(r["rating_majority"] == "split" for r in sample),
              "rows_rerated_on_new_body": sorted(r["variant_id"] for r in sample if r["rating_A_prov"]),
              "rows_appended": sorted(r["variant_id"] for r in sample if r["auto_outcome_prov"] and not r["rating_A_prov"]
                                      and r["variant_id"] in PARA_CHANGED_IDS),
              "rows_status_changed_body_unchanged": sorted(r["variant_id"] for r in sample if r["auto_outcome_prov"]
                                                           and r["variant_id"] not in PARA_CHANGED_IDS),
              "by_auto_outcome": dict(Counter((r["condition"], r["auto_outcome"]) for r in sample)),
              "agreement": {"all": agreement(sample, "rating", LABELS, "rating_majority"),
                            "paraphrase": agreement(para, "rating", LABELS, "rating_majority"),
                            "obfuscation": agreement(obf, "rating", LABELS, "rating_majority")},
              "per_condition": per_condition(sample),
              "residual_error_accepted": {"paraphrase": residual(para, population), "obfuscation": residual(obf),
                                          "all": residual(sample)},
              "obfuscation_meaning_clean_vs_cp1256": obfuscation_rerating(obf),
              "readability": readability_stats(obf)}
    frozen["by_auto_outcome"] = {f"{c}/{o}": n for (c, o), n in sorted(frozen["by_auto_outcome"].items())}
    result = {"human_label": "rating_majority (label given by at least two of three raters; 'split' rows excluded)",
              "provisional_run": provisional_block(sample, prov), "frozen_run": frozen}
    write_json(REPORTS / "variants_calibration.json", result)

    p, f = result["provisional_run"], result["frozen_run"]
    print("=" * 100)
    print(f"PROVISIONAL RUN (cosine {p['thresholds']['thr_cos']}, NLI {p['thresholds']['thr_nli']}; n={p['n_sample']}) "
          f"from {p['source']}  | consistency with *_prov columns: {p['consistency']}")
    print("=" * 100)
    ch = p["chosen"]
    print(f"thresholds: thr_cos {ch['thr_cos']} (pass rate of preserved {ch['cos']['pass_rate']:.1%}, target met {ch['cos']['target_met']}), "
          f"thr_nli {ch['thr_nli']} (grid bound: {ch['nli']['at_grid_bound']}; not adopted, see caveat)  "
          f"preserved paraphrases {p['n_paraphrase_preserved']}")
    print("false rejection per automatic test (share labelled preserved among items the test alone rejected):")
    for t in TESTS:
        fr = p["false_rejection_by_test"][t]
        fa = fr["first_attempt_alone"]
        print(f"  {t:9s} final exclusion: {fmt_rate(fr['final_alone']):42s}" + (f" first attempt: {fmt_rate(fa)}" if fa else ""))
    print(f"  {'any':9s} final exclusion: {fmt_rate(p['false_rejection_by_test']['any_excluded'])}")
    print("cosine-only exclusions:")
    for d in p["cosine_only_exclusions"]:
        print(f"  {d['variant_id']:22s} cos {d['sim_cos']:.4f}  nli_min {d['nli_min']:.3f}  A/B/C {d['rating_A']}/{d['rating_B']}/{d['rating_C']} -> {d['human_label']}")
    r = p["residual_error_accepted"]["paraphrase"]["not_preserved"]
    print(f"residual error among accepted paraphrases (provisional bodies): {fmt_rate(r)}")

    print("\n" + "=" * 100)
    print(f"FROZEN RUN (cosine {f['thresholds']['thr_cos']}, NLI {f['thresholds']['thr_nli']}; n={f['n_sample']}: "
          f"{f['n_paraphrase']} paraphrase, {f['n_obfuscation']} obfuscation; split {f['n_split']})")
    print("=" * 100)
    print(f"re-rated on new body: {f['rows_rerated_on_new_body']}\nappended: {f['rows_appended']}\n"
          f"status changed, body unchanged: {f['rows_status_changed_body_unchanged']}\nby outcome: {f['by_auto_outcome']}")
    print("\n== inter-rater agreement (meaning, current ratings) ==")
    print_agreement(f["agreement"])
    print("\n== residual error among accepted items (pass + regenerated under the frozen thresholds) ==")
    for grp, s in f["residual_error_accepted"].items():
        print(f"{grp:12s} not preserved {fmt_rate(s['not_preserved']):42s} strictly not {fmt_rate(s['not'])}")
        print(f"{'':12s} by outcome {s['by_auto_outcome']}  ids {s['not_preserved_ids']}")
    popw = f["residual_error_accepted"]["paraphrase"]["not_preserved_population_weighted"]
    print(f"{'':12s} paraphrase reweighted to population {popw['weights']}: {popw['rate']:.1%}")
    print("\n== per condition (majority label) ==")
    for c, s in f["per_condition"].items():
        flag = "  <-- review whole condition" if s["review_whole_condition"] else ""
        print(f"{c:10s} n={s['n']:3d}  not: {fmt_rate(s['not']):40s} not preserved: {fmt_rate(s['not_preserved'])}{flag}")
    o = f["obfuscation_meaning_clean_vs_cp1256"]
    print(f"\n== obfuscated rows, meaning from clean text vs first round == changed per rater {o['changed_per_rater']}; "
          f"majority clean {o['majority_clean']} vs cp1256 {o['majority_cp1256']}")
    rd = f["readability"]
    print(f"\n== readability (obfuscated rows) == {rd['status']}")
    if rd["status"] == "rated":
        a = rd["agreement"]
        pw = "  ".join(f"{p}: agree {s['percent_agreement']:.1%} kappa {s['cohen_kappa']:.3f} PABAK {s['pabak']:.3f}"
                       for p, s in a["pairwise"].items())
        print(f"{'':10s} n={a['n']}  unanimous {a['n_unanimous']}  split {a['n_split']}  Fleiss {a['fleiss_kappa']:.3f}  |  {pw}")
        for c, s in rd["per_condition"].items():
            flag = "  <-- majority 0 above 10 %" if s["flag_unreadable_above_10pct"] else ""
            print(f"{c:10s} n={s['n']}  majority 2/1/0 = {s['majority']['2']}/{s['majority']['1']}/{s['majority']['0']}  "
                  f"per rater {s['per_rater']}")
            print(f"{'':10s} unreadable word {fmt_rate(s['unreadable_word (majority 0)'])}   "
                  f"odd or worse {fmt_rate(s['odd_or_worse (majority 1 or 0)'])}{flag}")

    print("\n--- lines for docs/CHANGES_FOR_THESIS.md ---")
    a = f["agreement"]["all"]
    print(f"- Section 3.2.3 inter-rater agreement on the final sample (n={a['n']}): Fleiss' kappa {a['fleiss_kappa']}; pairwise "
          "percent agreement " + ", ".join(f"{p} {s['percent_agreement']:.1%}" for p, s in a["pairwise"].items())
          + "; PABAK " + ", ".join(f"{p} {s['pabak']:.2f}" for p, s in a["pairwise"].items()) + ".")
    r = f["residual_error_accepted"]["paraphrase"]["not_preserved"]
    print(f"- Residual error among paraphrases accepted under the frozen thresholds: {r['k']}/{r['n']} not fully preserved "
          f"({r['rate']:.1%}, 95% CI {r['ci95'][0]:.1%}-{r['ci95'][1]:.1%}); population-weighted {popw['rate']:.1%}.")
    for c, s in f["per_condition"].items():
        print(f"- {c}: manual-sample failure rate {s['not']['rate']:.1%} (95% CI {s['not']['ci95'][0]:.1%}-{s['not']['ci95'][1]:.1%}, n={s['n']}).")
    if rd["status"] == "rated":
        for c, s in rd["per_condition"].items():
            print(f"- {c} readability (majority 2/1/0): {s['majority']['2']}/{s['majority']['1']}/{s['majority']['0']} of {s['n']}; "
                  f"unreadable word {fmt_rate(s['unreadable_word (majority 0)'])}.")
    print(f"\nwritten to {(REPORTS / 'variants_calibration.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
