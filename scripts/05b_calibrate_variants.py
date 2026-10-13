#!/usr/bin/env python3
"""
05b_calibrate_variants.py — choose the meaning-check thresholds from the rated dev sample (Section 3.2.3).

Reads reports/manual_review_sample_dev.csv after both annotators have filled rating_A and
rating_B (preserved | partly | not; readability_A/B for obfuscated rows: readable | partly | not)
and data/processed/variants_dev.jsonl for the automatic scores of the same variants.

  * thr_cos / thr_nli: the highest grid value at which at least 95% of the paraphrases rated
    "preserved" still pass (equivalently, the 5th percentile of their scores, rounded down to the
    grid). The joint pass rate at the chosen pair is reported as well.
  * Cohen's kappa between the two annotators, overall and per family.
  * Sample failure rate per condition with a Wilson 95% confidence interval; conditions above 5%
    are flagged for full review (a manual gate, not automated here).

The YAML snippet for configs/variants.yaml and the lines for docs/CHANGES_FOR_THESIS.md are
printed for the author to paste; the config is deliberately not rewritten by the script.

Usage:  python scripts/05b_calibrate_variants.py [--rule both|either] [--selftest]
Output: reports/variants_calibration.json
"""
import argparse
import csv
import json
import math
import sys
from collections import Counter

from common import ROOT, open_utf8, write_json

PROC = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
GRID_COS = [round(0.70 + 0.01 * i, 2) for i in range(26)]      # 0.70 .. 0.95
GRID_NLI = [round(0.50 + 0.01 * i, 2) for i in range(41)]      # 0.50 .. 0.90
LABELS = ("preserved", "partly", "not")


