#!/usr/bin/env python3
"""
06_run_baselines.py — one (baseline, partition) cell of the baseline branch (TASK_06 sections 3 and 5;
Chapter 3 Section 3.5, Chapter 4 Section 4.4). Trains the baseline on `train` (TF-IDF models: refit every run,
C chosen on `valid`; DistilBERT: trained once, checkpoint reused), scores every item of the partition one at a
time and writes ONE ROW PER ITEM in the detector runner's schema to
results/raw/baseline_{key}/supervised/{partition}.jsonl: item_id, partition, condition, label_true, model,
strategy, raw_output, label_pred, invalid (always false), score, config_hash (counterpart of prompt_hash),
model_hash, n_prompt_tokens (non-zero TF-IDF features, or wordpieces fed to DistilBERT), n_output_tokens (0),
finish_reason ("n/a"), latency_s, truncated_input, backend.

Resumable and protected like scripts/06_run_detection.py (shared decision in scripts/detect/resume.py): rows
already present are kept, a complete file with matching hashes is skipped with exit 0, rows with other hashes
are refused, a finished eval file is rewritten only with --force --reason "..." (the old file is archived next
to it). Evaluation runs require configs/baselines.yaml to be committed (frozen) and the baseline's eval_tier.
Thresholds are fixed in the config; nothing is chosen on an evaluation partition. On `valid` the script also
records precision, recall and F1 (the TASK_06 sanity check and the C selection); on `eval` no score is
computed, scoring is step 07. Per-cell statistics, the training record, the selection table, all hashes and
versions go to reports/baselines_report.json.

Usage: python scripts/06_run_baselines.py --baseline {tfidf_lr,tfidf_svm,distilbert} --partition {valid,eval}
         [--tier laptop|colab_t4] [--backend auto|cpu|cuda] [--limit N (valid only)] [--force --reason "..."]
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
import time

from common import ROOT, load_config, read_text, write_json, open_utf8
from detect.items import load_records, load_partitions, count_items
from detect.prompts import sha256_file
from detect.resume import decide, read_rows, SKIP, FORCE
from detect.stats import cell_stats
from baselines.core import (STRATEGY, item_text, partition_items, config_hash, label_from_score, prf,
                            rows_for_decide, model_dir)

REPORT = ROOT / "reports" / "baselines_report.json"
FROZEN = ("configs/baselines.yaml",)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def frozen_is_committed() -> bool:
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", *FROZEN], cwd=ROOT, capture_output=True)
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", *FROZEN], cwd=ROOT, capture_output=True)
    return tracked.returncode == 0 and clean.returncode == 0


def resolve_backend(requested: str, tier: str, mcfg: dict) -> str:
    want = mcfg["tiers"][tier]["backend"]
    if requested != "auto" and requested != want:
        raise SystemExit(f"tier {tier} must report backend {want}, not {requested}")
    if want == "cuda":
        import torch
        if not torch.cuda.is_available():
            raise SystemExit(f"tier {tier} needs a CUDA device and none is available")
    return want


def gpu_name() -> str:
    """nvidia-smi's GPU name, or "" on a machine without it (the laptop)."""
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True)
    except FileNotFoundError:
        return ""
    return r.stdout.strip().splitlines()[0] if r.returncode == 0 and r.stdout.strip() else ""


def texts_labels(items: list, text_cfg: dict) -> tuple:
    return [item_text(i, text_cfg) for i in items], [i["label_true"] for i in items]


def build_tfidf(key: str, entry: dict, bcfg: dict, recs: dict, part: dict, dcfg: dict, seed: int, prev: dict) -> dict:
    """Refit (seconds). The model_hash must equal the one recorded by an earlier run: the fit is deterministic."""
    import sklearn
    from baselines import tfidf
    tr, va = partition_items("train", recs, part, bcfg, dcfg), partition_items("valid", recs, part, bcfg, dcfg)
    xt, yt = texts_labels(tr, bcfg["text"])
    xv, yv = texts_labels(va, bcfg["text"])
    model = tfidf.fit(entry, xt, yt, xv, yv, seed, bcfg["positive_class"])
    mh = tfidf.model_hash(model)
    path = model_dir(bcfg) / f"{key}.joblib"
    file_sha = tfidf.save(model, path)
    if prev.get("model_hash") and prev["model_hash"] != mh:
        raise SystemExit(f"{key}: refit gives model_hash {mh[:12]} but the report records {prev['model_hash'][:12]}; "
                         f"the fit is not reproducing (different library version or data?); investigate before running")
    training = {"n_train": model["n_train"], "n_valid": model["n_valid"], "class_counts_train": count_labels(yt),
                "class_counts_valid": count_labels(yv), "vocab_size": model["vocab_size"], "fit_s": model["fit_s"],
                "C_grid": entry["C_grid"], "selection_table_valid": {str(C): t for C, t in model["selection_table"].items()},
                "chosen_C": model["C"], "selection_rule": entry["selection"],
                "model_hash_reproduced": prev.get("model_hash") == mh if prev.get("model_hash") else None}
    score = lambda text: tfidf.score_one(model, text, bcfg["positive_class"]) + (False,)
    return {"model_hash": mh, "model_file": str(path.relative_to(ROOT)), "model_file_sha256": file_sha,
            "training": training, "score": score, "versions": {"scikit-learn": sklearn.__version__}}


