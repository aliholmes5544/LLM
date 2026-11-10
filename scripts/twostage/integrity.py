"""
integrity.py — integrity check of the two-stage detector's evaluation files (TASK_08 section 9 step 4;
QUESTIONS.md item 18i). Called by scripts/06_check_integrity.py --twostage; writes
reports/integrity_check_twostage.json and leaves reports/integrity_check.json untouched.

Per model of configs/twostage.yaml and per stage-2 fit (`fits`: lr_clean, the primary, and lr_all),
results/raw/twostage_{model}/{strategy_key}/eval.jsonl must: parse; hold every
evaluation item exactly once; carry the runner fields; agree with the item metadata; carry the current prompt
and config hashes, the model's pinned GGUF sha256 and the fitted stage-2 sha256 of the report; have backend cuda
and the GPU of the model's eval tier in the extraction cell of reports/twostage_report.json; set invalid exactly
when the extraction did not parse; and have every label reproducible from the stored indicators and the fitted
stage-2 model (models/twostage/, verified by sha256). Parse-ok counts are reported per cell.
"""
import json
from collections import Counter

from common import ROOT, load_config, read_text
from detect.prompts import load_prompt, sha256_file
from twostage.parse import schema_of
from twostage.stage2 import config_hash, load_model, predict_row, sha256_file as sha256_path

ROW_FIELDS = ("item_id", "partition", "condition", "label_true", "model", "strategy", "raw_output", "label_pred", "invalid",
              "score", "prompt_hash", "config_hash", "model_hash", "stage2_sha256", "n_prompt_tokens", "n_output_tokens",
              "finish_reason", "latency_s", "truncated_input", "backend", "parse_ok")
TIER_GPU = {"colab_t4": "Tesla T4", "colab_l4": "NVIDIA L4"}


def read_rows(path) -> tuple:
    rows, malformed = [], 0
    for line in read_text(path).splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            malformed += 1
    return rows, malformed


