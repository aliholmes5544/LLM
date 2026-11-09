#!/usr/bin/env python3
"""
06_check_integrity.py — integrity check of the raw detection results (TASK_06 section 6 item 8; Section 3.7).

For every results/raw/{model}/{strategy}/eval.jsonl it verifies, without modifying any file:
  - every line parses; the item ids are exactly the expected evaluation item set, built with the same code the
    runner uses (detect.items.eval_items on data/processed/partitions.json + variants_eval.jsonl), no duplicates;
  - partition, condition and label_true of every row equal those of the expected item;
  - prompt_hash and model_hash of every row equal the frozen values (prompt text hash, plus the few-shot file
    hash for few_shot; sha256 pinned in configs/models.yaml); model and strategy fields match the directory;
  - backend == cuda in every row, and the GPU recorded for the cell in reports/detection_run_report.json (cell
    entry and every session) is the one of the model's eval_tier (Tesla T4 for colab_t4, NVIDIA L4 for colab_l4);
  - label_pred equals extract_label(raw_output, strategy) and invalid == (label_pred == "invalid"), i.e. the
    stored labels are reproducible from the stored raw outputs with the frozen parser;
  - counts invalid, truncated_input, finish reasons and items per (partition, condition) for the cell, and
    records the file's sha256 as the fixed-artefact hash;
  - per model (cross-cell): the system text reached the model. The role system text is longer than the
    zero_shot one and the user text is identical, so for every item n_prompt_tokens(role) must exceed
    n_prompt_tokens(zero_shot); equality means the chat formatter dropped the system message (found for
    Mistral-7B on 2026-10-31, QUESTIONS.md item 13). The check is attached to every cell of the model.
  - baselines (configs/baselines.yaml; results/raw/baseline_{key}/supervised/eval.jsonl): the same item-set,
    duplicate, metadata and field checks; config_hash equal to the hash of the baseline's frozen config block;
    model_hash equal to the one in reports/baselines_report.json; backend of the baseline's eval_tier; every
    label_pred reproducible from the stored score with the fixed threshold rule; invalid false everywhere.
No accuracy or any other score is computed. Writes reports/integrity_check.json, prints one line per cell and
exits 1 if any cell fails or any (model, strategy) cell or baseline is missing.

Usage: python scripts/06_check_integrity.py [--raw-dir results/raw] [--models m1,m2] [--strategies s1,s2] [--report PATH]
"""
import argparse
import datetime as dt
import json
import sys
from collections import Counter

from common import ROOT, load_config, write_json, open_utf8, extract_label
from detect.items import load_records, load_partitions, eval_items, count_items
from detect.prompts import load_prompt, load_fewshot, sha256_file
from baselines.core import STRATEGY as BASELINE_STRATEGY, config_hash as baseline_config_hash, label_from_score

REPORT = ROOT / "reports" / "integrity_check.json"
RUN_REPORT = ROOT / "reports" / "detection_run_report.json"
BASELINE_REPORT = ROOT / "reports" / "baselines_report.json"
BASELINE_ROW_FIELDS = ("item_id", "partition", "condition", "label_true", "model", "strategy", "raw_output",
                       "label_pred", "invalid", "score", "config_hash", "model_hash", "n_prompt_tokens",
                       "n_output_tokens", "finish_reason", "latency_s", "truncated_input", "backend")
# GPU model names that nvidia-smi reports on the Colab tiers of configs/models.yaml (the hardware is Colab's).
TIER_GPU = {"colab_t4": "Tesla T4", "colab_l4": "NVIDIA L4"}
ROW_FIELDS = ("item_id", "partition", "condition", "label_true", "model", "strategy", "raw_output", "label_pred",
              "invalid", "prompt_hash", "model_hash", "n_prompt_tokens", "n_output_tokens", "finish_reason",
              "latency_s", "truncated_input", "backend")
