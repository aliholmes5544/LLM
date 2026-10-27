#!/usr/bin/env python3
"""
05d_control_exclusion_diagnosis.py — diagnose the exclusions among the evaluation paraphrases and
record the fixed evaluation artifact (Section 3.2.3 control, Section 3.8 reproducibility).

Part 1, diagnosis (docs/QUESTIONS.md item 7). No threshold is changed and nothing is re-derived.
For ctrl_para_legit/para_high and, for comparison, core_pos/para_high, excluded variants are compared
with accepted ones (pass + regenerated) on: body length in words (records.jsonl n_words), number of
eligible sentences, source collection (enron_ham / hard_ham / other), protected spans per record,
truncated generations, variants whose body is identical to the original (no eligible sentence), and
the achieved_fraction distribution. Exclusion rates are also tabulated by
source collection, by body-length bin and by eligible-sentence bin. One arithmetic fact is checked
directly: with k eligible sentences and r reverted ones the achieved fraction is (k - r) / k, so a
body with fewer than 5 eligible sentences cannot tolerate a single reverted sentence under the 0.80
minimum of the high condition (k = 4 -> 0.75), and a body with 0 eligible sentences has fraction 0.

Part 2, fixed artifact (docs/QUESTIONS.md item 8). The derived variants file and the generation
cache are the fixed evaluation artifact: everything downstream is byte-reproducible from them
(run 2 of run_variants_eval.sh), generation itself is seeded but not bit-reproducible on the CPU
backend (cache spot check: 8 of 179 sampled sentences differed by 1-3 words). Their sha256, size and
row count are written to reports/variants_eval_fixed_artifacts.json and attached to
reports/variants_eval_report.json under "fixed_artifacts" (scripts/05_derive_variants.py re-attaches
the file on a rerun). The files are archived at submission under CC BY-NC-SA 4.0 (the licence of the
Nahmias et al., 2024, data they derive from); they are not committed to git.

Usage:  python scripts/05d_control_exclusion_diagnosis.py
Input:  data/processed/records.jsonl, data/processed/partitions.json, data/processed/variants_eval.jsonl,
        data/interim/paraphrase_cache_eval.jsonl, reports/variants_eval_report.json
Output: reports/control_exclusion_diagnosis.json, reports/variants_eval_fixed_artifacts.json,
        reports/variants_eval_report.json (key "fixed_artifacts" added)
"""
import hashlib
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

from common import ROOT, load_config, open_utf8, read_text, write_json

PROC = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
ECFG = load_config("variants_eval.yaml")
OUT_DIAG = REPORTS / "control_exclusion_diagnosis.json"
OUT_FIXED = REPORTS / "variants_eval_fixed_artifacts.json"
CONDITION = "para_high"
GROUPS = {"ctrl_para_legit": "control (paraphrased legitimate)", "core_pos": "spear-phishing originals"}
WORD_BINS = [(0, 49), (50, 99), (100, 199), (200, 399), (400, None)]
ELIG_BINS = [(0, 0), (1, 4), (5, 9), (10, 19), (20, None)]
MIN_FRACTION_HIGH = 0.8

DECISION = ("The derived variants file and the generation cache are the fixed evaluation artifact. "
            "Every step downstream of generation is byte-reproducible from them (run 2 of "
            "run_variants_eval.sh reproduced run 1 byte-identically from the cache). Generation itself "
            "is seeded but not bit-reproducible on the CPU backend: in the cache spot check 8 of 179 "
            "sampled sentences differed by 1-3 words. Both files are archived at submission under "
            "CC BY-NC-SA 4.0, the licence of the Nahmias et al. (2024) data they derive from; they are "
            "not committed to git.")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def count_lines(path: Path) -> int:
    return sum(1 for _ in open_utf8(path))


def bin_label(value: int, bins: list) -> str:
    for lo, hi in bins:
        if value >= lo and (hi is None or value <= hi):
            return f"{lo}+" if hi is None else (f"{lo}" if lo == hi else f"{lo}-{hi}")
    return "?"


