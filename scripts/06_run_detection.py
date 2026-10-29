#!/usr/bin/env python3
"""
06_run_detection.py — one (model, strategy, partition) cell of the detection stage (TASK_06 section 5;
Chapter 3 Sections 3.6 and 3.7). Builds the item list, renders the frozen prompt, runs llama.cpp with the
frozen decoding settings and writes ONE ROW PER ITEM to results/raw/{model}/{strategy}/{partition}.jsonl:
item_id, partition, condition, label_true, model, strategy, raw_output, label_pred, invalid, prompt_hash,
model_hash, n_prompt_tokens, n_output_tokens, finish_reason, latency_s, truncated_input, backend.

Resumable: rows already in the file are kept and their items skipped (the file is appended row by row, so
an interrupted session loses at most the item in flight). A complete file whose rows carry the current prompt
and model hashes is reported as "already complete, skipping" and left untouched (exit 0, so the notebook's
loop over cells continues). A finished eval file is never overwritten: rerunning needs --force --reason "...",
which archives the old file next to it and logs the reason in reports/detection_run_report.json; --force
without --reason is refused (exit 1), as are existing rows whose prompt or model hash differs from the
current ones (scripts/detect/resume.py, unit-tested). Eval runs also require configs/detection.yaml,
configs/models.yaml and prompts/ to be identical to the committed HEAD (frozen artefacts).

Per-cell statistics (invalid rate, latencies, tokens, truncations), the backend (cpu / cuda), the GPU name,
the llama-cpp-python version, the runtime settings and all hashes go to reports/detection_run_report.json
(merged per cell). Scoring is step 07.

Usage: python scripts/06_run_detection.py --model KEY --strategy KEY --partition {dev,eval}
         [--tier laptop|colab_t4|colab_l4] [--backend auto|cpu|cuda] [--limit N (dev only)]
         [--force --reason "..."] [--progress-every 25]
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
import time

import llama_cpp

from common import ROOT, load_config, read_text, write_json, open_utf8, extract_label
from detect.backend import Detector, gpu_name, resolve_backend
from detect.items import load_records, load_partitions, eval_items, dev_items, count_items
from detect.prompts import load_prompt, load_fewshot, render, messages, sha256_file
from detect.resume import decide, SKIP, FORCE
from detect.stats import cell_stats

REPORT = ROOT / "reports" / "detection_run_report.json"
FROZEN = ("configs/detection.yaml", "configs/models.yaml", "prompts")
SYSTEM_ROLE_NOTE = ("Models with system_role false (Gemma 2) receive the system text prepended to the user "
                    "message, separated by a blank line (QUESTIONS.md item 9, confirmed 2026-10-27).")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def frozen_is_committed() -> bool:
    r = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", *FROZEN], cwd=ROOT, capture_output=True)
    return r.returncode == 0


def read_rows(path) -> list:
    """Rows of a results file. A truncated LAST line (a copy taken while a row was being written, or a
    session killed mid-write) is dropped and the file rewritten without it, so the item is simply rerun."""
    if not path.exists():
        return []
    lines = [l for l in read_text(path).split("\n") if l.strip()]
    rows = []
    for n, line in enumerate(lines):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            if n == len(lines) - 1:
                print(f"{path.name}: dropping a truncated last line ({len(line)} chars); the item will be rerun")
                with open_utf8(path, "w") as f:
                    f.write("".join(l + "\n" for l in lines[:-1]))
                break
            raise SystemExit(f"{path}: malformed row {n + 1} inside the file; refusing to continue")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--partition", required=True, choices=("dev", "eval"))
    ap.add_argument("--tier", default="laptop")
    ap.add_argument("--backend", default="auto", choices=("auto", "cpu", "cuda"))
    ap.add_argument("--limit", type=int, default=0, help="dev only: run the first N items")
    ap.add_argument("--force", action="store_true", help="archive a finished eval file and rerun (needs --reason)")
    ap.add_argument("--reason", default="")
    ap.add_argument("--progress-every", type=int, default=25)
    a = ap.parse_args()

    cfg, dcfg, mcfg = load_config(), load_config("detection.yaml"), load_config("models.yaml")
    if a.model not in mcfg["models"]:
        raise SystemExit(f"unknown model {a.model}; keys: {list(mcfg['models'])}")
    if a.strategy not in dcfg["prompts"]["strategies"]:
        raise SystemExit(f"unknown strategy {a.strategy}; keys: {list(dcfg['prompts']['strategies'])}")
    if a.tier not in mcfg["tiers"]:
        raise SystemExit(f"unknown tier {a.tier}; keys: {list(mcfg['tiers'])}")
    entry, seed = mcfg["models"][a.model], cfg["seed"]
    tier = load_config(mcfg["tiers"][a.tier]["runtime"])
    backend = resolve_backend(a.backend, tier, a.tier, mcfg["tiers"])
    gpu = gpu_name()

    if a.partition == "eval":
        if a.limit:
            raise SystemExit("--limit is allowed on dev only (evaluation items are run once, completely)")
        if a.tier != entry["eval_tier"]:
            raise SystemExit(f"{a.model} evaluates on tier {entry['eval_tier']} (configs/models.yaml), not {a.tier}")
        if not frozen_is_committed():
            raise SystemExit(f"{', '.join(FROZEN)} differ from the committed HEAD; eval runs use frozen, committed "
                             f"artefacts only (commit or discard the changes)")

    recs, part = load_records(), load_partitions()
    items = eval_items(recs, part, dcfg) if a.partition == "eval" else dev_items(recs, part, dcfg)
    if a.limit:
        items = items[:a.limit]
    expected = [i["item_id"] for i in items]
    prompt = load_prompt(dcfg, a.strategy)
    fewshot = load_fewshot(dcfg, recs) if a.strategy == "few_shot" else None
    prompt_hash = prompt["sha256"] + (":" + fewshot["sha256"] if fewshot else "")
    max_tokens = dcfg["decoding"]["max_tokens"][a.strategy]

    out = ROOT / dcfg["output"]["raw_dir"] / a.model / a.strategy / f"{a.partition}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    report = json.loads(read_text(REPORT)) if REPORT.exists() else {"cells": {}, "forced_overwrites": []}
    report.setdefault("cells", {})
    report.setdefault("forced_overwrites", [])
    cell_key = f"{a.model}/{a.strategy}/{a.partition}"

    rows = read_rows(out)
    have = {r["item_id"] for r in rows}
    extra = have - set(expected)
    if extra and not a.limit:
        raise SystemExit(f"{out.relative_to(ROOT)} holds {len(extra)} rows outside the current item set "
                         f"(e.g. {sorted(extra)[0]}); the item set changed, refusing to continue")
    action = decide(rows, expected, prompt_hash, entry.get("sha256"), a.force, a.reason)
    if action == SKIP:
        print(f"{cell_key}: already complete ({len(rows)} rows), skipping")
        return 0
    if action == FORCE:
        archive = out.with_name(f"{a.partition}.overwritten-{now().replace(':', '')}.jsonl")
        out.rename(archive)
        report["forced_overwrites"].append({"cell": cell_key, "archived_to": str(archive.relative_to(ROOT)),
                                            "rows": len(rows), "reason": a.reason.strip(), "at": now(),
                                            "git_commit": git("rev-parse", "--short", "HEAD")})
        write_json(REPORT, report)
        print(f"forced: archived {archive.relative_to(ROOT)} ({len(rows)} rows); reason: {a.reason.strip()}")
        rows, have = [], set()

    todo = [i for i in items if i["item_id"] not in have]
    print(f"{cell_key}: {len(expected)} items ({count_items(items)}); {len(have)} done, {len(todo)} to run; "
          f"tier {a.tier}, backend {backend}, gpu {gpu or 'none'}, llama-cpp-python {llama_cpp.__version__}, "
          f"commit {git('describe', '--tags', '--always')}", flush=True)

    det = Detector(a.model, mcfg, dcfg, tier, seed)
    if entry.get("sha256") and det.model_hash != entry["sha256"]:
        raise SystemExit("model hash mismatch")
    print(f"[{a.model}] loaded in {det.load_s} s; sha256 {det.model_hash[:12]}; system_role {entry['system_role']}; "
          f"prompt_hash {prompt_hash[:12]}", flush=True)

    started, t0, lat_sum = now(), time.perf_counter(), 0.0
    ex = fewshot["examples"] if fewshot else None
    with open_utf8(out, "a") as f:
        for n, it in enumerate(todo, start=1):
            body, trunc = det.fit_body(lambda b: render(prompt, it["subject"], b, ex), it["body"], max_tokens)
            system, user = render(prompt, it["subject"], body, ex)
            o = det.complete(messages(system, user, entry["system_role"]), max_tokens)
            label = extract_label(o["raw_output"], a.strategy)
            row = {"item_id": it["item_id"], "partition": it["partition"], "condition": it["condition"],
                   "label_true": it["label_true"], "model": a.model, "strategy": a.strategy,
                   "raw_output": o["raw_output"], "label_pred": label, "invalid": label == "invalid",
                   "prompt_hash": prompt_hash, "model_hash": det.model_hash,
                   "n_prompt_tokens": o["n_prompt_tokens"], "n_output_tokens": o["n_output_tokens"],
                   "finish_reason": o["finish_reason"], "latency_s": o["latency_s"],
                   "truncated_input": trunc, "backend": backend}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            rows.append(row)
            lat_sum += o["latency_s"]
            if n % a.progress_every == 0 or n == len(todo):
                el = time.perf_counter() - t0
                eta = el / n * (len(todo) - n)
                print(f"[{cell_key}] {n}/{len(todo)} elapsed {el / 60:.1f} min, mean {lat_sum / n:.2f} s/item, "
                      f"eta {eta / 60:.1f} min, invalid so far {sum(r['invalid'] for r in rows)}", flush=True)
    det.close()
    wall = round(time.perf_counter() - t0, 1)

    rows = read_rows(out)
    st = cell_stats(rows)
    st.update({"model": a.model, "strategy": a.strategy, "partition": a.partition,
               "n_expected": len(expected), "n_done": len(rows), "complete": set(expected) <= {r["item_id"] for r in rows},
               "items_by_partition_condition": count_items(items), "limit": a.limit or None,
               "tier": a.tier, "runtime": tier, "backend": backend, "gpu": gpu or None,
               "llama_cpp_python": llama_cpp.__version__, "model_sha256": det.model_hash, "model_load_s": det.load_s,
               "system_role": entry["system_role"], "license": entry["license"],
               "prompt_file": prompt["file"], "prompt_sha256": prompt["sha256"], "prompt_hash": prompt_hash,
               "few_shot_examples": {"file": fewshot["file"], "sha256": fewshot["sha256"],
                                     "ids": [e["id"] for e in fewshot["examples"]]} if fewshot else None,
               "decoding": dcfg["decoding"], "n_ctx": dcfg["context"]["n_ctx"], "seed": seed,
               "config_sha256": {x: sha256_file(ROOT / "configs" / x) for x in ("detection.yaml", "models.yaml")},
               "git_commit": git("rev-parse", "--short", "HEAD"), "git_describe": git("describe", "--tags", "--always"),
               "sessions": report["cells"].get(cell_key, {}).get("sessions", []) + [
                   {"started_at": started, "finished_at": now(), "items_run": len(todo), "wall_s": wall,
                    "backend": backend, "gpu": gpu or None}]})
    report["cells"][cell_key] = st
    report["system_role_note"] = SYSTEM_ROLE_NOTE
    report["updated_at"] = now()
    write_json(REPORT, report)
    print(f"[{cell_key}] {'COMPLETE' if st['complete'] else 'PARTIAL'} {st['n_done']}/{st['n_expected']}; invalid "
          f"{st['invalid']} ({st['invalid_rate']:.1%}); median {st['latency_median_s']} s, mean {st['latency_mean_s']} s; "
          f"truncated {st['truncated_input']}; preds {st['pred_counts']}; this session {len(todo)} items in {wall} s")
    print(f"-> {out.relative_to(ROOT)}, {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
