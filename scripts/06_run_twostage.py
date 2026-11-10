#!/usr/bin/env python3
"""
06_run_twostage.py — the two-stage indicator detector (docs/TASK_08_twostage.md; supervisor-requested,
exploratory, post hoc; QUESTIONS.md item 18 with the decisions of 2026-11-09). An additional evaluated condition
inside the existing framework: nothing here reads or writes the frozen artefacts of steps 05 to 07.

Five modes, one command each (TASK_08 section 9):

  extract   stage 1: the language model (configs/models.yaml entry; same GGUF, verified sha256) fills the
            indicator JSON for every item of a partition under prompts/extract_indicators.txt, greedy decoding,
            seed 2026, max_tokens from configs/twostage.yaml. One row per item, appended as it is produced, to
            results/raw/twostage_{model}/extract/{partition}.jsonl: item_id, partition, condition, label_true,
            model, strategy ("extract"), raw_output, indicators (dict or null), parse_ok, parse_error,
            extra_keys, volunteered_verdict, prompt_hash, config_hash, model_hash, n_prompt_tokens,
            n_output_tokens, finish_reason, latency_s, truncated_input, backend. Resumable, skip / refuse /
            --force --reason rules of scripts/detect/resume.py; eval needs the model's eval_tier and committed
            frozen files. --smoke runs the 20-item dev smoke sample of configs/detection.yaml (10 + 10, seeded)
            into results/smoke_twostage/{model}/{tier}.jsonl instead (TASK_08 section 9 step 2).
            --units-before / --units-after record the Colab "Available compute units" reading of the session;
            the wall-clock estimate (hours x configs/twostage.yaml budget.rates_units_per_hour) is recorded too.
  fit       stage 2: logistic regressions on the one-hot indicators of the COMPLETE dev extraction (TASK_08
            section 5, item 18a/b: dev only; parse failures excluded and counted; C by StratifiedGroupKFold on dev
            with the source e-mail as group; threshold 0.5), saved under models/twostage/ (gitignored) with their
            sha256, coefficients and selection tables in the report. Two fits per model (configs/twostage.yaml
            `fits`, amended 2026-11-10): `clean`, the PRIMARY, on the 400 dev originals only, and `all`, the
            attack-aware secondary, on all 796 dev items. --stage2 clean|all runs one of them.
  predict   writes the detector rows results/raw/twostage_{model}/{lr_clean,lr_all}/{partition}.jsonl, one file
            per fit, in the runner schema
            of every other detector (TASK_08 section 6) from the extraction rows and the fitted stage 2:
            raw_output = the extraction JSON string, label_pred from stage 2 ("invalid" when the extraction did
            not parse, scored as incorrect exactly as in step 06), score = p_phish, plus parse_ok and the
            indicator columns ind_<key>. Same overwrite guards as the eval files of step 06.
  units     records one Colab "Available compute units" reading (before, after; item 18j/k) against the cells of a
            session: the covered extraction sessions, their wall-clock estimate, the gap and the rate measured over
            the session's span (report `compute_units`). No model, no data.
  budget    writes the report's `budget_projection` for plans A (dev + full eval, 6,003 items per model) and B (dev +
            core eval, gen_phish and gen_legit excluded, 4,003) from the GPU smoke cells and the measured rate when
            present, else from the main study's CoT latencies (scripts/twostage/budget.py). No model.

Every mode merges its statistics, hashes and versions into reports/twostage_report.json.

Usage: python scripts/06_run_twostage.py extract --model KEY --partition {dev,eval} [--tier T] [--backend auto|cpu|cuda]
             [--smoke] [--stats-only] [--limit N (dev only)] [--force --reason "..."] [--progress-every 25] [--units-before X --units-after Y]
       python scripts/06_run_twostage.py fit     --model KEY
       python scripts/06_run_twostage.py predict --model KEY --partition {dev,eval} [--force --reason "..."]
       python scripts/06_run_twostage.py units   --tier T --units-before X --units-after Y [--models k1,k2] [--smoke | --partition P] [--span-s S]
       python scripts/06_run_twostage.py budget
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from collections import Counter

from common import ROOT, load_config, read_text, write_json, open_utf8
from detect.items import load_records, load_partitions, eval_items, dev_items, smoke_items, count_items
from detect.prompts import load_prompt, render, messages, sha256_file
from detect.resume import decide, read_rows, SKIP, FORCE
from detect.stats import cell_stats
import statistics
from twostage.parse import parse_indicators, schema_of, volunteered_verdict
from twostage.stage2 import config_hash, fit_stage2, load_model, predict_row, save_model, sha256_file as sha256_path
from twostage.budget import format_table, plan_counts, projection, units_entry

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
    for k, v in (("cells", {}), ("stage2", {}), ("forced_overwrites", []), ("compute_units", {})):
        rep.setdefault(k, v)
    rep.setdefault("note", "Two-stage indicator detector, TASK_08: supervisor-requested, exploratory, post hoc (QUESTIONS.md "
                           "item 18). Not a proposed system; RQ1 to RQ4 unchanged; the frozen scores of step 07 are untouched.")
    return rep


def extraction_prompt(tcfg: dict, dcfg: dict) -> dict:
    """The extraction prompt through the study's loader (same section markers, same hashing)."""
    pcfg = {"prompts": {"dir": ".", "strategies": {EXTRACT_STRATEGY: tcfg["prompt"]},
                        "section_markers": dcfg["prompts"]["section_markers"]}}
    return load_prompt(pcfg, EXTRACT_STRATEGY)


