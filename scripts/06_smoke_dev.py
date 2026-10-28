#!/usr/bin/env python3
"""
06_smoke_dev.py — format-compliance smoke test on the development set (TASK_06 section 5; gate for the
order of work, item 2). Runs every selected model x every strategy on a seeded, stratified sample of dev
items (smoke.n_items, per_class in configs/detection.yaml) and reports per cell: invalid rate, predicted
label distribution, median and maximum latency, prompt tokens, truncated inputs, and whether the cell
passes the gate (invalid rate <= smoke.max_invalid_rate). Nothing here touches an evaluation partition.

Models: --models, or every model whose smoke_tiers (configs/models.yaml) contain --tier. The backend
(cpu / cuda) is resolved from the tier and recorded in every row and in the report, so the same sample can
be run on the laptop (results/smoke_dev/) and on Colab (--out-dir results/smoke_gpu) and compared with
scripts/06_compare_smoke.py.

Rows (one per item, TASK_06 section 5 schema) -> {out-dir}/{model}/{strategy}.jsonl; a finished cell is
skipped on rerun (delete the file to repeat it). Report -> --report (default reports/smoke_dev_report.json).
Usage: python scripts/06_smoke_dev.py [--tier laptop] [--backend auto|cpu|cuda] [--models k1,k2]
         [--strategies s1,s2] [--out-dir results/smoke_dev] [--report reports/smoke_dev_report.json]
"""
import argparse
import datetime as dt
import json
import subprocess
import sys

import llama_cpp