ROW_CHECKS = ("fields", "item_metadata", "model_or_strategy_field", "prompt_hash", "model_hash", "backend",
              "label_pred_not_reproducible", "invalid_flag")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def frozen_prompt_hash(dcfg: dict, recs: dict, strategy: str) -> str:
    """Same construction as 06_run_detection.py."""
    h = load_prompt(dcfg, strategy)["sha256"]
    if strategy == "few_shot":
        h += ":" + load_fewshot(dcfg, recs)["sha256"]
    return h


def read_rows(path) -> tuple:
    rows, malformed = [], 0
    for line in open_utf8(path):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            malformed += 1
    return rows, malformed


def check_rows(rows: list, model: str, strategy: str, items: dict, prompt_hash: str, model_sha: str) -> Counter:
    """Number of rows failing each per-row check (ROW_CHECKS)."""
    bad = Counter()
    for r in rows:
        if any(k not in r for k in ROW_FIELDS):
            bad["fields"] += 1
            continue
        it = items.get(r["item_id"])
        if it is not None and (r["partition"], r["condition"], r["label_true"]) != \
                (it["partition"], it["condition"], it["label_true"]):
            bad["item_metadata"] += 1
        if r["model"] != model or r["strategy"] != strategy:
            bad["model_or_strategy_field"] += 1
        if r["prompt_hash"] != prompt_hash:
            bad["prompt_hash"] += 1
        if r["model_hash"] != model_sha:
            bad["model_hash"] += 1
        if r["backend"] != "cuda":
            bad["backend"] += 1
        if extract_label(r["raw_output"], strategy) != r["label_pred"]:
            bad["label_pred_not_reproducible"] += 1
        if r["invalid"] != (r["label_pred"] == "invalid"):
            bad["invalid_flag"] += 1
    return bad


def check_run_report(run_cell, n_rows: int, tier: str, prompt_hash: str, model_sha: str) -> tuple:
    """(checks, detail) for the cell's entry in reports/detection_run_report.json."""
    gpu_expected = TIER_GPU[tier]
    if run_cell is None:
        return ({"run_report_cell_present": False, "gpu_matches_eval_tier": False, "run_report_consistent": False},
                {"run_report": "cell missing from reports/detection_run_report.json", "gpu_expected": gpu_expected})
    sessions = run_cell.get("sessions", [])
    gpus = {run_cell.get("gpu")} | {s.get("gpu") for s in sessions}
    checks = {"run_report_cell_present": True,
              "gpu_matches_eval_tier": gpus == {gpu_expected},
              "run_report_consistent": (run_cell.get("complete") is True and run_cell.get("n") == n_rows
                                        and run_cell.get("backend") == "cuda" and run_cell.get("tier") == tier
                                        and run_cell.get("prompt_hash") == prompt_hash
                                        and run_cell.get("model_sha256") == model_sha)}
    detail = {"run_report": {"gpu": sorted(g for g in gpus if g), "n": run_cell.get("n"),
                             "complete": run_cell.get("complete"), "tier": run_cell.get("tier"),
                             "llama_cpp_python": run_cell.get("llama_cpp_python"),
                             "git_describe": run_cell.get("git_describe"), "sessions": len(sessions),
                             "items_run_in_recorded_sessions": sum(s.get("items_run", 0) for s in sessions),
                             "latency_median_s": run_cell.get("latency_median_s"),
                             "latency_total_s": run_cell.get("latency_total_s")},
              "gpu_expected": gpu_expected}
    return checks, detail


def system_text_delivered(raw_dir, model: str) -> dict:
    """Cross-cell check: role prompts must be longer than zero_shot prompts for every item (see module doc)."""
    zp, rp = raw_dir / model / "zero_shot" / "eval.jsonl", raw_dir / model / "role" / "eval.jsonl"
    if not (zp.exists() and rp.exists()):
        return {"checked": False}
    z = {r["item_id"]: r["n_prompt_tokens"] for r in read_rows(zp)[0]}
    ro = {r["item_id"]: r["n_prompt_tokens"] for r in read_rows(rp)[0]}
    common = z.keys() & ro.keys()
    diffs = Counter(ro[i] - z[i] for i in common)
    return {"checked": True, "n_items": len(common),
            "n_items_role_not_longer": sum(n for d, n in diffs.items() if d <= 0),
            "token_diff_role_minus_zero_shot": {str(d): n for d, n in sorted(diffs.items())},
            "pass": bool(common) and all(d > 0 for d in diffs)}


