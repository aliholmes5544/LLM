#!/usr/bin/env python3
"""
06_run_twostage.py — the two-stage indicator detector (docs/TASK_08_twostage.md; supervisor-requested,
exploratory, post hoc; QUESTIONS.md item 18). An additional evaluated condition inside the existing framework:
nothing here reads or writes the frozen artefacts of steps 05 to 07.

Three modes, one command each (TASK_08 section 9):

  extract   stage 1: the language model (configs/models.yaml entry; same GGUF, verified sha256) fills the
            indicator JSON for every item of a partition under prompts/extract_indicators.txt, greedy decoding,
            seed 2026, max_tokens from configs/twostage.yaml. One row per item, appended as it is produced, to
            results/raw/twostage_{model}/extract/{partition}.jsonl: item_id, partition, condition, label_true,
            model, strategy ("extract"), raw_output, indicators (dict or null), parse_ok, parse_error,
            volunteered_verdict, prompt_hash, config_hash, model_hash, n_prompt_tokens, n_output_tokens,
            finish_reason, latency_s, truncated_input, backend. Resumable, skip / refuse / --force --reason
            rules of scripts/detect/resume.py; eval needs the model's eval_tier and committed frozen files.
  fit       stage 2: one logistic regression on the one-hot indicators of the COMPLETE dev extraction (TASK_08
            section 5: dev only; C by stratified cross-validation on dev; threshold 0.5), saved under
            models/twostage/ (gitignored) with its sha256, coefficients and selection table in the report.
  predict   writes the detector rows results/raw/twostage_{model}/lr/{partition}.jsonl in the runner schema
            of every other detector (TASK_08 section 6) from the extraction rows and the fitted stage 2:
            raw_output = the extraction JSON string, label_pred from stage 2 ("invalid" when the extraction did
            not parse, scored as incorrect exactly as in step 06), score = p_phish, plus parse_ok and the
            indicator columns ind_<key>. Same overwrite guards as the eval files of step 06.

Every mode merges its statistics, hashes and versions into reports/twostage_report.json.

Usage: python scripts/06_run_twostage.py extract --model KEY --partition {dev,eval} [--tier T] [--backend auto|cpu|cuda]
                                                 [--limit N (dev only)] [--force --reason "..."] [--progress-every 25]
       python scripts/06_run_twostage.py fit     --model KEY
       python scripts/06_run_twostage.py predict --model KEY --partition {dev,eval} [--force --reason "..."]
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
import time

from common import ROOT, load_config, read_text, write_json, open_utf8
from detect.items import load_records, load_partitions, eval_items, dev_items, count_items
from detect.prompts import load_prompt, render, messages, sha256_file
from detect.resume import decide, read_rows, SKIP, FORCE
from detect.stats import cell_stats
from twostage.parse import parse_indicators, schema_of, volunteered_verdict
from twostage.stage2 import config_hash, fit_stage2, load_model, predict_row, save_model, sha256_file as sha256_path

REPORT = ROOT / "reports" / "twostage_report.json"
FROZEN = ("configs/twostage.yaml", "prompts/extract_indicators.txt", "configs/detection.yaml", "configs/models.yaml")
EXTRACT_STRATEGY = "extract"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def frozen_is_committed() -> bool:
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", *FROZEN], cwd=ROOT, capture_output=True)
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", *FROZEN], cwd=ROOT, capture_output=True)
    return tracked.returncode == 0 and clean.returncode == 0


def load_report() -> dict:
    rep = json.loads(read_text(REPORT)) if REPORT.exists() else {}
    rep.setdefault("cells", {})
    rep.setdefault("stage2", {})
    rep.setdefault("forced_overwrites", [])
    rep.setdefault("note", "Two-stage indicator detector, TASK_08: supervisor-requested, exploratory, post hoc (QUESTIONS.md "
                           "item 18). Not a proposed system; RQ1 to RQ4 unchanged; the frozen scores of step 07 are untouched.")
    return rep


def extraction_prompt(tcfg: dict, dcfg: dict) -> dict:
    """The extraction prompt through the study's loader (same section markers, same hashing)."""
    pcfg = {"prompts": {"dir": ".", "strategies": {EXTRACT_STRATEGY: tcfg["prompt"]},
                        "section_markers": dcfg["prompts"]["section_markers"]}}
    return load_prompt(pcfg, EXTRACT_STRATEGY)