from common import ROOT, load_config, read_text, write_json, open_utf8, extract_label
from detect.backend import Detector, gpu_name, resolve_backend
from detect.items import load_records, load_partitions, smoke_items
from detect.prompts import load_prompt, load_fewshot, render, messages, sha256_file
from detect.stats import cell_stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="laptop")
    ap.add_argument("--backend", default="auto", choices=("auto", "cpu", "cuda"))
    ap.add_argument("--models", default="")
    ap.add_argument("--strategies", default="")
    ap.add_argument("--out-dir", default="results/smoke_dev")
    ap.add_argument("--report", default="reports/smoke_dev_report.json")
    a = ap.parse_args()
    cfg, dcfg, mcfg = load_config(), load_config("detection.yaml"), load_config("models.yaml")
    seed = cfg["seed"]
    if a.tier not in mcfg["tiers"]:
        raise SystemExit(f"unknown tier {a.tier}; keys: {list(mcfg['tiers'])}")
    tier = load_config(mcfg["tiers"][a.tier]["runtime"])
    backend = resolve_backend(a.backend, tier, a.tier, mcfg["tiers"])
    gpu = gpu_name()
    keys = [k for k in mcfg["models"] if a.tier in mcfg["models"][k]["smoke_tiers"]]
    if a.models:
        keys = [k for k in a.models.split(",") if k in mcfg["models"]]
    strategies = a.strategies.split(",") if a.strategies else list(dcfg["prompts"]["strategies"])
    out_dir, report_path = ROOT / a.out_dir, ROOT / a.report

    recs, part = load_records(), load_partitions()
    items = smoke_items(recs, part, dcfg, seed)
    prompts = {s: load_prompt(dcfg, s) for s in strategies}
    fewshot = load_fewshot(dcfg, recs)
    gate = dcfg["smoke"]["max_invalid_rate"]
    report = json.loads(read_text(report_path)) if report_path.exists() else {"cells": {}}
    report.update({
        "seed": seed, "tier": a.tier, "runtime": tier, "backend": backend, "gpu": gpu or None, "n_items": len(items),
        "items": [{"item_id": i["item_id"], "label_true": i["label_true"], "subclass": recs[i["item_id"]]["subclass"]}
                  for i in items],
        "decoding": dcfg["decoding"], "n_ctx": dcfg["context"]["n_ctx"],
        "prompts": {s: {"file": p["file"], "sha256": p["sha256"]} for s, p in prompts.items()},
        "few_shot_examples": {"file": fewshot["file"], "sha256": fewshot["sha256"],
                              "ids": [e["id"] for e in fewshot["examples"]]},
        "config_sha256": {f: sha256_file(ROOT / "configs" / f) for f in ("detection.yaml", "models.yaml")},
        "llama_cpp_python": llama_cpp.__version__,
        "git_commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                     text=True).stdout.strip(),
        "system_role_note": "Models with system_role false (Gemma 2) receive the system text prepended to the "
                            "user message, separated by a blank line (QUESTIONS.md item 9, confirmed 2026-10-27).",
    })
    print(f"smoke: {len(items)} dev items, models {keys}, strategies {strategies}, tier {a.tier}, backend {backend}, "
          f"gpu {gpu or 'none'}, llama-cpp-python {llama_cpp.__version__}", flush=True)

    for key in keys:
        entry = mcfg["models"][key]
        todo = [s for s in strategies if not (out_dir / key / f"{s}.jsonl").exists()]
        if not todo:
            print(f"[{key}] all cells present, skipped", flush=True)
            continue
        det = Detector(key, mcfg, dcfg, tier, seed)
        print(f"[{key}] loaded in {det.load_s} s; sha256 {det.model_hash[:12]}; system_role {entry['system_role']}", flush=True)
        report.setdefault("models", {})[key] = {"sha256": det.model_hash, "load_s": det.load_s,
                                                 "system_role": entry["system_role"], "license": entry["license"]}
        for s in todo:
            p, max_tokens = prompts[s], dcfg["decoding"]["max_tokens"][s]
            ex = fewshot["examples"] if s == "few_shot" else None
            prompt_hash = p["sha256"] if s != "few_shot" else p["sha256"] + ":" + fewshot["sha256"]
            rows = []
            for n, it in enumerate(items, start=1):
                body, trunc = det.fit_body(lambda b: render(p, it["subject"], b, ex), it["body"], max_tokens)
                system, user = render(p, it["subject"], body, ex)
                out = det.complete(messages(system, user, entry["system_role"]), max_tokens)
                label = extract_label(out["raw_output"], s)
                rows.append({"item_id": it["item_id"], "partition": it["partition"], "condition": it["condition"],
                             "label_true": it["label_true"], "model": key, "strategy": s,
                             "raw_output": out["raw_output"], "label_pred": label, "invalid": label == "invalid",
                             "prompt_hash": prompt_hash, "model_hash": det.model_hash,
                             "n_prompt_tokens": out["n_prompt_tokens"], "n_output_tokens": out["n_output_tokens"],
                             "finish_reason": out["finish_reason"], "latency_s": out["latency_s"],
                             "truncated_input": trunc, "backend": backend})
                print(f"[{key}/{s}] {n:2d}/{len(items)} {out['latency_s']:6.1f}s {label:8s} {out['raw_output'][:60]!r}",
                      flush=True)
            (out_dir / key).mkdir(parents=True, exist_ok=True)
            with open_utf8(out_dir / key / f"{s}.jsonl", "w") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            st = cell_stats(rows, gate)
            report["cells"][f"{key}/{s}"] = st
            report["updated_at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            write_json(report_path, report)
            print(f"[{key}/{s}] invalid {st['invalid']}/{st['n']} ({st['invalid_rate']:.0%}) gate "
                  f"{'PASS' if st['gate_pass'] else 'FAIL'}; median {st['latency_median_s']} s; "
                  f"preds {st['pred_counts']}; truncated {st['truncated_input']}", flush=True)
        det.close()

    cells = report["cells"]
    report["gate_all_pass"] = all(c["gate_pass"] for c in cells.values()) if cells else False
    write_json(report_path, report)
    print(f"\n{'cell':28s} {'invalid':>8s} {'median s':>9s} {'max s':>7s} {'trunc':>5s}  preds")
    for name, c in sorted(cells.items()):
        print(f"{name:28s} {c['invalid']:>3d}/{c['n']:<4d} {c['latency_median_s']:>9.1f} {c['latency_max_s']:>7.1f} "
              f"{c['truncated_input']:>5d}  {c['pred_counts']}")
    print(f"gate (invalid <= {gate:.0%} in every cell): {'PASS' if report['gate_all_pass'] else 'FAIL'}")
    print(f"-> {report_path.relative_to(ROOT)}, {out_dir.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