def partition_items(partition: str, dcfg: dict, smoke: bool = False, seed: int = None) -> list:
    recs, part = load_records(), load_partitions()
    if smoke:
        return smoke_items(recs, part, dcfg, seed)
    return eval_items(recs, part, dcfg) if partition == "eval" else dev_items(recs, part, dcfg)


def paths(tcfg: dict, dcfg: dict, model: str, partition: str, tier: str = None, smoke: bool = False, fit_key: str = None) -> dict:
    """Files of one model: the extraction rows, and for `fit_key` (configs/twostage.yaml fits) the stage-2 model file
    models/twostage/{model}_{strategy_key}.joblib and the detector rows results/raw/twostage_{model}/{strategy_key}/."""
    name = tcfg["model_prefix"] + model
    raw = ROOT / dcfg["output"]["raw_dir"] / name
    sk = tcfg["fits"][fit_key]["strategy_key"] if fit_key else None
    return {"name": name, "strategy_key": sk,
            "extract": (ROOT / tcfg["smoke_dir"] / model / f"{tier}.jsonl") if smoke else raw / tcfg["extract_key"] / f"{partition}.jsonl",
            "final": raw / sk / f"{partition}.jsonl" if sk else None,
            "model": ROOT / tcfg["stage2"]["model_dir"] / f"{model}_{sk}.joblib" if sk else None}


def fit_keys(tcfg: dict, a) -> list:
    """The stage-2 fits to run: --stage2 KEY, else every fit of configs/twostage.yaml `fits` in order (clean first)."""
    keys = list(tcfg["fits"])
    if getattr(a, "stage2", None):
        if a.stage2 not in keys:
            raise SystemExit(f"--stage2 {a.stage2} is not one of {keys} (configs/twostage.yaml fits)")
        return [a.stage2]
    return keys


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


def extract_stats(rows: list) -> dict:
    """Per-cell statistics of extraction rows (no label_pred here: invalid = parse failure)."""
    lat = [r["latency_s"] for r in rows]
    n_pf = int(sum(not r["parse_ok"] for r in rows))
    n = len(rows)
    return {"n": n, "invalid": n_pf, "invalid_rate": round(n_pf / n, 4) if n else None,
            "parse_failures": n_pf, "parse_failure_rate": round(n_pf / n, 4) if n else None,
            "parse_errors": dict(sorted(Counter(r["parse_error"] for r in rows if r["parse_error"]).items())),
            "rows_with_extra_keys": int(sum(bool(r.get("extra_keys")) for r in rows)),
            "extra_keys_seen": dict(sorted(Counter(k for r in rows for k in r.get("extra_keys", [])).items())),
            "volunteered_verdicts": int(sum(r["volunteered_verdict"] for r in rows)),
            "volunteered_verdict_rate": round(sum(r["volunteered_verdict"] for r in rows) / n, 4) if n else None,
            "latency_median_s": round(statistics.median(lat), 3) if lat else None,
            "latency_mean_s": round(statistics.fmean(lat), 3) if lat else None,
            "latency_max_s": round(max(lat), 3) if lat else None, "latency_total_s": round(sum(lat), 1),
            "prompt_tokens_median": int(statistics.median(r["n_prompt_tokens"] for r in rows)) if rows else None,
            "output_tokens_mean": round(statistics.fmean(r["n_output_tokens"] for r in rows), 1) if rows else None,
            "output_tokens_max": max((r["n_output_tokens"] for r in rows), default=None),
            "finish_reasons": dict(Counter(r["finish_reason"] for r in rows)),
            "truncated_input": int(sum(r["truncated_input"] for r in rows)),
            "backends": dict(Counter(r["backend"] for r in rows))}