def quantile(sorted_values: list, q: float) -> float:
    if not sorted_values:
        return None
    pos = q * (len(sorted_values) - 1)
    lo, hi = int(pos), min(int(pos) + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def describe(values: list, digits: int = 4) -> dict:
    """min / p25 / median / p75 / max / mean of a numeric list (None for an empty list)."""
    if not values:
        return {"n": 0}
    s = sorted(values)
    return {"n": len(s), "min": round(s[0], digits), "p25": round(quantile(s, 0.25), digits),
            "median": round(statistics.median(s), digits), "p75": round(quantile(s, 0.75), digits),
            "max": round(s[-1], digits), "mean": round(statistics.fmean(s), digits)}


def fraction_histogram(values: list) -> dict:
    edges = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)]
    hist = {f"{lo}-{hi}": 0 for lo, hi in edges}
    for v in values:
        for lo, hi in edges:
            if lo <= v < hi or (hi == 1.0 and v == 1.0):
                hist[f"{lo}-{hi}"] += 1
                break
    return hist


def rate_table(items: list, key, order: list = None) -> dict:
    """Exclusion count / total / rate per value of key(item), in the given order (else sorted)."""
    totals, excluded = Counter(), Counter()
    for it in items:
        k = key(it)
        totals[k] += 1
        excluded[k] += it["excluded"]
    out = {}
    for k in (k for k in order if k in totals) if order else sorted(totals):
        out[k] = {"n": totals[k], "excluded": excluded[k], "rate": round(excluded[k] / totals[k], 4)}
    return out


def group_summary(items: list) -> dict:
    """Describe one group (excluded or accepted) of (record, variant) items."""
    return {"n": len(items),
            "source_collection": dict(Counter(it["collection"] for it in items)),
            "body_words": describe([it["n_words"] for it in items], 1),
            "n_segments": describe([it["n_segments"] for it in items], 1),
            "n_eligible_sentences": describe([it["n_eligible"] for it in items], 1),
            "n_eligible_below_5": sum(it["n_eligible"] < 5 for it in items),
            "n_eligible_zero": sum(it["n_eligible"] == 0 for it in items),
            "protected_spans_per_record": describe([it["n_spans"] for it in items], 1),
            "n_reverted_sentences": describe([it["n_reverted"] for it in items], 1),
            "truncated_generations": {"variants_with_any": sum(it["truncated"] > 0 for it in items),
                                      "total": sum(it["truncated"] for it in items)},
            "body_identical_to_original": sum(it["body_unchanged"] for it in items),
            "first_attempt_cosine": describe([it["sim_cos_a0"] for it in items]),
            "achieved_fraction": {**describe([it["achieved_fraction"] for it in items]),
                                  "histogram": fraction_histogram([it["achieved_fraction"] for it in items])},
            "status": dict(Counter(it["status"] for it in items)),
            "failed_tests": dict(Counter(t for it in items for t in it["failed_tests"]))}


def diagnose(partition: str, items: list) -> dict:
    excluded = [it for it in items if it["excluded"]]
    accepted = [it for it in items if not it["excluded"]]
    fraction_only = [it for it in excluded if it["failed_tests"] == ["fraction"]]
    # (k - r) / k < 0.8  <=>  r > 0.2 k ; with k < 5 any r >= 1 excludes
    cannot_tolerate_one_revert = sum(it["n_eligible"] < 5 for it in fraction_only)
    explained_by_reverts = sum(round((it["n_eligible"] - it["n_reverted"]) / it["n_eligible"], 4) == it["achieved_fraction"]
                               for it in fraction_only if it["n_eligible"])
    return {"condition": CONDITION, "description": GROUPS[partition], "min_achieved_fraction": MIN_FRACTION_HIGH,
            "n_variants": len(items), "n_excluded": len(excluded), "exclusion_rate": round(len(excluded) / len(items), 4),
            "excluded": group_summary(excluded), "accepted": group_summary(accepted),
            "exclusion_rate_by_source_collection": rate_table(items, lambda it: it["collection"]),
            "exclusion_rate_by_body_words": rate_table(items, lambda it: bin_label(it["n_words"], WORD_BINS),
                                                       [bin_label(lo, WORD_BINS) for lo, _ in WORD_BINS]),
            "exclusion_rate_by_eligible_sentences": rate_table(items, lambda it: bin_label(it["n_eligible"], ELIG_BINS),
                                                               [bin_label(lo, ELIG_BINS) for lo, _ in ELIG_BINS]),
            "fraction_exclusions": {"n": len(fraction_only),
                                    "with_fewer_than_5_eligible_sentences": cannot_tolerate_one_revert,
                                    "with_zero_eligible_sentences": sum(it["n_eligible"] == 0 for it in fraction_only),
                                    "fraction_equals_(eligible-reverted)/eligible": explained_by_reverts,
                                    "reverted_sentences_total": sum(it["n_reverted"] for it in fraction_only)}}