def check_cell(path, model: str, strategy: str, items: dict, prompt_hash: str, model_sha: str, tier: str,
               run_cell) -> dict:
    rows, malformed = read_rows(path)
    ids = [r.get("item_id") for r in rows]
    have, expected = set(ids), set(items)
    c = {"parses": malformed == 0, "no_duplicates": len(have) == len(ids), "exact_item_set": have == expected}
    detail = {"malformed_lines": malformed,
              "duplicate_item_ids": sorted(i for i, n in Counter(ids).items() if n > 1)[:10],
              "n_rows": len(rows), "n_expected": len(expected),
              "missing": len(expected - have), "extra": len(have - expected),
              "missing_examples": sorted(expected - have)[:5], "extra_examples": sorted(have - expected)[:5]}
    bad = check_rows(rows, model, strategy, items, prompt_hash, model_sha)
    for k in ROW_CHECKS:
        c[f"rows_{k}_ok"] = bad[k] == 0
        detail[f"rows_bad_{k}"] = bad[k]
    rc, rd = check_run_report(run_cell, len(rows), tier, prompt_hash, model_sha)
    c.update(rc)
    detail.update(rd)

    n_invalid = sum(1 for r in rows if r.get("invalid"))
    n_trunc = sum(1 for r in rows if r.get("truncated_input"))
    return {"file": str(path.relative_to(ROOT)), "file_sha256": sha256_file(path), "model": model,
            "strategy": strategy, "eval_tier": tier, "pass": all(c.values()), "checks": c, **detail,
            "invalid": n_invalid, "invalid_rate": round(n_invalid / len(rows), 4) if rows else None,
            "truncated_input": n_trunc, "finish_reasons": dict(Counter(r.get("finish_reason") for r in rows)),
            "items_by_partition_condition": count_items(
                [{"partition": r["partition"], "condition": r["condition"]} for r in rows if "partition" in r]),
            "failed_checks": sorted(k for k, v in c.items() if not v)}


def check_baseline(path, key: str, entry: dict, bcfg: dict, items: dict, chash: str, brep, seed: int) -> dict:
    """Integrity of one baseline's eval file (see module doc). model_hash comes from reports/baselines_report.json."""
    rows, malformed = read_rows(path)
    ids = [r.get("item_id") for r in rows]
    have, expected = set(ids), set(items)
    model_name = bcfg["model_prefix"] + key
    rec = (brep or {}).get("baselines", {}).get(key)
    model_sha = rec.get("model_hash") if rec else None
    backend_expected = load_config("models.yaml")["tiers"][entry["eval_tier"]]["backend"]
    rule, positive = entry["threshold"]["rule"], bcfg["positive_class"]
    bad = Counter()
    for r in rows:
        if any(k not in r for k in BASELINE_ROW_FIELDS):
            bad["fields"] += 1
            continue
        it = items.get(r["item_id"])
        if it is not None and (r["partition"], r["condition"], r["label_true"]) != \
                (it["partition"], it["condition"], it["label_true"]):
            bad["item_metadata"] += 1
        if r["model"] != model_name or r["strategy"] != BASELINE_STRATEGY:
            bad["model_or_strategy_field"] += 1
        if r["config_hash"] != chash:
            bad["config_hash"] += 1
        if model_sha is None or r["model_hash"] != model_sha:
            bad["model_hash"] += 1
        if r["backend"] != backend_expected:
            bad["backend"] += 1
        if label_from_score(r["score"], rule, positive) != r["label_pred"]:
            bad["label_pred_not_reproducible"] += 1
        if r["invalid"] is not False:
            bad["invalid_flag"] += 1
    c = {"parses": malformed == 0, "no_duplicates": len(have) == len(ids), "exact_item_set": have == expected,
         "report_entry_present": rec is not None,
         "report_consistent": bool(rec) and rec.get("config_hash") == chash
         and rec.get("cells", {}).get("eval", {}).get("complete") is True
         and rec.get("cells", {}).get("eval", {}).get("n") == len(rows)}
    for k in ("fields", "item_metadata", "model_or_strategy_field", "config_hash", "model_hash", "backend",
              "label_pred_not_reproducible", "invalid_flag"):
        c[f"rows_{k}_ok"] = bad[k] == 0
    return {"file": str(path.relative_to(ROOT)), "file_sha256": sha256_file(path), "baseline": key,
            "model": model_name, "eval_tier": entry["eval_tier"], "backend_expected": backend_expected,
            "pass": all(c.values()), "checks": c, "malformed_lines": malformed, "n_rows": len(rows),
            "n_expected": len(expected), "missing": len(expected - have), "extra": len(have - expected),
            "rows_bad": dict(bad), "config_hash": chash, "model_hash": model_sha,
            "truncated_input": sum(1 for r in rows if r.get("truncated_input")),
            "pred_counts": dict(Counter(r.get("label_pred") for r in rows)),
            "items_by_partition_condition": count_items(
                [{"partition": r["partition"], "condition": r["condition"]} for r in rows if "partition" in r]),
            "failed_checks": sorted(k for k, v in c.items() if not v)}


