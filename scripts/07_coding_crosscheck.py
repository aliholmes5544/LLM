#!/usr/bin/env python3
"""
07_coding_crosscheck.py — read-only cross-check of the author's hard-core coding against the TASK_08 indicator
extractions (TASK_07 section 4c and TASK_08; QUESTIONS.md items 12c, 17 and 18; docs/HARDCORE_CODING_GUIDE.md).

Reads the filled coding workbook (reports/hardcore_coding.xlsx, sheet "coding"; sheet "review" when present) and
reports/hardcore_sample.csv (38 rows), then joins every coded item, and for a variant also its original, with the
stage-1 indicators extracted by the three TASK_08 models (results/raw/twostage_<model>/extract/eval.jsonl). For each
code the extraction is compared with the coder's reading by one fixed rule:

  paraphrase_cue_dropped   link_or_url goes yes (original) -> no (variant)
  paraphrase_softened      urgency goes yes (original) -> no or unclear (variant)
  paraphrase_neutral       none of the eight threat indicators changes between original and variant
  no_call_to_action        link_or_url and credential_or_payment_request are both no on the item
  personalised_pretext     descriptive only: the mean number of threat indicators asserted ("yes") on the item
  placeholder_artifact     descriptive only, as above

Counts are given out of n coded rows per model; the rows where the extraction does not meet the rule are listed as
disagreements. The script writes reports/hardcore_coding_crosscheck.json and prints a summary. It writes nothing
else: the workbook, the sample CSV and every frozen file stay untouched, and the coding is NOT imported
(scripts/07_import_coding.py does that).

Usage: python scripts/07_coding_crosscheck.py [--xlsx reports/hardcore_coding.xlsx] [--out reports/hardcore_coding_crosscheck.json]
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import yaml
from openpyxl import load_workbook

from common import ROOT, open_utf8, write_json
from scoring.hardcore_codes import codes_for

XLSX = ROOT / "reports" / "hardcore_coding.xlsx"
SAMPLE = ROOT / "reports" / "hardcore_sample.csv"
TWOSTAGE_CFG = ROOT / "configs" / "twostage.yaml"
OUT = ROOT / "reports" / "hardcore_coding_crosscheck.json"

RULES = {   # code -> (short name of the rule, needs the original, description)
    "paraphrase_cue_dropped": ("link_or_url_yes_to_no", True, "link_or_url is yes on the original and no on the variant"),
    "paraphrase_softened": ("urgency_drops", True, "urgency is yes on the original and no or unclear on the variant"),
    "paraphrase_neutral": ("no_threat_indicator_changes", True, "all eight threat indicators are identical on original and variant"),
    "no_call_to_action": ("link_and_credential_both_no", False, "link_or_url and credential_or_payment_request are both no on the item"),
    "personalised_pretext": (None, False, "descriptive only: mean number of threat indicators asserted (yes) on the item"),
    "placeholder_artifact": (None, False, "descriptive only: mean number of threat indicators asserted (yes) on the item"),
}
NO_RULE = (None, False, "no rule defined for this code")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def original_of(item_id: str) -> str:
    """The source item of a variant id (`<item>#<condition>`); an original is its own source."""
    return item_id.split("#", 1)[0]


def read_sheet(wb, name: str) -> list:
    rows = list(wb[name].iter_rows(values_only=True))
    header = [str(h) for h in rows[0]]
    return [dict(zip(header, list(r) + [None] * (len(header) - len(r))))
            for r in rows[1:] if any(v not in (None, "") for v in r)]


def read_coding(path: Path) -> tuple:
    """(coding rows, review rows or []) from the workbook; values are stripped strings."""
    wb = load_workbook(path, read_only=True, data_only=True)
    if "coding" not in wb.sheetnames:
        raise SystemExit(f"{path}: no sheet named 'coding'")

    def clean(rows):
        return [{k: (str(v).strip() if v is not None else "") for k, v in r.items()} for r in rows]

    coding = clean(read_sheet(wb, "coding"))
    review = clean(read_sheet(wb, "review")) if "review" in wb.sheetnames else []
    return coding, review


def check_against_sample(coding: list, sample: pd.DataFrame) -> list:
    """Every workbook row must match the sample (sample_id, item_id, condition) and carry a code valid for its type."""
    by_id = {int(r["sample_id"]): r for _, r in sample.iterrows()}
    problems = []
    for r in coding:
        sid = int(r["sample_id"])
        s = by_id.get(sid)
        if s is None:
            problems.append(f"sample_id {sid}: not in {SAMPLE.name}")
            continue
        if r["item_id"] != s["item_id"] or r["stratum"] != s["condition"]:
            problems.append(f"sample_id {sid}: item_id/stratum differ from {SAMPLE.name}")
        if not r["failure_type"]:
            problems.append(f"sample_id {sid}: failure_type empty")
        elif r["failure_type"] not in codes_for(s["condition"]):
            problems.append(f"sample_id {sid}: code {r['failure_type']!r} is not a {s['condition']} code")
    if len(coding) != len(sample):
        problems.append(f"{len(coding)} workbook rows, {len(sample)} sample rows")
    return problems


def load_extractions(model: str, cfg: dict) -> tuple:
    """(item_id -> indicators dict, or None on a parse failure; file record) for one extraction model."""
    path = ROOT / "results" / "raw" / f"{cfg['model_prefix']}{model}" / cfg["extract_key"] / "eval.jsonl"
    if not path.exists():
        raise SystemExit(f"{path.relative_to(ROOT)} missing")
    ind, hashes, n = {}, set(), 0
    with open_utf8(path) as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            n += 1
            ind[r["item_id"]] = r["indicators"] if r.get("parse_ok") else None
            hashes.add(r["config_hash"])
    return ind, {"file": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "n_rows": n,
                 "config_hash": sorted(hashes)}


def n_asserted(ind: dict, threat: list) -> int:
    return sum(1 for k in threat if ind[k] == "yes")


def threat_changes(orig: dict, var: dict, threat: list) -> list:
    return [{"indicator": k, "original": orig[k], "variant": var[k]} for k in threat if orig[k] != var[k]]


def rule_result(code: str, item: dict, orig, threat: list):
    """True / False for a code with a rule, None for a descriptive code."""
    if code == "paraphrase_cue_dropped":
        return orig["link_or_url"] == "yes" and item["link_or_url"] == "no"
    if code == "paraphrase_softened":
        return orig["urgency"] == "yes" and item["urgency"] in ("no", "unclear")
    if code == "paraphrase_neutral":
        return not threat_changes(orig, item, threat)
    if code == "no_call_to_action":
        return item["link_or_url"] == "no" and item["credential_or_payment_request"] == "no"
    return None


def row_detail(code: str, item: dict, orig, threat: list) -> dict:
    """The indicator values the rule looks at, for the per-row listing."""
    d = {"n_threat_asserted": n_asserted(item, threat), "asserted": [k for k in threat if item[k] == "yes"]}
    if orig is not None:
        d["n_threat_asserted_original"] = n_asserted(orig, threat)
        d["threat_changes"] = threat_changes(orig, item, threat)
    if code == "paraphrase_cue_dropped":
        d["link_or_url"] = {"original": orig["link_or_url"], "variant": item["link_or_url"]}
    elif code == "paraphrase_softened":
        d["urgency"] = {"original": orig["urgency"], "variant": item["urgency"]}
    elif code == "no_call_to_action":
        d["link_or_url"] = item["link_or_url"]
        d["credential_or_payment_request"] = item["credential_or_payment_request"]
    return d


def crosscheck(coding: list, extractions: dict, threat: list) -> tuple:
    """(per_code, rows, disagreements): counts per code and model, the joined rows, and the disagreeing rows."""
    rows, disagreements = [], []
    for r in coding:
        code, item_id = r["failure_type"], r["item_id"]
        is_variant = "#" in item_id
        rule, needs_orig, _ = RULES.get(code, NO_RULE)
        row = {"sample_id": int(r["sample_id"]), "set": r["set"], "stratum": r["stratum"], "item_id": item_id,
               "failure_type": code, "models": {}}
        for model, ind in extractions.items():
            item = ind.get(item_id, "missing")
            orig = ind.get(original_of(item_id), "missing") if is_variant else None
            if item == "missing" or orig == "missing":
                raise SystemExit(f"{model}: no extraction row for {item_id} or its original")
            if item is None or (is_variant and orig is None):
                row["models"][model] = {"parse_failure": True}
                continue
            applicable = rule is not None and (is_variant or not needs_orig)
            res = rule_result(code, item, orig, threat) if applicable else None
            det = row_detail(code, item, orig, threat)
            det["rule_met"] = res
            row["models"][model] = det
            if res is False:
                disagreements.append({"sample_id": row["sample_id"], "item_id": item_id, "stratum": r["stratum"],
                                      "failure_type": code, "model": model, "rule": rule,
                                      "extraction": {k: v for k, v in det.items() if k != "rule_met"}})
        rows.append(row)
    per_code = {}
    for code in sorted({r["failure_type"] for r in coding}):
        rule, needs_orig, desc = RULES.get(code, NO_RULE)
        code_rows = [x for x in rows if x["failure_type"] == code]
        pm = {}
        for model in extractions:
            valid = [x["models"][model] for x in code_rows if not x["models"][model].get("parse_failure")]
            met = [x for x in valid if x["rule_met"] is True]
            mean = lambda key: round(sum(x[key] for x in valid) / len(valid), 3) if valid else None
            entry = {"n": len(code_rows), "n_valid": len(valid), "mean_threat_indicators_asserted": mean("n_threat_asserted")}
            if rule is not None:
                entry["count_rule_met"] = len(met)
                entry["fraction_rule_met"] = round(len(met) / len(valid), 3) if valid else None
                entry["disagreeing_sample_ids"] = [x["sample_id"] for x in code_rows
                                                   if x["models"][model].get("rule_met") is False]
            if needs_orig:
                entry["mean_threat_indicators_asserted_original"] = mean("n_threat_asserted_original")
            pm[model] = entry
        per_code[code] = {"rule": rule, "description": desc, "n": len(code_rows),
                          "sample_ids": [x["sample_id"] for x in code_rows], "per_model": pm}
    return per_code, rows, disagreements


def review_agreement(coding: list, review: list) -> dict:
    """How the final code compares with the reviewer_code of sheet 'review' (the author's own re-review)."""
    if not review:
        return {"present": False}
    rv = {int(r["sample_id"]): r for r in review}
    same = [int(r["sample_id"]) for r in coding if rv.get(int(r["sample_id"]), {}).get("reviewer_code") == r["failure_type"]]
    differ = [int(r["sample_id"]) for r in coding if int(r["sample_id"]) in rv and int(r["sample_id"]) not in same]
    verdicts = Counter(r["reviewer_verdict"] for r in review)
    return {"present": True, "n_review_rows": len(review), "final_code_equals_reviewer_code": len(same),
            "differ_sample_ids": differ, "reviewer_verdicts": dict(sorted(verdicts.items()))}


def print_summary(per_code: dict, disagreements: list, models: list) -> None:
    print(f"{'code':24s} {'rule':30s} {'n':>3s}  " + "  ".join(f"{m:>12s}" for m in models))
    for code, c in per_code.items():
        cells = []
        for m in models:
            e = c["per_model"][m]
            cells.append(f"{e['count_rule_met']}/{e['n_valid']}" if c["rule"] else f"mean {e['mean_threat_indicators_asserted']}")
        print(f"{code:24s} {str(c['rule']):30s} {c['n']:3d}  " + "  ".join(f"{x:>12s}" for x in cells))
    print(f"disagreements (row x model): {len(disagreements)}")
    skip = ("n_threat_asserted", "n_threat_asserted_original", "asserted")
    for d in disagreements:
        print(f"  row {d['sample_id']:2d} {d['stratum']:9s} {d['failure_type']:24s} {d['model']:11s} "
              + json.dumps({k: v for k, v in d["extraction"].items() if k not in skip}))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default=str(XLSX))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    xlsx = Path(a.xlsx)
    cfg = yaml.safe_load(open_utf8(TWOSTAGE_CFG).read())
    threat = list(cfg["indicators"]["threat"])
    coding, review = read_coding(xlsx)
    sample = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    problems = check_against_sample(coding, sample)
    if problems:
        print("\n".join(problems))
        return 1
    extractions, files = {}, {}
    for model in cfg["models"]:
        extractions[model], files[model] = load_extractions(model, cfg)
    per_code, rows, disagreements = crosscheck(coding, extractions, threat)
    report = {
        "script": "scripts/07_coding_crosscheck.py",
        "purpose": "read-only cross-check of the hard-core coding against the TASK_08 stage-1 indicator extractions; "
                   "the coding is not imported and nothing frozen changes",
        "inputs": {"coding_xlsx": {"file": str(xlsx.relative_to(ROOT)), "sha256": sha256_file(xlsx)},
                   "sample_csv": {"file": str(SAMPLE.relative_to(ROOT)), "sha256": sha256_file(SAMPLE)},
                   "extractions": files, "threat_indicators": threat},
        "n_rows": len(coding),
        "codes": dict(sorted(Counter(r["failure_type"] for r in coding).items())),
        "codes_by_stratum": {s: dict(sorted(Counter(r["failure_type"] for r in coding if r["stratum"] == s).items()))
                             for s in sorted({r["stratum"] for r in coding})},
        "review_sheet": review_agreement(coding, review),
        "rules": {k: {"rule": v[0], "uses_original": v[1], "description": v[2]} for k, v in RULES.items()},
        "per_code": per_code,
        "n_disagreements": len(disagreements),
        "disagreements": disagreements,
        "rows": rows,
    }
    write_json(Path(a.out), report)
    print_summary(per_code, disagreements, cfg["models"])
    print(f"written {Path(a.out).relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