def partition_items(partition: str, dcfg: dict) -> list:
    recs, part = load_records(), load_partitions()
    return eval_items(recs, part, dcfg) if partition == "eval" else dev_items(recs, part, dcfg)


def paths(tcfg: dict, dcfg: dict, model: str, partition: str) -> dict:
    name = tcfg["model_prefix"] + model
    raw = ROOT / dcfg["output"]["raw_dir"] / name
    return {"name": name, "extract": raw / tcfg["extract_key"] / f"{partition}.jsonl",
            "final": raw / tcfg["strategy_key"] / f"{partition}.jsonl",
            "model": ROOT / tcfg["stage2"]["model_dir"] / f"{model}_lr.joblib"}


def archive_or_skip(out, rows: list, expected: list, phash: str, mhash, a, report: dict, cell_key: str) -> tuple:
    """Shared resume logic: returns (rows, action) after archiving on --force."""
    have = {r["item_id"] for r in rows}
    extra = have - set(expected)
    if extra and not getattr(a, "limit", 0):
        raise SystemExit(f"{out.relative_to(ROOT)} holds {len(extra)} rows outside the current item set; refusing")
    action = decide(rows, expected, phash, mhash, a.force, a.reason)
    if action == FORCE:
        archive = out.with_name(f"{out.stem}.overwritten-{now().replace(':', '')}.jsonl")
        out.rename(archive)
        report["forced_overwrites"].append({"cell": cell_key, "archived_to": str(archive.relative_to(ROOT)), "rows": len(rows),
                                            "reason": a.reason.strip(), "at": now(), "git_commit": git("rev-parse", "--short", "HEAD")})
        write_json(REPORT, report)
        print(f"forced: archived {archive.relative_to(ROOT)} ({len(rows)} rows); reason: {a.reason.strip()}")
        rows = []
    return rows, action


# ---------------------------------------------------------------- extract

