#!/usr/bin/env python3
"""
05c_spot_check_cache.py — regenerate the paraphrases of a seeded sample of core_pos records with the
cache bypassed and confirm the model output is byte-identical to the cached text (Section 3.8).

The determinism check in run_variants_eval.sh compares two runs that share the generation cache, so it
proves that everything downstream of generation is deterministic but not that generation itself is.
This script closes that gap for a sample: 10 core_pos records are chosen with the project seed
(derive_rng(seed, "spot_check", "core_pos")), their (record, condition) states are rebuilt exactly as
scripts/05_derive_variants.py builds them, and every sentence that the eval run generated for them
(attempt 0 and, where retried, attempt 1) is generated again by calling the model directly, with the
same seed, bypassing the cache. The raw model output and finish reason must equal the cached row.

Output: reports/variants_eval_spot_check.json, and the same object under "cache_spot_check" in
reports/variants_eval_report.json (scripts/05_derive_variants.py re-attaches it on a rerun).

Usage:  python scripts/05c_spot_check_cache.py [--n 10]
"""
import argparse
import importlib.util
import json
import sys
import time
from collections import Counter
from pathlib import Path

from common import ROOT, open_utf8, read_text, write_json

sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location("m05", ROOT / "scripts" / "05_derive_variants.py")
m05 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m05)
from variants import paraphrase as pp                                  # noqa: E402
from variants.rng import derive_rng, llama_seed                        # noqa: E402

PROC = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
OUT = REPORTS / "variants_eval_spot_check.json"
PARTITION = "core_pos"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--n", type=int, default=10, help="number of core_pos records to regenerate")
    args = ap.parse_args()
    t_start = time.time()

    parts = json.loads(read_text(PROC / "partitions.json"))
    by_id = {}
    for line in open_utf8(PROC / "records.jsonl"):
        r = json.loads(line)
        if r["id"] in set(parts[PARTITION]):
            by_id[r["id"]] = r
    chosen = sorted(derive_rng(m05.SEED, "spot_check", PARTITION).sample(sorted(parts[PARTITION]), args.n))
    print(f"seeded choice of {args.n} {PARTITION} records: {chosen}")

    variants = {}
    for line in open_utf8(ROOT / m05.ECFG["outputs"]["variants"]):
        v = json.loads(line)
        if v["source_id"] in chosen and "attempt_0" in v["checks"]:
            variants[v["variant_id"]] = v
    cache_path = ROOT / m05.ECFG["outputs"]["cache"]
    cache = {}
    for line in open_utf8(cache_path):
        row = json.loads(line)
        cache[row["key"]] = row
    print(f"eval cache: {len(cache)} rows ({cache_path.relative_to(ROOT)})")

    model_path, model_sha = m05.ensure_model(skip_download=True)
    prompt_text = read_text(ROOT / m05.VCFG["paths"]["prompt"]).strip()
    tmp_cache = ROOT / "data" / "interim" / "spot_check_scratch_cache.jsonl"
    if tmp_cache.exists():
        tmp_cache.unlink()
    para = pp.Paraphraser(model_path, model_sha, prompt_text, m05.VCFG["llama"], tmp_cache)   # never consulted: _generate is called directly
    spans_by_id = m05.compute_spans([by_id[i] for i in chosen])

    results, mismatches, n_gen = [], [], 0
    spans_ok = selection_ok = True
    for vid, v in sorted(variants.items()):
        rec, cond = by_id[v["source_id"]], v["condition"]
        st = m05.ParaState(rec, cond, m05.VCFG["conditions"][cond]["rate"], spans_by_id[rec["id"]])
        ch = v["checks"]
        rec_spans = [{"text": s["text"], "label": s["label"]} for s in spans_by_id[rec["id"]]]
        if rec_spans != ch["spans"]:
            spans_ok = False
        a0_idx = [s["idx"] for s in ch["attempt_0"]["sentences"]]
        if st.selected != a0_idx:
            selection_ok = False
        jobs = [(i, 0) for i in st.selected]
        if ch["attempt_1"]:
            jobs += [(s["idx"], 1) for s in ch["attempt_1"]["sentences"] if s["attempt"] == 1]
        same = 0
        for idx, attempt in jobs:
            sentence = st.segs[idx]["text"]
            seed = llama_seed(m05.SEED, rec["id"], idx, attempt)
            key = para._key(sentence, seed)
            cached = cache.get(key)
            fresh = para._generate(sentence, seed, key)
            n_gen += 1
            if cached is None:
                mismatches.append({"variant_id": vid, "idx": idx, "attempt": attempt, "reason": "no cached row for this key"})
            elif fresh["raw"] != cached["raw"] or fresh["finish_reason"] != cached["finish_reason"]:
                mismatches.append({"variant_id": vid, "idx": idx, "attempt": attempt, "reason": "output differs",
                                   "cached_raw": cached["raw"], "fresh_raw": fresh["raw"],
                                   "cached_finish": cached["finish_reason"], "fresh_finish": fresh["finish_reason"]})
            else:
                same += 1
        results.append({"variant_id": vid, "condition": cond, "n_generations": len(jobs), "identical": same,
                        "attempt_1_sentences": sum(1 for _, a in jobs if a == 1)})
        print(f"  {vid:24s} {len(jobs):3d} generations, identical {same:3d}" + ("" if same == len(jobs) else "  <-- MISMATCH"))
    para.close()
    if tmp_cache.exists():
        tmp_cache.unlink()

    identical = not mismatches and spans_ok and selection_ok
    report = {"partition": PARTITION, "seed": m05.SEED, "rng_label": ["spot_check", PARTITION], "n_records": len(chosen),
              "records": chosen, "n_variants": len(results), "n_generations": n_gen,
              "n_identical": n_gen - len([m for m in mismatches if m["reason"] == "output differs"]),
              "cache_rows_missing": sum(m["reason"] == "no cached row for this key" for m in mismatches),
              "spans_identical_to_eval_run": spans_ok, "sentence_selection_identical_to_eval_run": selection_ok,
              "mismatches": mismatches, "identical": identical,
              "llama": m05.VCFG["llama"], "model_sha256": model_sha, "prompt_sha256": para.prompt_hash,
              "per_condition": dict(Counter(r["condition"] for r in results)),
              "runtime_s": round(time.time() - t_start, 1)}
    write_json(OUT, report)
    rpath = ROOT / m05.ECFG["outputs"]["report"]
    full = json.loads(read_text(rpath))
    full["cache_spot_check"] = report
    write_json(rpath, full)
    print(f"\nspot check: {n_gen} generations over {len(results)} variants of {len(chosen)} records; "
          f"identical {report['n_identical']}; missing cache rows {report['cache_rows_missing']}; "
          f"spans identical {spans_ok}; selection identical {selection_ok}")
    print("RESULT:", "IDENTICAL" if identical else "DIFFERS")
    print(f"written to {OUT.relative_to(ROOT)} and attached to {rpath.relative_to(ROOT)} (cache_spot_check)")
    return 0 if identical else 1


if __name__ == "__main__":
    sys.exit(main())