def rel(path) -> str:
    """Path relative to the repo when inside it, else as given (a --report outside the repo)."""
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=None, help="default: output.raw_dir of configs/detection.yaml")
    ap.add_argument("--models", default="", help="comma list; default all in configs/models.yaml")
    ap.add_argument("--strategies", default="", help="comma list; default all in configs/detection.yaml")
    ap.add_argument("--baselines", default="", help="comma list; default all in configs/baselines.yaml; 'none' skips")
    ap.add_argument("--report", default=None, help="output path; default reports/integrity_check.json (make evaluate "
                                                   "writes reports/integrity_check_<model>.json so the committed report stays)")
    ap.add_argument("--twostage", action="store_true", help="check the TASK_08 two-stage eval files only, into "
                                                            "reports/integrity_check_twostage.json (item 18i)")
    a = ap.parse_args()
    report_path = ROOT / a.report if a.report else REPORT
    if a.twostage:
        from twostage.integrity import check_twostage
        dcfg, mcfg = load_config("detection.yaml"), load_config("models.yaml")
        raw_dir = ROOT / (a.raw_dir or dcfg["output"]["raw_dir"])
        recs, part = load_records(), load_partitions()
        items = {i["item_id"]: i for i in eval_items(recs, part, dcfg)}
        rep = {"checked_at": now(), **check_twostage(raw_dir, items, mcfg, load_config()["seed"], dcfg)}
        out = ROOT / (a.report or "reports/integrity_check_twostage.json")
        write_json(out, rep)
        print(f"{'ALL PASS' if rep['all_pass'] else 'FAILED'}: {rep['n_pass']}/{rep['n_cells']} two-stage cells pass, "
              f"{len(rep['missing_cells'])} missing -> {rel(out)}")
        return 0 if rep["all_pass"] else 1

    dcfg, mcfg = load_config("detection.yaml"), load_config("models.yaml")
    raw_dir = ROOT / (a.raw_dir or dcfg["output"]["raw_dir"])
    models = a.models.split(",") if a.models else list(mcfg["models"])
    strategies = a.strategies.split(",") if a.strategies else list(dcfg["prompts"]["strategies"])
    recs, part = load_records(), load_partitions()
    items = {i["item_id"]: i for i in eval_items(recs, part, dcfg)}
    hashes = {s: frozen_prompt_hash(dcfg, recs, s) for s in strategies}
    run = json.loads(open_utf8(RUN_REPORT).read()) if RUN_REPORT.exists() else {"cells": {}}

    cells, missing, delivered = {}, [], {}
    for m in models:
        entry = mcfg["models"][m]
        sd = delivered[m] = system_text_delivered(raw_dir, m)
        for s in strategies:
            path, key = raw_dir / m / s / "eval.jsonl", f"{m}/{s}"
            if not path.exists():
                missing.append(key)
                print(f"MISSING {key:24s} {path.relative_to(ROOT)}")
                continue
            r = check_cell(path, m, s, items, hashes[s], entry["sha256"], entry["eval_tier"],
                           run["cells"].get(f"{key}/eval"))
            if sd["checked"]:
                r["checks"]["system_text_delivered"] = sd["pass"]
                r["pass"] = all(r["checks"].values())
                r["failed_checks"] = sorted(k for k, v in r["checks"].items() if not v)
            cells[key] = r
            gpu = ",".join(r["run_report"]["gpu"]) if isinstance(r["run_report"], dict) else "?"
            print(f"{'OK  ' if r['pass'] else 'FAIL'} {key:24s} rows {r['n_rows']}/{r['n_expected']}  "
                  f"invalid {r['invalid']} ({r['invalid_rate'] * 100:.2f}%)  truncated {r['truncated_input']}  "
                  f"gpu {gpu}" + (f"  FAILED: {', '.join(r['failed_checks'])}" if not r["pass"] else ""))

    # ---- baselines (configs/baselines.yaml) ----
    bcfg, seed = load_config("baselines.yaml"), load_config()["seed"]
    bkeys = [] if a.baselines == "none" else (a.baselines.split(",") if a.baselines else list(bcfg["baselines"]))
    brep = json.loads(open_utf8(BASELINE_REPORT).read()) if BASELINE_REPORT.exists() else None
    baselines, missing_baselines = {}, []
    for k in bkeys:
        entry = bcfg["baselines"][k]
        path = raw_dir / (bcfg["model_prefix"] + k) / BASELINE_STRATEGY / "eval.jsonl"
        if not path.exists():
            missing_baselines.append(k)
            print(f"MISSING baseline {k:15s} {path.relative_to(ROOT)}")
            continue
        r = check_baseline(path, k, entry, bcfg, items, baseline_config_hash(k, bcfg, seed), brep, seed)
        baselines[k] = r
        print(f"{'OK  ' if r['pass'] else 'FAIL'} baseline {k:15s} rows {r['n_rows']}/{r['n_expected']}  "
              f"truncated {r['truncated_input']}  backend {r['backend_expected']}  preds {r['pred_counts']}"
              + (f"  FAILED: {', '.join(r['failed_checks'])}" if not r["pass"] else ""))

    n_pass = sum(1 for r in cells.values() if r["pass"])
    n_pass_b = sum(1 for r in baselines.values() if r["pass"])
    ok = n_pass == len(cells) and not missing and n_pass_b == len(baselines) and not missing_baselines
    report = {"checked_at": now(), "raw_dir": str(raw_dir.relative_to(ROOT)), "n_expected_items": len(items),
              "expected_items_by_partition_condition": count_items(list(items.values())),
              "frozen_prompt_hashes": hashes, "frozen_model_sha256": {m: mcfg["models"][m]["sha256"] for m in models},
              "tier_gpu": TIER_GPU, "n_cells": len(cells), "n_pass": n_pass, "missing_cells": missing,
              "all_pass": ok, "system_text_delivered": delivered,
              "baselines": {"n_checked": len(baselines), "n_pass": n_pass_b, "missing": missing_baselines,
                            "cells": baselines},
              "totals": {"rows": sum(r["n_rows"] for r in cells.values()),
                         "invalid": sum(r["invalid"] for r in cells.values()),
                         "truncated_input": sum(r["truncated_input"] for r in cells.values())},
              "cells": cells}
    write_json(report_path, report)
    print(f"{'ALL PASS' if ok else 'FAILED'}: {n_pass}/{len(cells)} cells pass, {len(missing)} missing; "
          f"baselines {n_pass_b}/{len(baselines)} pass, {len(missing_baselines)} missing; "
          f"{report['totals']['rows']} rows, {report['totals']['invalid']} invalid, "
          f"{report['totals']['truncated_input']} truncated -> {rel(report_path)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
