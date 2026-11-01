#!/usr/bin/env python3
"""
07_freeze_lexicon.py — step 07, step 2 (TASK_07 sections 4b and 8; QUESTIONS.md item 12b): freeze the CoT
cue lexicon on dev and report how it behaves there.

Reads ONLY dev rationales: the six full-dev CoT cells results/raw/<model>/cot/dev.jsonl (tag v0.7.0-devcot)
and the dev smoke sets results/smoke_dev/*/cot.jsonl, results/smoke_gpu/*/cot.jsonl. Every row is asserted to
have partition == "dev" and strategy == "cot"; a path containing "eval" is refused. Applies the lexicon in
configs/cue_lexicon.yaml and writes reports/cue_lexicon_dev_report.json with the lexicon sha256, the input
hashes, per-category counts of rationales that mention / assert / negate the category (overall, per model,
per condition, per sub-pattern), the empty-rationale counts, and seeded example matches for the author's
review (3 asserted and 1 negated per category). No prediction is compared with its label: counts are by
model and condition only. --check recomputes everything and compares it with the report on disk.

Usage: python scripts/07_freeze_lexicon.py [--check]
"""
import argparse
import datetime as dt
import json
import random
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from common import ROOT, load_config, cot_rationale, write_json
from scoring.cues import CATEGORIES, load_lexicon, lexicon_sha256
from scoring.items import load_jsonl, sha256_file

LEXICON = ROOT / "configs" / "cue_lexicon.yaml"
REPORT = ROOT / "reports" / "cue_lexicon_dev_report.json"
MODELS = ("llama31-8b", "mistral-7b", "gemma2-9b", "qwen25-7b", "qwen25-14b", "gemma2-27b")
N_DEV_ROWS = 796
CONTEXT = 90


def git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def input_files() -> list:
    files = [ROOT / "results" / "raw" / m / "cot" / "dev.jsonl" for m in MODELS]
    for d in ("smoke_dev", "smoke_gpu"):
        files += sorted((ROOT / "results" / d).glob("*/cot.jsonl"))
    return files


def load_rows(files: list) -> tuple:
    rows, inputs = [], []
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        if "eval" in rel:
            raise SystemExit(f"refusing to read a non-dev file: {rel}")
        if not p.exists():
            raise SystemExit(f"missing dev input {rel}")
        rs = load_jsonl(p)
        for r in rs:
            if r.get("partition") != "dev" or r.get("strategy") != "cot":
                raise SystemExit(f"{rel}: row {r.get('item_id')} is not a dev cot row")
            r["_file"] = rel
        if rel.startswith("results/raw/") and len(rs) != N_DEV_ROWS:
            raise SystemExit(f"{rel}: {len(rs)} rows, expected {N_DEV_ROWS}")
        rows += rs
        inputs.append({"file": rel, "sha256": sha256_file(p), "n_rows": len(rs)})
    return rows, inputs


def excerpt(text: str, start: int, end: int) -> str:
    a, b = max(0, start - CONTEXT), min(len(text), end + CONTEXT)
    return ("..." if a else "") + text[a:b].replace("\n", " ") + ("..." if b < len(text) else "")