def build_distilbert(key: str, entry: dict, bcfg: dict, recs: dict, part: dict, dcfg: dict, seed: int, prev: dict,
                     backend: str) -> dict:
    """Train once on `train` (checkpoint in models/baselines/), afterwards load the checkpoint; its sha256 is the
    model_hash. No validation-based selection of any kind."""
    from baselines import distilbert as db
    db.set_determinism(seed, entry["deterministic"])
    device = "cuda" if backend == "cuda" else "cpu"
    m = db.load(entry, device)
    path = model_dir(bcfg) / f"{key}.pt"
    training = prev.get("training", {})
    if path.exists():
        mh = db.load_checkpoint(m, path)
        print(f"[{key}] loaded checkpoint {path.relative_to(ROOT)} sha256 {mh[:12]}", flush=True)
        if prev.get("model_hash") and prev["model_hash"] != mh:
            raise SystemExit(f"{key}: checkpoint sha256 {mh[:12]} differs from the recorded model_hash "
                             f"{prev['model_hash'][:12]}; refusing to score with an unrecorded model")
    else:
        tr = partition_items("train", recs, part, bcfg, dcfg)
        xt, yt = texts_labels(tr, bcfg["text"])
        print(f"[{key}] training on {len(xt)} items ({count_labels(yt)}), device {device}", flush=True)
        training = db.train(m, entry, xt, yt, seed, log=lambda s: print(s, flush=True))
        training.update({"class_counts_train": count_labels(yt), "trained_at": now(), "device": device,
                         "gpu": gpu_name() or None})
        mh = db.save_checkpoint(m, path)
        print(f"[{key}] trained in {training['train_s']} s; checkpoint sha256 {mh[:12]}", flush=True)
    score = lambda text: db.score_one(m, text, entry["max_length"])
    return {"model_hash": mh, "model_file": str(path.relative_to(ROOT)), "model_file_sha256": mh,
            "training": training, "score": score,
            "versions": {"torch": m["torch"], "transformers": m["transformers"]},
            "pretrained": {"name": m["pretrained"], "snapshot_sha": m["snapshot_sha"]}}