# ---- statistics ---------------------------------------------------------------
def cohen_kappa(a: list, b: list) -> float:
    """Cohen's kappa (Cohen, 1960) for two raters over the same items."""
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def wilson(k: int, n: int, z: float = 1.959964) -> tuple:
    """Wilson score interval for a proportion k/n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def verdict(ra: str, rb: str, rule: str) -> str:
    """Consensus label for one row: both/either annotators rate it 'preserved'; both 'not' -> not."""
    ra, rb = ra.strip().lower(), rb.strip().lower()
    if rule == "both":
        if ra == rb == "preserved":
            return "preserved"
    elif "preserved" in (ra, rb) and "not" not in (ra, rb):
        return "preserved"
    if ra == rb == "not":
        return "not"
    return "partly"


def pick_threshold(scores: list, grid: list, target: float = 0.95) -> float:
    """Highest grid value at which >= target of `scores` are still >= the value."""
    best = grid[0]
    for t in grid:
        if sum(s >= t for s in scores) / len(scores) >= target:
            best = t
    return best


# ---- calibration ---------------------------------------------------------------
def calibrate(sample_rows: list, variants: dict, rule: str) -> dict:
    para = [r for r in sample_rows if variants[r["variant_id"]]["family"] == "paraphrase"]
    obf = [r for r in sample_rows if variants[r["variant_id"]]["family"] == "obfuscation"]
    for r in sample_rows:
        r["verdict"] = verdict(r["rating_A"], r["rating_B"], rule)

    preserved = [variants[r["variant_id"]] for r in para if r["verdict"] == "preserved"]
    if not preserved:
        raise SystemExit("no paraphrase row is rated 'preserved' by both annotators; cannot calibrate")
    thr_cos = pick_threshold([v["sim_cos"] for v in preserved], GRID_COS)
    thr_nli = pick_threshold([v["nli_min"] for v in preserved], GRID_NLI)
    joint = sum(v["sim_cos"] >= thr_cos and v["nli_min"] >= thr_nli and v["len_ok"] and v["spans_ok"] for v in preserved)
    grid = [{"thr_cos": c, "pass_rate": round(sum(v["sim_cos"] >= c for v in preserved) / len(preserved), 4)} for c in GRID_COS]
    grid_n = [{"thr_nli": t, "pass_rate": round(sum(v["nli_min"] >= t for v in preserved) / len(preserved), 4)} for t in GRID_NLI]

    per_condition = {}
    for c in sorted({r["condition"] for r in sample_rows}):
        rs = [r for r in sample_rows if r["condition"] == c]
        k = sum(r["verdict"] == "not" for r in rs)
        lo, hi = wilson(k, len(rs))
        per_condition[c] = {"n": len(rs), "not_preserved": k, "failure_rate": round(k / len(rs), 4),
                            "ci95": [round(lo, 4), round(hi, 4)], "review_whole_condition": k / len(rs) > 0.05,
                            "verdicts": dict(Counter(r["verdict"] for r in rs))}

    kappa = {"all": round(cohen_kappa([r["rating_A"].strip().lower() for r in sample_rows],
                                      [r["rating_B"].strip().lower() for r in sample_rows]), 4)}
    for name, rs in (("paraphrase", para), ("obfuscation", obf)):
        if rs:
            kappa[name] = round(cohen_kappa([r["rating_A"].strip().lower() for r in rs],
                                            [r["rating_B"].strip().lower() for r in rs]), 4)
    readability = [r for r in obf if r.get("readability_A", "").strip() and r.get("readability_B", "").strip()]
    if readability:
        kappa["readability"] = round(cohen_kappa([r["readability_A"].strip().lower() for r in readability],
                                                 [r["readability_B"].strip().lower() for r in readability]), 4)

    return {"rule": rule, "n_sample": len(sample_rows), "n_paraphrase_preserved": len(preserved),
            "chosen": {"thr_cos": thr_cos, "thr_nli": thr_nli,
                       "joint_pass_rate_preserved": round(joint / len(preserved), 4)},
            "grid_cos": grid, "grid_nli": grid_n, "kappa": kappa, "per_condition": per_condition}


def load_inputs() -> tuple:
    with open_utf8(REPORTS / "manual_review_sample_dev.csv") as fh:
        sample = list(csv.DictReader(fh))
    unrated = [r["variant_id"] for r in sample if not (r["rating_A"].strip() and r["rating_B"].strip())]
    if unrated:
        raise SystemExit(f"{len(unrated)} sample rows are not rated by both annotators yet, e.g. {unrated[:3]}")
    bad = [r["variant_id"] for r in sample if r["rating_A"].strip().lower() not in LABELS or r["rating_B"].strip().lower() not in LABELS]
    if bad:
        raise SystemExit(f"ratings must be one of {LABELS}; offending rows: {bad[:5]}")
    variants = {}
    for line in open_utf8(PROC / "variants_dev.jsonl"):
        v = json.loads(line)
        ch = v["checks"]
        if "attempt_0" in ch:
            fin = ch[f"attempt_{ch['final_attempt']}"]
            variants[v["variant_id"]] = {"family": "paraphrase", "sim_cos": fin["sim_cos"], "nli_min": fin["nli_min"],
                                         "len_ok": fin["len_ok"], "spans_ok": fin["spans_ok"]}
        else:
            variants[v["variant_id"]] = {"family": "obfuscation"}
    return sample, variants


def selftest() -> int:
    ok = True
    k = cohen_kappa(["a", "a", "b", "b"], ["a", "a", "b", "b"])
    ok &= abs(k - 1.0) < 1e-9
    k = cohen_kappa(["a", "b", "a", "b"], ["a", "a", "b", "b"])
    ok &= abs(k - 0.0) < 1e-9
    lo, hi = wilson(1, 10)
    ok &= 0.0 < lo < 0.1 < hi < 0.5
    ok &= pick_threshold([0.9, 0.85, 0.8, 0.75, 0.95] * 20, GRID_COS) == 0.75
    ok &= verdict("preserved", "preserved", "both") == "preserved"
    ok &= verdict("preserved", "partly", "both") == "partly"
    ok &= verdict("preserved", "partly", "either") == "preserved"
    ok &= verdict("not", "not", "both") == "not"
    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--rule", choices=("both", "either"), default="both",
                    help="'preserved' requires both annotators (default) or either one")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    sample, variants = load_inputs()
    result = calibrate(sample, variants, args.rule)
    write_json(REPORTS / "variants_calibration.json", result)

    ch = result["chosen"]
    n_para = sum(1 for r in sample if variants[r["variant_id"]]["family"] == "paraphrase")
    print(f"preserved paraphrases in sample: {result['n_paraphrase_preserved']} / {n_para}")
    print(f"chosen thresholds: thr_cos {ch['thr_cos']}  thr_nli {ch['thr_nli']}  "
          f"(joint pass rate of preserved {ch['joint_pass_rate_preserved']:.1%})")
    print(f"Cohen's kappa: {result['kappa']}")
    for c, s in result["per_condition"].items():
        flag = "  <-- review whole condition" if s["review_whole_condition"] else ""
        print(f"{c:10s} n={s['n']:3d}  not preserved {s['not_preserved']}  rate {s['failure_rate']:.1%}  "
              f"CI95 [{s['ci95'][0]:.1%}, {s['ci95'][1]:.1%}]{flag}")
    print("\n--- paste into configs/variants.yaml (thresholds:) ---")
    print(f"  thr_cos: {ch['thr_cos']}\n  thr_nli: {ch['thr_nli']}")
    print("\n--- lines for docs/CHANGES_FOR_THESIS.md ---")
    print(f"- Section 3.2.3 thresholds calibrated on dev: cosine >= {ch['thr_cos']}, NLI entailment >= {ch['thr_nli']} "
          f"(rule: preserved = {args.rule} annotators).")
    for c, s in result["per_condition"].items():
        print(f"- {c}: manual-sample failure rate {s['failure_rate']:.1%} (95% CI {s['ci95'][0]:.1%}-{s['ci95'][1]:.1%}, n={s['n']}).")
    print(f"\nwritten to {(REPORTS / 'variants_calibration.json').relative_to(ROOT)}")
    print("NOTE: rerun scripts/05_derive_variants.py after updating the thresholds so statuses reflect them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