def run_extract(a, tcfg: dict, dcfg: dict, mcfg: dict, seed: int) -> int:
    from detect.backend import Detector, gpu_name, resolve_backend
    import llama_cpp
    entry = mcfg["models"][a.model]
    if a.tier not in mcfg["tiers"]:
        raise SystemExit(f"unknown tier {a.tier}; keys: {list(mcfg['tiers'])}")
    if a.partition == "eval":
        if a.limit:
            raise SystemExit("--limit is allowed on dev only (evaluation items are run once, completely)")
        if a.tier != entry["eval_tier"]:
            raise SystemExit(f"{a.model} evaluates on tier {entry['eval_tier']} (configs/models.yaml), not {a.tier}")
        if not frozen_is_committed():
            raise SystemExit(f"{', '.join(FROZEN)} must be committed unchanged; eval runs use frozen artefacts only")
    tier = load_config(mcfg["tiers"][a.tier]["runtime"])
    backend = resolve_backend(a.backend, tier, a.tier, mcfg["tiers"])
    gpu = gpu_name()
    items = partition_items(a.partition, dcfg)
    if a.limit:
        items = items[:a.limit]
    expected = [i["item_id"] for i in items]
    prompt = extraction_prompt(tcfg, dcfg)
    phash, chash = prompt["sha256"], config_hash(tcfg, seed)
    schema, max_tokens = schema_of(tcfg), tcfg["decoding"]["max_tokens"]
    p = paths(tcfg, dcfg, a.model, a.partition)
    out, cell_key = p["extract"], f"{p['name']}/{EXTRACT_STRATEGY}/{a.partition}"
    out.parent.mkdir(parents=True, exist_ok=True)
    report = load_report()
    rows, action = archive_or_skip(out, read_rows(out), expected, phash, entry.get("sha256"), a, report, cell_key)
    if action == SKIP:
        print(f"{cell_key}: already complete ({len(rows)} rows), skipping")
        return 0
    have = {r["item_id"] for r in rows}
    todo = [i for i in items if i["item_id"] not in have]
    print(f"{cell_key}: {len(expected)} items ({count_items(items)}); {len(have)} done, {len(todo)} to run; tier {a.tier}, "
          f"backend {backend}, gpu {gpu or 'none'}, llama-cpp-python {llama_cpp.__version__}, commit {git('describe', '--tags', '--always')}", flush=True)

    dcfg2 = {**dcfg, "decoding": tcfg["decoding"]}            # the study's context rule, TASK_08 decoding
    det = Detector(a.model, mcfg, dcfg2, tier, seed)
    if entry.get("sha256") and det.model_hash != entry["sha256"]:
        raise SystemExit("model hash mismatch")
    print(f"[{a.model}] loaded in {det.load_s} s; sha256 {det.model_hash[:12]}; system_role {entry['system_role']}; "
          f"prompt_hash {phash[:12]}; config_hash {chash[:12]}", flush=True)
    started, t0, n_fail, n_vol = now(), time.perf_counter(), 0, 0
    with open_utf8(out, "a") as f:
        for n, it in enumerate(todo, start=1):
            body, trunc = det.fit_body(lambda b: render(prompt, it["subject"], b), it["body"], max_tokens)
            system, user = render(prompt, it["subject"], body)
            o = det.complete(messages(system, user, entry["system_role"]), max_tokens)
            ind, err = parse_indicators(o["raw_output"], schema)
            vol = volunteered_verdict(o["raw_output"], tcfg["parse"]["verdict_words"])
            n_fail += ind is None
            n_vol += vol
            row = {"item_id": it["item_id"], "partition": it["partition"], "condition": it["condition"], "label_true": it["label_true"],
                   "model": p["name"], "strategy": EXTRACT_STRATEGY, "raw_output": o["raw_output"], "indicators": ind,
                   "parse_ok": ind is not None, "parse_error": err, "volunteered_verdict": vol, "invalid": ind is None,
                   "prompt_hash": phash, "config_hash": chash, "model_hash": det.model_hash,
                   "n_prompt_tokens": o["n_prompt_tokens"], "n_output_tokens": o["n_output_tokens"], "finish_reason": o["finish_reason"],
                   "latency_s": o["latency_s"], "truncated_input": trunc, "backend": backend}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            if n % a.progress_every == 0 or n == len(todo):
                el = time.perf_counter() - t0
                print(f"[{cell_key}] {n}/{len(todo)} elapsed {el / 60:.1f} min, eta {el / n * (len(todo) - n) / 60:.1f} min, "
                      f"parse failures {n_fail}, volunteered verdicts {n_vol}", flush=True)
    det.close()
    wall = round(time.perf_counter() - t0, 1)
    rows = read_rows(out)
    st = cell_stats(rows)                                     # invalid = parse failure here
    st.update({"model": a.model, "detector": p["name"], "strategy": EXTRACT_STRATEGY, "partition": a.partition,
               "n_expected": len(expected), "n_done": len(rows), "complete": set(expected) <= {r["item_id"] for r in rows},
               "parse_failures": int(sum(not r["parse_ok"] for r in rows)),
               "parse_failure_rate": round(sum(not r["parse_ok"] for r in rows) / len(rows), 4) if rows else None,
               "parse_errors": dict(sorted(__import__("collections").Counter(r["parse_error"] for r in rows if r["parse_error"]).items())),
               "volunteered_verdicts": int(sum(r["volunteered_verdict"] for r in rows)),
               "items_by_partition_condition": count_items(items), "limit": a.limit or None, "tier": a.tier, "runtime": tier,
               "backend": backend, "gpu": gpu or None, "llama_cpp_python": llama_cpp.__version__, "model_sha256": det.model_hash,
               "model_load_s": det.load_s, "system_role": entry["system_role"], "prompt_file": prompt["file"], "prompt_hash": phash,
               "config_hash": chash, "decoding": tcfg["decoding"], "n_ctx": dcfg["context"]["n_ctx"], "seed": seed,
               "config_sha256": {x: sha256_file(ROOT / x) for x in FROZEN},
               "git_commit": git("rev-parse", "--short", "HEAD"), "git_describe": git("describe", "--tags", "--always"),
               "sessions": report["cells"].get(cell_key, {}).get("sessions", []) + [
                   {"started_at": started, "finished_at": now(), "items_run": len(todo), "wall_s": wall, "backend": backend, "gpu": gpu or None}]})
    report["cells"][cell_key] = st
    report["updated_at"] = now()
    write_json(REPORT, report)
    print(f"[{cell_key}] {'COMPLETE' if st['complete'] else 'PARTIAL'} {st['n_done']}/{st['n_expected']}; parse failures "
          f"{st['parse_failures']} ({st['parse_failure_rate']:.1%}); volunteered verdicts {st['volunteered_verdicts']}; "
          f"median {st['latency_median_s']} s; this session {len(todo)} items in {wall} s")
    print(f"-> {out.relative_to(ROOT)}, {REPORT.relative_to(ROOT)}")
    return 0