def count_labels(y: list) -> dict:
    return {k: y.count(k) for k in sorted(set(y))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--partition", required=True, choices=("valid", "eval"))
    ap.add_argument("--tier", default="laptop")
    ap.add_argument("--backend", default="auto", choices=("auto", "cpu", "cuda"))
    ap.add_argument("--limit", type=int, default=0, help="valid only: score the first N items")
    ap.add_argument("--force", action="store_true", help="archive a finished eval file and rerun (needs --reason)")
    ap.add_argument("--reason", default="")
    ap.add_argument("--progress-every", type=int, default=1000)
    a = ap.parse_args()

    cfg, bcfg, dcfg, mcfg = load_config(), load_config("baselines.yaml"), load_config("detection.yaml"), load_config("models.yaml")
    if a.baseline not in bcfg["baselines"]:
        raise SystemExit(f"unknown baseline {a.baseline}; keys: {list(bcfg['baselines'])}")
    if a.tier not in mcfg["tiers"]:
        raise SystemExit(f"unknown tier {a.tier}; keys: {list(mcfg['tiers'])}")
    entry, seed = bcfg["baselines"][a.baseline], cfg["seed"]
    backend = resolve_backend(a.backend, a.tier, mcfg)
    if a.partition == "eval":
        if a.limit:
            raise SystemExit("--limit is allowed on valid only (evaluation items are scored once, completely)")
        if a.tier != entry["eval_tier"]:
            raise SystemExit(f"{a.baseline} evaluates on tier {entry['eval_tier']} (configs/baselines.yaml), not {a.tier}")
        if not frozen_is_committed():
            raise SystemExit(f"{', '.join(FROZEN)} is not committed unchanged; eval runs use frozen artefacts only")

    recs, part = load_records(), load_partitions()
    items = partition_items(a.partition, recs, part, bcfg, dcfg)
    if a.limit:
        items = items[:a.limit]
    expected = [i["item_id"] for i in items]
    chash = config_hash(a.baseline, bcfg, seed)
    model_name = bcfg["model_prefix"] + a.baseline
    out = ROOT / dcfg["output"]["raw_dir"] / model_name / STRATEGY / f"{a.partition}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    report = json.loads(read_text(REPORT)) if REPORT.exists() else {"baselines": {}, "forced_overwrites": []}
    report.setdefault("baselines", {})
    report.setdefault("forced_overwrites", [])
    prev = report["baselines"].get(a.baseline, {})
    if prev.get("config_hash") and prev["config_hash"] != chash:
        print(f"[{a.baseline}] NOTE: configs/baselines.yaml block changed since the recorded run "
              f"({prev['config_hash'][:12]} -> {chash[:12]}); existing rows with the old hash are refused below")
        prev = {}
    cell_key = f"{model_name}/{STRATEGY}/{a.partition}"

    print(f"{cell_key}: {len(expected)} items ({count_items(items)}); tier {a.tier}, backend {backend}, "
          f"gpu {gpu_name() or 'none'}, config_hash {chash[:12]}, commit {git('describe', '--tags', '--always')}", flush=True)
    if entry["method"] == "finetuned_transformer":
        built = build_distilbert(a.baseline, entry, bcfg, recs, part, dcfg, seed, prev, backend)
    else:
        built = build_tfidf(a.baseline, entry, bcfg, recs, part, dcfg, seed, prev)
    mh = built["model_hash"]
    print(f"[{a.baseline}] model_hash {mh[:12]}; training: "
          f"{ {k: v for k, v in built['training'].items() if k not in ('selection_table_valid',)} }", flush=True)

    rows = read_rows(out)
    have = {r["item_id"] for r in rows}
    extra = have - set(expected)
    if extra and not a.limit:
        raise SystemExit(f"{out.relative_to(ROOT)} holds {len(extra)} rows outside the current item set; refusing")
    action = decide(rows_for_decide(rows), expected, chash, mh, a.force, a.reason)
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
    rule, started, t0 = entry["threshold"]["rule"], now(), time.perf_counter()
    with open_utf8(out, "a") as f:
        for n, it in enumerate(todo, start=1):
            text = item_text(it, bcfg["text"])
            t1 = time.perf_counter()
            score, ntok, trunc = built["score"](text)
            lat = round(time.perf_counter() - t1, 4)
            label = label_from_score(score, rule, bcfg["positive_class"])
            row = {"item_id": it["item_id"], "partition": it["partition"], "condition": it["condition"],
                   "label_true": it["label_true"], "model": model_name, "strategy": STRATEGY,
                   "raw_output": f"{entry['threshold']['score']}={score:.6f}", "label_pred": label, "invalid": False,
                   "score": round(score, 6), "config_hash": chash, "model_hash": mh,
                   "n_prompt_tokens": ntok, "n_output_tokens": 0, "finish_reason": "n/a", "latency_s": lat,
                   "truncated_input": bool(trunc), "backend": backend}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            rows.append(row)
            if n % a.progress_every == 0 or n == len(todo):
                print(f"[{cell_key}] {n}/{len(todo)} elapsed {time.perf_counter() - t0:.1f} s", flush=True)
    wall = round(time.perf_counter() - t0, 1)

    rows = read_rows(out)
    st = cell_stats(rows)
    st.update({"partition": a.partition, "n_expected": len(expected), "n_done": len(rows),
               "complete": set(expected) <= {r["item_id"] for r in rows},
               "items_by_partition_condition": count_items(items), "limit": a.limit or None,
               "tier": a.tier, "backend": backend, "gpu": gpu_name() or None,
               "sessions": prev.get("cells", {}).get(a.partition, {}).get("sessions", []) + [
                   {"started_at": started, "finished_at": now(), "items_run": len(todo), "wall_s": wall,
                    "backend": backend, "gpu": gpu_name() or None}]})
    if a.partition == "valid":        # sanity check and selection partition only; never on eval here
        st["valid_metrics"] = prf([r["label_true"] for r in rows], [r["label_pred"] for r in rows], bcfg["positive_class"])
    cells = prev.get("cells", {})
    cells[a.partition] = st
    report["baselines"][a.baseline] = {
        "method": entry["method"], "eval_tier": entry["eval_tier"], "strategy": STRATEGY, "model": model_name,
        "config_hash": chash, "model_hash": mh, "model_file": built["model_file"],
        "model_file_sha256": built["model_file_sha256"], "threshold": entry["threshold"],
        "text": bcfg["text"], "seed": seed, "training": built["training"], "versions": built["versions"],
        **({"pretrained": built["pretrained"]} if "pretrained" in built else {}),
        "config_sha256": {"baselines.yaml": sha256_file(ROOT / "configs" / "baselines.yaml")},
        "git_commit": git("rev-parse", "--short", "HEAD"), "git_describe": git("describe", "--tags", "--always"),
        "cells": cells}
    report["note"] = ("Baselines are trained on `train` and selected on `valid` only (TASK_06 section 3); valid_metrics "
                      "are the sanity check of TASK_06 section 6 item 4, not evaluation results. Scoring on eval is step 07.")
    report["updated_at"] = now()
    write_json(REPORT, report)
    print(f"[{cell_key}] {'COMPLETE' if st['complete'] else 'PARTIAL'} {st['n_done']}/{st['n_expected']}; preds "
          f"{st['pred_counts']}; median {st['latency_median_s']} s; truncated {st['truncated_input']}; "
          f"this session {len(todo)} items in {wall} s"
          + (f"; valid P/R/F1 {st['valid_metrics']['precision']}/{st['valid_metrics']['recall']}/{st['valid_metrics']['f1']}"
             if a.partition == "valid" else ""))
    print(f"-> {out.relative_to(ROOT)}, {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