def load_items() -> dict:
    parts = json.loads(read_text(PROC / "partitions.json"))
    wanted = {i for p in GROUPS for i in parts[p]}
    by_id = {}
    for line in open_utf8(PROC / "records.jsonl"):
        r = json.loads(line)
        if r["id"] in wanted:
            by_id[r["id"]] = r
    items = {p: [] for p in GROUPS}
    membership = {p: set(parts[p]) for p in GROUPS}
    for line in open_utf8(ROOT / ECFG["outputs"]["variants"]):
        v = json.loads(line)
        if v["condition"] != CONDITION:
            continue
        for p, ids in membership.items():
            if v["source_id"] in ids:
                break
        else:
            continue
        r, ch = by_id[v["source_id"]], v["checks"]
        sub = r["subclass"]
        items[p].append({"variant_id": v["variant_id"], "status": v["status"], "excluded": v["status"] == "excluded",
                         "collection": sub if sub in ("enron_ham", "hard_ham") else f"other ({sub})",
                         "n_words": r["n_words"], "n_segments": ch["n_segments"], "n_eligible": ch["n_eligible"],
                         "n_spans": len(ch["spans"]), "n_reverted": ch["n_reverted"], "truncated": ch["truncated"],
                         "sim_cos_a0": ch["attempt_0"]["sim_cos"], "achieved_fraction": ch["achieved_fraction"],
                         "failed_tests": list(ch["failed_tests"]), "body_unchanged": v["body"] == r["body"]})
    return items


def fixed_artifacts() -> dict:
    files = {}
    for key in ("variants", "cache"):
        p = ROOT / ECFG["outputs"][key]
        files[ECFG["outputs"][key]] = {"sha256": sha256_file(p), "bytes": p.stat().st_size, "rows": count_lines(p)}
    return {"decision": DECISION, "licence": "CC BY-NC-SA 4.0 (Nahmias et al., 2024)", "archived_at_submission": True,
            "in_git": False, "files": files}


def main() -> int:
    items = load_items()
    diag = {"question": "docs/QUESTIONS.md item 7", "thresholds_changed": False,
            "source": {"variants": ECFG["outputs"]["variants"], "report": ECFG["outputs"]["report"]},
            "word_bins": [bin_label(lo, WORD_BINS) for lo, _ in WORD_BINS],
            "eligible_sentence_bins": [bin_label(lo, ELIG_BINS) for lo, _ in ELIG_BINS],
            "partitions": {p: diagnose(p, its) for p, its in items.items()}}
    write_json(OUT_DIAG, diag)
    for p, d in diag["partitions"].items():
        print(f"{p}/{CONDITION}: {d['n_excluded']}/{d['n_variants']} excluded ({100 * d['exclusion_rate']:.1f} %)")
        for grp in ("excluded", "accepted"):
            g = d[grp]
            print(f"  {grp:8s} n {g['n']:3d}  words median {g['body_words'].get('median')}  eligible median "
                  f"{g['n_eligible_sentences'].get('median')}  eligible<5 {g['n_eligible_below_5']}  "
                  f"spans median {g['protected_spans_per_record'].get('median')}  truncated {g['truncated_generations']['total']}  "
                  f"fraction median {g['achieved_fraction'].get('median')}  {g['source_collection']}")
        print(f"  by collection {d['exclusion_rate_by_source_collection']}")
        print(f"  by eligible sentences {d['exclusion_rate_by_eligible_sentences']}")
        print(f"  by body words {d['exclusion_rate_by_body_words']}")
        print(f"  fraction exclusions {d['fraction_exclusions']}")
    print(f"diagnosis -> {OUT_DIAG.relative_to(ROOT)}")

    fixed = fixed_artifacts()
    write_json(OUT_FIXED, fixed)
    rpath = ROOT / ECFG["outputs"]["report"]
    full = json.loads(read_text(rpath))
    full["fixed_artifacts"] = fixed
    write_json(rpath, full)
    for path, f in fixed["files"].items():
        print(f"fixed artifact {path}: sha256 {f['sha256']}  {f['bytes']} bytes  {f['rows']} rows")
    print(f"fixed artifacts -> {OUT_FIXED.relative_to(ROOT)} and attached to {rpath.relative_to(ROOT)} (fixed_artifacts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