# ---------------------------------------------------------------- fit

def complete_rows(path, partition: str, dcfg: dict, phash: str, chash: str) -> list:
    rows = read_rows(path)
    expected = {i["item_id"] for i in partition_items(partition, dcfg)}
    have = {r["item_id"] for r in rows}
    if have != expected:
        raise SystemExit(f"{path.relative_to(ROOT)}: {len(have)} rows, expected the complete {partition} set of {len(expected)}; "
                         f"run `extract` first")
    bad = [r["item_id"] for r in rows if r["prompt_hash"] != phash or r["config_hash"] != chash]
    if bad:
        raise SystemExit(f"{path.relative_to(ROOT)}: {len(bad)} rows carry another prompt or config hash; re-extract with --force --reason")
    return rows


def run_fit(a, tcfg: dict, dcfg: dict, seed: int) -> int:
    import sklearn
    fit_part = tcfg["stage2"]["fit_partition"]
    if fit_part != "dev":
        raise SystemExit("stage 2 is fitted on dev only (TASK_08 section 5)")
    phash, chash = extraction_prompt(tcfg, dcfg)["sha256"], config_hash(tcfg, seed)
    p = paths(tcfg, dcfg, a.model, fit_part)
    rows = complete_rows(p["extract"], fit_part, dcfg, phash, chash)
    t0 = time.perf_counter()
    res = fit_stage2(rows, tcfg, seed)
    payload = {"model": res["model"], "feature_names": res["feature_names"], "C": res["C"], "prompt_hash": phash,
               "config_hash": chash, "fit_partition": fit_part, "n_rows": res["n_rows"], "fitted_at": now()}
    sha = save_model(p["model"], payload)
    report = load_report()
    report["stage2"][a.model] = {"model_file": str(p["model"].relative_to(ROOT)), "model_sha256": sha, "fit_partition": fit_part,
                                 "n_rows": res["n_rows"], "n_positive": res["n_positive"], "n_parse_failures": res["n_parse_failures"],
                                 "C": res["C"], "cv": tcfg["stage2"]["cv"], "cv_table": res["cv_table"],
                                 "intercept": round(res["intercept"], 6), "coefficients": res["coefficients"],
                                 "top3_abs": [c["feature"] for c in res["coefficients"][:3]],
                                 "prompt_hash": phash, "config_hash": chash, "fit_s": round(time.perf_counter() - t0, 1),
                                 "versions": {"scikit-learn": sklearn.__version__}, "fitted_at": now(),
                                 "git_commit": git("rev-parse", "--short", "HEAD")}
    report["updated_at"] = now()
    write_json(REPORT, report)
    print(f"[{p['name']}] stage 2 fitted on {res['n_rows']} dev rows ({res['n_positive']} phish, {res['n_parse_failures']} parse "
          f"failures); C = {res['C']} by {tcfg['stage2']['cv']['metric']} cv; largest |coef|: "
          f"{', '.join(f'{c['feature']} {c['coef']:+.3f}' for c in res['coefficients'][:3])}; sha256 {sha[:12]}")
    print(f"-> {p['model'].relative_to(ROOT)}, {REPORT.relative_to(ROOT)}")
    return 0


# ---------------------------------------------------------------- predict