def analyse(lex, rows: list, seed: int) -> dict:
    n = len(rows)
    rats = [cot_rationale(r["raw_output"]) for r in rows]
    empty = [not t for t in rats]
    per_cat = {c: {"mentioned": 0, "asserted": 0, "negated": 0, "by_model": defaultdict(Counter),
                   "by_condition": defaultdict(Counter), "by_pattern": Counter(), "matches": 0} for c in CATEGORIES}
    examples = {c: {"asserted": [], "negated": []} for c in CATEGORIES}
    n_cats_asserted = Counter()
    for r, t in zip(rows, rats):
        if not t:
            continue
        ms = lex.matches(t)
        flags = lex.cue_flags(t)
        k = 0
        for c in CATEGORIES:
            f = flags[c]
            pc = per_cat[c]
            for key in ("mentioned", "asserted", "negated"):
                if f[key]:
                    pc[key] += 1
                    pc["by_model"][r["model"]][key] += 1
                    pc["by_condition"][r["condition"]][key] += 1
            k += f["asserted"]
        n_cats_asserted[k] += 1
        for m in ms:
            pc = per_cat[m["category"]]
            pc["matches"] += 1
            pc["by_pattern"][m["pattern"] + (":negated" if m["negated"] else "")] += 1
            examples[m["category"]]["negated" if m["negated"] else "asserted"].append(
                {"model": r["model"], "item_id": r["item_id"], "condition": r["condition"], "pattern": m["pattern"],
                 "match": m["text"], "context": excerpt(t, m["start"], m["end"])})
    out = {"n_rationales": n, "n_empty_rationale": sum(empty),
           "empty_by_model": dict(sorted(Counter(r["model"] for r, e in zip(rows, empty) if e).items())),
           "rows_by_model": dict(sorted(Counter(r["model"] for r in rows).items())),
           "rows_by_condition": dict(sorted(Counter(r["condition"] for r in rows).items())),
           "n_invalid_rows": sum(1 for r in rows if r["invalid"]),
           "asserted_categories_per_rationale": {str(k): v for k, v in sorted(n_cats_asserted.items())},
           "categories": {}, "examples": {}}
    for c in CATEGORIES:
        pc = per_cat[c]
        out["categories"][c] = {
            "mentioned": pc["mentioned"], "asserted": pc["asserted"], "negated": pc["negated"], "matches": pc["matches"],
            "by_model": {m: dict(pc["by_model"][m]) for m in sorted(pc["by_model"])},
            "by_condition": {k: dict(pc["by_condition"][k]) for k in sorted(pc["by_condition"])},
            "by_pattern": dict(sorted(pc["by_pattern"].items()))}
        ex = {}
        for pol, k in (("asserted", 3), ("negated", 1)):
            pool = examples[c][pol]
            rng = random.Random(f"{seed}:cue_lexicon:{c}:{pol}")
            ex[pol] = rng.sample(pool, min(k, len(pool))) if pool else []
        out["examples"][c] = ex
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="recompute and compare with the report on disk; write nothing")
    a = ap.parse_args()
    seed = load_config("data.yaml")["seed"]
    lex = load_lexicon(LEXICON)
    lex_sha = lexicon_sha256(LEXICON)
    rows, inputs = load_rows(input_files())
    res = analyse(lex, rows, seed)
    report = {"lexicon_file": LEXICON.relative_to(ROOT).as_posix(), "lexicon_sha256": lex_sha,
              "lexicon_version": lex.spec["version"], "frozen_on": lex.spec["frozen_on"],
              "categories_order": list(CATEGORIES),
              "patterns_per_category": {c: [p[0] for p in lex.patterns[c]] for c in CATEGORIES},
              "inputs": inputs, "seed": seed, **res}
    if a.check:
        disk = json.loads(REPORT.read_text(encoding="utf-8"))
        keys = [k for k in report if k not in ("built_at", "git_commit", "git_describe", "versions", "note")]
        diff = [k for k in keys if report[k] != disk.get(k)]
        print(f"lexicon sha256 {lex_sha[:16]} {'matches' if disk.get('lexicon_sha256') == lex_sha else 'DIFFERS FROM'} the report; "
              f"recomputation {'IDENTICAL' if not diff else 'DIFFERS in ' + ', '.join(diff)}")
        return 0 if not diff else 1
    report.update({"built_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "versions": {"python": sys.version.split()[0], "pyyaml": yaml.__version__},
                   "git_commit": git("rev-parse", "--short", "HEAD"), "git_describe": git("describe", "--tags", "--always"),
                   "note": "Dev only. Counts are by model and condition; no prediction is compared with its label. "
                           "The lexicon is applied to eval rationales for the first time in scripts/07_secondary.py (step 3)."})
    write_json(REPORT, report)
    print(f"lexicon {report['lexicon_file']} sha256 {lex_sha}")
    print(f"{res['n_rationales']:,} dev rationales from {len(inputs)} files; empty rationales {res['n_empty_rationale']} "
          f"{res['empty_by_model']}; invalid rows {res['n_invalid_rows']}")
    print(f"{'category':<26}{'mentioned':>10}{'asserted':>10}{'negated':>9}   sub-patterns (asserted matches)")
    for c in CATEGORIES:
        pc = res["categories"][c]
        subs = ", ".join(f"{k} {v}" for k, v in pc["by_pattern"].items() if not k.endswith(":negated"))
        print(f"{c:<26}{pc['mentioned']:>10}{pc['asserted']:>10}{pc['negated']:>9}   {subs}")
    print("asserted categories per rationale:", res["asserted_categories_per_rationale"])
    for c in CATEGORIES:
        print(f"\n[{c}]")
        for e in res["examples"][c]["asserted"]:
            print(f"  + {e['model']} {e['item_id']} {e['condition']} ({e['pattern']} '{e['match']}'): {e['context']}")
        for e in res["examples"][c]["negated"]:
            print(f"  - {e['model']} {e['item_id']} {e['condition']} ({e['pattern']} '{e['match']}', negated): {e['context']}")
    print(f"\n-> {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