def check_twostage(raw_dir, items: dict, mcfg: dict, seed: int, dcfg: dict) -> dict:
    tcfg = load_config("twostage.yaml")
    pcfg = {"prompts": {"dir": ".", "strategies": {"extract": tcfg["prompt"]}, "section_markers": dcfg["prompts"]["section_markers"]}}
    phash, chash = load_prompt(pcfg, "extract")["sha256"], config_hash(tcfg, seed)
    rep_path = ROOT / "reports" / "twostage_report.json"
    rep = json.loads(read_text(rep_path)) if rep_path.exists() else {"cells": {}, "stage2": {}}
    schema, keys = schema_of(tcfg), list(schema_of(tcfg))
    cells, missing = {}, []
    for m, fkey in [(m, f) for m in tcfg["models"] for f in tcfg["fits"]]:
        name, entry, sk = tcfg["model_prefix"] + m, mcfg["models"][m], tcfg["fits"][fkey]["strategy_key"]
        path = raw_dir / name / sk / "eval.jsonl"
        key = f"{name}/{sk}"
        if not path.exists():
            missing.append(key)
            print(f"MISSING {key:28s} {path.relative_to(ROOT)}")
            continue
        rows, malformed = read_rows(path)
        ids = [r.get("item_id") for r in rows]
        have, expected = set(ids), set(items)
        c = {"parses": malformed == 0, "no_duplicates": len(have) == len(ids), "exact_item_set": have == expected}
        s2 = rep.get("stage2", {}).get(m) or {}
        s2 = (s2.get(fkey) or {}) if "model_sha256" not in s2 else {}      # one entry per fit since 2026-11-10
        model_file = ROOT / s2["model_file"] if s2.get("model_file") else None
        s2_ok = bool(model_file and model_file.exists() and sha256_path(model_file) == s2.get("model_sha256"))
        payload = load_model(model_file) if s2_ok else None
        bad = Counter()
        for r in rows:
            if any(k not in r for k in ROW_FIELDS):
                bad["fields"] += 1
                continue
            it = items.get(r["item_id"])
            if it is not None and (r["partition"], r["condition"], r["label_true"]) != (it["partition"], it["condition"], it["label_true"]):
                bad["item_metadata"] += 1
            if r["model"] != name or r["strategy"] != sk:
                bad["model_or_strategy_field"] += 1
            if r["prompt_hash"] != phash:
                bad["prompt_hash"] += 1
            if r["config_hash"] != chash:
                bad["config_hash"] += 1
            if r["model_hash"] != entry["sha256"]:
                bad["model_hash"] += 1
            if r["stage2_sha256"] != s2.get("model_sha256"):
                bad["stage2_sha256"] += 1
            if r["backend"] != "cuda":
                bad["backend"] += 1
            if r["invalid"] != (not r["parse_ok"]) or r["invalid"] != (r["label_pred"] == "invalid"):
                bad["invalid_flag"] += 1
            if payload is not None and r["parse_ok"]:
                ind = {k: r.get(f"ind_{k}") for k in keys}
                label, _ = predict_row(payload["model"], {"indicators": ind}, tcfg)
                if label != r["label_pred"]:
                    bad["label_pred_not_reproducible"] += 1
        for k in ("fields", "item_metadata", "model_or_strategy_field", "prompt_hash", "config_hash", "model_hash", "stage2_sha256",
                  "backend", "invalid_flag", "label_pred_not_reproducible"):
            c[f"rows_{k}_ok"] = bad[k] == 0
        c["stage2_model_verified"] = s2_ok
        xc = rep.get("cells", {}).get(f"{name}/extract/eval")
        gpus = ({xc.get("gpu")} | {s.get("gpu") for s in xc.get("sessions", [])}) if xc else set()
        c["extract_cell_present"] = xc is not None
        c["gpu_matches_eval_tier"] = gpus == {TIER_GPU[entry["eval_tier"]]}
        c["extract_cell_complete"] = bool(xc and xc.get("complete") and xc.get("n") == len(rows))
        n_ok = sum(1 for r in rows if r.get("parse_ok"))
        cells[key] = {"file": str(path.relative_to(ROOT)), "file_sha256": sha256_file(path), "model": name, "base_model": m,
                      "strategy": sk, "fit_key": fkey, "fit_rows": tcfg["fits"][fkey]["rows"], "primary": bool(tcfg["fits"][fkey].get("primary")),
                      "eval_tier": entry["eval_tier"], "pass": all(c.values()), "checks": c,
                      "malformed_lines": malformed, "n_rows": len(rows), "n_expected": len(expected),
                      "missing": len(expected - have), "extra": len(have - expected),
                      "rows_bad": {k: v for k, v in bad.items()}, "parse_ok": n_ok, "parse_failures": len(rows) - n_ok,
                      "parse_failure_rate": round((len(rows) - n_ok) / len(rows), 4) if rows else None,
                      "pred_counts": dict(Counter(r.get("label_pred") for r in rows)),
                      "gpu": sorted(g for g in gpus if g), "failed_checks": sorted(k for k, v in c.items() if not v)}
        print(f"{'OK  ' if cells[key]['pass'] else 'FAIL'} {key:28s} rows {len(rows)}/{len(expected)}  parse failures "
              f"{len(rows) - n_ok}  gpu {','.join(cells[key]['gpu']) or '?'}" + (f"  FAILED: {', '.join(cells[key]['failed_checks'])}" if not cells[key]["pass"] else ""))
    n_pass = sum(1 for r in cells.values() if r["pass"])
    return {"raw_dir": str(raw_dir.relative_to(ROOT)), "n_expected_items": len(items), "prompt_hash": phash, "config_hash": chash,
            "frozen_model_sha256": {m: mcfg["models"][m]["sha256"] for m in tcfg["models"]}, "tier_gpu": TIER_GPU,
            "n_cells": len(cells), "n_pass": n_pass, "missing_cells": missing,
            "fits": {k: v["strategy_key"] for k, v in tcfg["fits"].items()},
            "all_pass": n_pass == len(cells) and not missing and len(cells) == len(tcfg["models"]) * len(tcfg["fits"]), "cells": cells}