def run_predict(a, tcfg: dict, dcfg: dict, mcfg: dict, seed: int) -> int:
    entry = mcfg["models"][a.model]
    if a.partition == "eval" and not frozen_is_committed():
        raise SystemExit(f"{', '.join(FROZEN)} must be committed unchanged; eval rows use frozen artefacts only")
    phash, chash = extraction_prompt(tcfg, dcfg)["sha256"], config_hash(tcfg, seed)
    p = paths(tcfg, dcfg, a.model, a.partition)
    report = load_report()
    s2 = report["stage2"].get(a.model)
    if not s2 or not p["model"].exists():
        raise SystemExit(f"no fitted stage 2 for {a.model}; run `fit` first")
    if sha256_path(p["model"]) != s2["model_sha256"]:
        raise SystemExit(f"{p['model'].relative_to(ROOT)}: sha256 differs from reports/twostage_report.json; refusing")
    payload = load_model(p["model"])
    if payload["prompt_hash"] != phash or payload["config_hash"] != chash:
        raise SystemExit("the fitted stage 2 was trained under another prompt or config hash; re-fit")
    rows_x = complete_rows(p["extract"], a.partition, dcfg, phash, chash)
    expected = [r["item_id"] for r in rows_x]
    out, cell_key = p["final"], f"{p['name']}/{tcfg['strategy_key']}/{a.partition}"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows, action = archive_or_skip(out, read_rows(out), expected, phash, entry.get("sha256"), a, report, cell_key)
    if action == SKIP:
        print(f"{cell_key}: already complete ({len(rows)} rows), skipping")
        return 0
    have = {r["item_id"] for r in rows}
    t0, keys = time.perf_counter(), list(schema_of(tcfg))
    with open_utf8(out, "a") as f:
        for r in rows_x:
            if r["item_id"] in have:
                continue
            t1 = time.perf_counter()
            label, score = predict_row(payload["model"], r, tcfg)
            lat = round(time.perf_counter() - t1, 4)
            row = {"item_id": r["item_id"], "partition": r["partition"], "condition": r["condition"], "label_true": r["label_true"],
                   "model": p["name"], "strategy": tcfg["strategy_key"], "raw_output": r["raw_output"], "label_pred": label,
                   "invalid": label == "invalid", "score": None if score is None else round(score, 6),
                   "prompt_hash": phash, "config_hash": chash, "model_hash": r["model_hash"], "stage2_sha256": s2["model_sha256"],
                   "n_prompt_tokens": r["n_prompt_tokens"], "n_output_tokens": r["n_output_tokens"], "finish_reason": r["finish_reason"],
                   "latency_s": round(r["latency_s"] + lat, 4), "truncated_input": r["truncated_input"], "backend": r["backend"],
                   "parse_ok": r["parse_ok"], **{f"ind_{k}": (r["indicators"] or {}).get(k) for k in keys}}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    rows = read_rows(out)
    st = cell_stats(rows)
    st.update({"model": a.model, "detector": p["name"], "strategy": tcfg["strategy_key"], "partition": a.partition,
               "n_expected": len(expected), "n_done": len(rows), "complete": set(expected) <= {r["item_id"] for r in rows},
               "stage2_sha256": s2["model_sha256"], "prompt_hash": phash, "config_hash": chash, "threshold": tcfg["stage2"]["threshold"],
               "wall_s": round(time.perf_counter() - t0, 1), "git_commit": git("rev-parse", "--short", "HEAD"), "at": now()})
    report["cells"][cell_key] = st
    report["updated_at"] = now()
    write_json(REPORT, report)
    print(f"[{cell_key}] {'COMPLETE' if st['complete'] else 'PARTIAL'} {st['n_done']}/{st['n_expected']}; invalid (parse failures) "
          f"{st['invalid']} ({st['invalid_rate']:.1%}); preds {st['pred_counts']}")
    print(f"-> {out.relative_to(ROOT)}, {REPORT.relative_to(ROOT)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("extract", "fit", "predict"))
    ap.add_argument("--model", required=True)
    ap.add_argument("--partition", default=None, choices=(None, "dev", "eval"))
    ap.add_argument("--tier", default="laptop")
    ap.add_argument("--backend", default="auto", choices=("auto", "cpu", "cuda"))
    ap.add_argument("--limit", type=int, default=0, help="extract on dev only: run the first N items")
    ap.add_argument("--force", action="store_true", help="archive a finished file and redo it (needs --reason)")
    ap.add_argument("--reason", default="")
    ap.add_argument("--progress-every", type=int, default=25)
    a = ap.parse_args()
    tcfg, dcfg, mcfg, seed = load_config("twostage.yaml"), load_config("detection.yaml"), load_config("models.yaml"), load_config()["seed"]
    if a.model not in tcfg["models"]:
        raise SystemExit(f"{a.model} is not in configs/twostage.yaml models {tcfg['models']} (TASK_08 section 2: three, no more)")
    if a.model not in mcfg["models"]:
        raise SystemExit(f"unknown model {a.model}; keys: {list(mcfg['models'])}")
    if a.mode in ("extract", "predict") and not a.partition:
        raise SystemExit(f"{a.mode} needs --partition dev|eval")
    if a.mode == "extract":
        return run_extract(a, tcfg, dcfg, mcfg, seed)
    if a.mode == "fit":
        return run_fit(a, tcfg, dcfg, seed)
    return run_predict(a, tcfg, dcfg, mcfg, seed)


if __name__ == "__main__":
    sys.exit(main())