def write_extract_cell(report: dict, cell_key: str, rows: list, items: list, expected: list, a, tcfg: dict, dcfg: dict,
                       prompt: dict, phash: str, chash: str, seed: int, tier: dict, entry: dict, extra: dict) -> dict:
    st = extract_stats(rows)
    st.update({"model": a.model, "detector": tcfg["model_prefix"] + a.model, "strategy": EXTRACT_STRATEGY, "partition": a.partition,
               "smoke": a.smoke, "n_expected": len(expected), "n_done": len(rows), "complete": set(expected) <= {r["item_id"] for r in rows},
               "items_by_partition_condition": count_items(items), "limit": a.limit or None, "tier": a.tier, "runtime": tier,
               "system_role": entry["system_role"], "prompt_file": prompt["file"], "prompt_hash": phash, "config_hash": chash,
               "decoding": tcfg["decoding"], "n_ctx": dcfg["context"]["n_ctx"], "seed": seed,
               "model_sha256": rows[0]["model_hash"] if rows else entry.get("sha256"),
               "config_sha256": {x: sha256_file(ROOT / x) for x in FROZEN},
               "git_commit": git("rev-parse", "--short", "HEAD"), "git_describe": git("describe", "--tags", "--always"),
               "sessions": report["cells"].get(cell_key, {}).get("sessions", []), **extra})
    report["cells"][cell_key] = st
    report["updated_at"] = now()
    write_json(REPORT, report)
    return st


def units_record(a, tier_name: str, wall_s: float, tcfg: dict) -> dict:
    """Compute units of one session: wall-clock x published rate, and the author's before/after reading (item 18j/k)."""
    rate = tcfg["budget"]["rates_units_per_hour"].get(tier_name)
    est = round(wall_s / 3600 * rate, 3) if rate else None
    read = (round(a.units_before - a.units_after, 3) if a.units_before is not None and a.units_after is not None else None)
    return {"tier": tier_name, "wall_s": wall_s, "rate_units_per_hour": rate, "estimate_wall_x_rate": est,
            "units_before": a.units_before, "units_after": a.units_after, "measured_from_reading": read,
            "gap_measured_minus_estimate": (round(read - est, 3) if read is not None and est is not None else None)}


# ---------------------------------------------------------------- extract

def run_extract(a, tcfg: dict, dcfg: dict, mcfg: dict, seed: int) -> int:
    from detect.backend import Detector, gpu_name, resolve_backend
    import llama_cpp
    entry = mcfg["models"][a.model]
    if a.tier not in mcfg["tiers"]:
        raise SystemExit(f"unknown tier {a.tier}; keys: {list(mcfg['tiers'])}")
    if a.smoke and a.partition == "eval":
        raise SystemExit("--smoke runs the dev smoke sample only")
    if a.partition == "eval":
        if a.limit:
            raise SystemExit("--limit is allowed on dev only (evaluation items are run once, completely)")
        if a.tier != entry["eval_tier"]:
            raise SystemExit(f"{a.model} evaluates on tier {entry['eval_tier']} (configs/models.yaml), not {a.tier}")
        if not frozen_is_committed():
            raise SystemExit(f"{', '.join(FROZEN)} must be committed unchanged; eval runs use frozen artefacts only")
    tier = load_config(mcfg["tiers"][a.tier]["runtime"])
    backend = "n/a" if a.stats_only else resolve_backend(a.backend, tier, a.tier, mcfg["tiers"])
    gpu = gpu_name()
    items = partition_items(a.partition, dcfg, a.smoke, seed)
    if a.limit:
        items = items[:a.limit]
    expected = [i["item_id"] for i in items]
    prompt = extraction_prompt(tcfg, dcfg)
    phash, chash = prompt["sha256"], config_hash(tcfg, seed)
    schema, ncfg, max_tokens = schema_of(tcfg), tcfg["parse"]["normalise"], tcfg["decoding"]["max_tokens"]
    p = paths(tcfg, dcfg, a.model, a.partition, a.tier, a.smoke)
    out = p["extract"]
    cell_key = f"smoke/{a.model}/{a.tier}" if a.smoke else f"{p['name']}/{EXTRACT_STRATEGY}/{a.partition}"
    out.parent.mkdir(parents=True, exist_ok=True)
    report = load_report()
    if a.stats_only:                                          # (re)write the cell's statistics from its file; no model
        rows = read_rows(out)
        st = write_extract_cell(report, cell_key, rows, items, expected, a, tcfg, dcfg, prompt, phash, chash, seed, tier, entry,
                                {"backend": rows[0]["backend"] if rows else None, "gpu": gpu or None, "stats_only_at": now()})
        print(f"[{cell_key}] stats rewritten from {out.relative_to(ROOT)}: {'COMPLETE' if st['complete'] else 'PARTIAL'} "
              f"{st['n_done']}/{st['n_expected']}; parse failures {st['parse_failures']}; volunteered {st['volunteered_verdicts']}; "
              f"median {st['latency_median_s']} s; output tokens mean {st['output_tokens_mean']}")
        return 0
    rows, action = archive_or_skip(out, read_rows(out), expected, phash, entry.get("sha256"), a, report, cell_key)
    if action == SKIP:
        if cell_key not in report["cells"]:
            write_extract_cell(report, cell_key, rows, items, expected, a, tcfg, dcfg, prompt, phash, chash, seed, tier, entry,
                               {"backend": rows[0]["backend"] if rows else backend, "gpu": gpu or None, "stats_only_at": now()})
            print(f"{cell_key}: already complete ({len(rows)} rows); statistics written to the report")
        else:
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
            ind, err, extra = parse_indicators(o["raw_output"], schema, ncfg)
            vol = volunteered_verdict(o["raw_output"], tcfg["parse"]["verdict_words"])
            n_fail += ind is None
            n_vol += vol
            row = {"item_id": it["item_id"], "partition": it["partition"], "condition": it["condition"], "label_true": it["label_true"],
                   "model": p["name"], "strategy": EXTRACT_STRATEGY, "raw_output": o["raw_output"], "indicators": ind,
                   "parse_ok": ind is not None, "parse_error": err, "extra_keys": extra, "volunteered_verdict": vol,
                   "invalid": ind is None, "prompt_hash": phash, "config_hash": chash, "model_hash": det.model_hash,
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
    session = {"started_at": started, "finished_at": now(), "items_run": len(todo), "wall_s": wall, "backend": backend,
               "gpu": gpu or None, "units": units_record(a, a.tier, wall, tcfg)}
    report["cells"].setdefault(cell_key, {}).setdefault("sessions", []).append(session)
    st = write_extract_cell(report, cell_key, rows, items, expected, a, tcfg, dcfg, prompt, phash, chash, seed, tier, entry,
                            {"backend": backend, "gpu": gpu or None, "llama_cpp_python": llama_cpp.__version__,
                             "model_load_s": det.load_s})
    n_pf = st["parse_failures"]
    print(f"[{cell_key}] {'COMPLETE' if st['complete'] else 'PARTIAL'} {st['n_done']}/{st['n_expected']}; parse failures "
          f"{n_pf} ({st['parse_failure_rate']:.1%}); volunteered verdicts {st['volunteered_verdicts']}; extra keys in "
          f"{st['rows_with_extra_keys']} rows; median {st['latency_median_s']} s, mean {st['latency_mean_s']} s; "
          f"output tokens mean {st['output_tokens_mean']}; this session {len(todo)} items in {wall} s"
          + (f"; units estimate {session['units']['estimate_wall_x_rate']}" if session["units"]["estimate_wall_x_rate"] is not None else ""))
    print(f"-> {out.relative_to(ROOT)}, {REPORT.relative_to(ROOT)}")
    return 0


# ---------------------------------------------------------------- units, budget

def run_units(a, tcfg: dict, dcfg: dict, mcfg: dict) -> int:
    """Record one compute-unit reading of a Colab session (item 18j/k) in the report."""
    if a.units_before is None or a.units_after is None:
        raise SystemExit("units needs --units-before and --units-after (the Colab 'Available compute units' readings)")
    if a.tier not in mcfg["tiers"]:
        raise SystemExit(f"unknown tier {a.tier}; keys: {list(mcfg['tiers'])}")
    models = [k.strip() for k in (a.models or "").split(",") if k.strip()] or [m for m in tcfg["models"] if mcfg["models"][m]["eval_tier"] == a.tier]
    bad = [m for m in models if m not in tcfg["models"]]
    if bad:
        raise SystemExit(f"{bad} not in configs/twostage.yaml models {tcfg['models']}")
    if not a.smoke and not a.partition:
        raise SystemExit("units needs --smoke or --partition dev|eval to name the covered cells")
    cells = [f"smoke/{m}/{a.tier}" if a.smoke else f"{tcfg['model_prefix']}{m}/{EXTRACT_STRATEGY}/{a.partition}" for m in models]
    report = load_report()
    missing = [c for c in cells if c not in report["cells"]]
    if missing:
        raise SystemExit(f"no such cell(s) in {REPORT.relative_to(ROOT)}: {missing}")
    entry = units_entry(report, a.tier, cells, a.units_before, a.units_after, a.span_s, tcfg["budget"]["rates_units_per_hour"])
    entry["recorded_at"] = now()
    report["compute_units"][entry["recorded_at"]] = entry
    report["updated_at"] = now()
    write_json(REPORT, report)
    print(f"[units {a.tier}] {a.units_before} -> {a.units_after}: measured {entry['measured_units']} units over {len(entry['sessions'])} "
          f"session(s), extraction wall {entry['extraction_wall_s']} s, estimate {entry['estimate_wall_x_rate']}, gap "
          f"{entry['gap_measured_minus_estimate']}; span {a.span_s} s -> {entry['rate_measured_per_span_hour']} units/h "
          f"(published {entry['rate_published_units_per_hour']})")
    print(f"-> {REPORT.relative_to(ROOT)} compute_units[{entry['recorded_at']}]")
    return 0


def run_budget(a, tcfg: dict, dcfg: dict, mcfg: dict) -> int:
    """Write and print the budget projection for plans A and B (TASK_08 section 9 step 2)."""
    det = json.loads(read_text(ROOT / "reports" / "detection_run_report.json"))["cells"]
    recs, part = load_records(), load_partitions()
    counts = plan_counts(dev_items(recs, part, dcfg), eval_items(recs, part, dcfg))
    report = load_report()
    proj = projection(report, tcfg, mcfg, det, counts)
    proj["computed_at"] = now()
    report["budget_projection"] = proj
    report["updated_at"] = now()
    write_json(REPORT, report)
    print(format_table(proj))
    print(f"-> {REPORT.relative_to(ROOT)} budget_projection ({'all models measured on their tier' if proj['all_measured'] else 'prior basis for at least one model: run the GPU smoke'})")
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
    rows = complete_rows(paths(tcfg, dcfg, a.model, fit_part)["extract"], fit_part, dcfg, phash, chash)
    report = load_report()
    s2m = report["stage2"].get(a.model)
    if not isinstance(s2m, dict) or "model_sha256" in s2m:        # before 2026-11-10 the entry was one flat fit
        s2m = report["stage2"][a.model] = {}
    for key in fit_keys(tcfg, a):
        fcfg, p = tcfg["fits"][key], paths(tcfg, dcfg, a.model, fit_part, fit_key=key)
        t0 = time.perf_counter()
        res = fit_stage2(rows, tcfg, seed, fcfg["rows"])
        payload = {"model": res["model"], "feature_names": res["feature_names"], "C": res["C"], "prompt_hash": phash,
                   "config_hash": chash, "fit_partition": fit_part, "fit_key": key, "fit_rows": fcfg["rows"],
                   "strategy_key": fcfg["strategy_key"], "n_fitted": res["n_fitted"], "fitted_at": now()}
        sha = save_model(p["model"], payload)
        s2m[key] = {"model_file": str(p["model"].relative_to(ROOT)), "model_sha256": sha, "fit_partition": fit_part, "fit_key": key,
                    "fit_rows": fcfg["rows"], "strategy_key": fcfg["strategy_key"], "primary": bool(fcfg.get("primary")),
                    "n_rows_available": res["n_rows_available"], "n_rows": res["n_rows"], "n_fitted": res["n_fitted"],
                    "n_excluded_parse_failures": res["n_excluded_parse_failures"], "n_positive": res["n_positive"],
                    "n_negative": res["n_negative"], "n_groups": res["n_groups"], "C": res["C"], "cv": tcfg["stage2"]["cv"],
                    "cv_table": res["cv_table"], "balanced_accuracy_cv": res["balanced_accuracy_cv"],
                    "balanced_accuracy_cv_sd": res["balanced_accuracy_cv_sd"],
                    "balanced_accuracy_resubstitution": res["balanced_accuracy_resubstitution"],
                    "intercept": round(res["intercept"], 6), "coefficients": res["coefficients"],
                    "top3_abs": [c["feature"] for c in res["coefficients"][:3]], "prompt_hash": phash, "config_hash": chash,
                    "fit_s": round(time.perf_counter() - t0, 1), "versions": {"scikit-learn": sklearn.__version__},
                    "fitted_at": now(), "git_commit": git("rev-parse", "--short", "HEAD")}
        print(f"[{p['name']}/{fcfg['strategy_key']}] stage 2 '{key}' ({fcfg['rows']}{', PRIMARY' if fcfg.get('primary') else ''}) fitted on "
              f"{res['n_fitted']} of {res['n_rows']} rows ({res['n_excluded_parse_failures']} parse failures excluded; {res['n_positive']} phish, "
              f"{res['n_negative']} legit; {res['n_groups']} source e-mails as cv groups); C = {res['C']} by {tcfg['stage2']['cv']['metric']} "
              f"(grouped cv {res['balanced_accuracy_cv']:.4f}, resubstitution {res['balanced_accuracy_resubstitution']:.4f}); largest |coef|: "
              f"{', '.join(f'{c['feature']} {c['coef']:+.3f}' for c in res['coefficients'][:3])}; sha256 {sha[:12]}")
        print(f"-> {p['model'].relative_to(ROOT)}")
    report["updated_at"] = now()
    write_json(REPORT, report)
    print(f"-> {REPORT.relative_to(ROOT)}")
    return 0


# ---------------------------------------------------------------- predict

def run_predict(a, tcfg: dict, dcfg: dict, mcfg: dict, seed: int) -> int:
    entry = mcfg["models"][a.model]
    if a.partition == "eval" and not frozen_is_committed():
        raise SystemExit(f"{', '.join(FROZEN)} must be committed unchanged; eval rows use frozen artefacts only")
    phash, chash = extraction_prompt(tcfg, dcfg)["sha256"], config_hash(tcfg, seed)
    rows_x = complete_rows(paths(tcfg, dcfg, a.model, a.partition)["extract"], a.partition, dcfg, phash, chash)
    for key in fit_keys(tcfg, a):
        predict_one(a, tcfg, dcfg, entry, key, rows_x, phash, chash)
    return 0


def predict_one(a, tcfg: dict, dcfg: dict, entry: dict, key: str, rows_x: list, phash: str, chash: str) -> None:
    """The detector rows of one stage-2 fit (configs/twostage.yaml fits.<key>) from the complete extraction rows."""
    p = paths(tcfg, dcfg, a.model, a.partition, fit_key=key)
    sk = p["strategy_key"]
    report = load_report()
    s2 = (report["stage2"].get(a.model) or {}).get(key) if isinstance(report["stage2"].get(a.model), dict) else None
    if not s2 or not p["model"].exists():
        raise SystemExit(f"no fitted stage 2 '{key}' for {a.model}; run `fit` first")
    if sha256_path(p["model"]) != s2["model_sha256"]:
        raise SystemExit(f"{p['model'].relative_to(ROOT)}: sha256 differs from reports/twostage_report.json; refusing")
    payload = load_model(p["model"])
    if payload["prompt_hash"] != phash or payload["config_hash"] != chash:
        raise SystemExit("the fitted stage 2 was trained under another prompt or config hash; re-fit")
    if payload.get("fit_key") != key or payload.get("strategy_key") != sk:
        raise SystemExit(f"{p['model'].relative_to(ROOT)} was fitted as '{payload.get('fit_key')}', not '{key}'; re-fit")
    expected = [r["item_id"] for r in rows_x]
    out, cell_key = p["final"], f"{p['name']}/{sk}/{a.partition}"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows, action = archive_or_skip(out, read_rows(out), expected, phash, entry.get("sha256"), a, report, cell_key)
    if action == SKIP:
        print(f"{cell_key}: already complete ({len(rows)} rows), skipping")
        return
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
                   "model": p["name"], "strategy": sk, "raw_output": r["raw_output"], "label_pred": label,
                   "invalid": label == "invalid", "score": None if score is None else round(score, 6),
                   "prompt_hash": phash, "config_hash": chash, "model_hash": r["model_hash"], "stage2_sha256": s2["model_sha256"],
                   "n_prompt_tokens": r["n_prompt_tokens"], "n_output_tokens": r["n_output_tokens"], "finish_reason": r["finish_reason"],
                   "latency_s": round(r["latency_s"] + lat, 4), "truncated_input": r["truncated_input"], "backend": r["backend"],
                   "parse_ok": r["parse_ok"], **{f"ind_{k}": (r["indicators"] or {}).get(k) for k in keys}}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    rows = read_rows(out)
    st = cell_stats(rows)
    st.update({"model": a.model, "detector": p["name"], "strategy": sk, "fit_key": key, "fit_rows": s2["fit_rows"], "primary": s2["primary"],
               "partition": a.partition, "n_expected": len(expected), "n_done": len(rows), "complete": set(expected) <= {r["item_id"] for r in rows},
               "stage2_sha256": s2["model_sha256"], "prompt_hash": phash, "config_hash": chash, "threshold": tcfg["stage2"]["threshold"],
               "wall_s": round(time.perf_counter() - t0, 1), "git_commit": git("rev-parse", "--short", "HEAD"), "at": now()})
    report["cells"][cell_key] = st
    report["updated_at"] = now()
    write_json(REPORT, report)
    print(f"[{cell_key}] {'COMPLETE' if st['complete'] else 'PARTIAL'} {st['n_done']}/{st['n_expected']}; invalid (parse failures) "
          f"{st['invalid']} ({st['invalid_rate']:.1%}); preds {st['pred_counts']}")
    print(f"-> {out.relative_to(ROOT)}, {REPORT.relative_to(ROOT)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("extract", "fit", "predict", "units", "budget"))
    ap.add_argument("--model", default=None, help="extract, fit, predict: one of the three models")
    ap.add_argument("--models", default=None, help="units: comma list of the models covered (default: the models of --tier)")
    ap.add_argument("--span-s", type=float, default=None, help="units: seconds from the start of the extraction cell to the after reading")
    ap.add_argument("--partition", default=None, choices=(None, "dev", "eval"))
    ap.add_argument("--stage2", default=None, help="fit, predict: one stage-2 fit of configs/twostage.yaml `fits` (clean | all); default both")
    ap.add_argument("--tier", default="laptop")
    ap.add_argument("--backend", default="auto", choices=("auto", "cpu", "cuda"))
    ap.add_argument("--smoke", action="store_true", help="extract: the 20-item dev smoke sample into results/smoke_twostage/")
    ap.add_argument("--stats-only", action="store_true", help="extract: rewrite the cell's report statistics from its file, no model load")
    ap.add_argument("--limit", type=int, default=0, help="extract on dev only: run the first N items")
    ap.add_argument("--force", action="store_true", help="archive a finished file and redo it (needs --reason)")
    ap.add_argument("--reason", default="")
    ap.add_argument("--progress-every", type=int, default=25)
    ap.add_argument("--units-before", type=float, default=None, help="Colab 'Available compute units' before the session")
    ap.add_argument("--units-after", type=float, default=None, help="... and after it (item 18j/k)")
    a = ap.parse_args()
    tcfg, dcfg, mcfg, seed = load_config("twostage.yaml"), load_config("detection.yaml"), load_config("models.yaml"), load_config()["seed"]
    if a.mode == "units":
        return run_units(a, tcfg, dcfg, mcfg)
    if a.mode == "budget":
        return run_budget(a, tcfg, dcfg, mcfg)
    if a.model is None:
        raise SystemExit(f"{a.mode} needs --model KEY")
    if a.model not in tcfg["models"]:
        raise SystemExit(f"{a.model} is not in configs/twostage.yaml models {tcfg['models']} (TASK_08 section 2: three, no more)")
    if a.model not in mcfg["models"]:
        raise SystemExit(f"unknown model {a.model}; keys: {list(mcfg['models'])}")
    if a.smoke and a.mode == "extract" and not a.partition:
        a.partition = "dev"
    if a.mode in ("extract", "predict") and not a.partition:
        raise SystemExit(f"{a.mode} needs --partition dev|eval")
    if a.mode == "extract":
        return run_extract(a, tcfg, dcfg, mcfg, seed)
    if a.mode == "fit":
        return run_fit(a, tcfg, dcfg, seed)
    return run_predict(a, tcfg, dcfg, mcfg, seed)


if __name__ == "__main__":
    sys.exit(main())
