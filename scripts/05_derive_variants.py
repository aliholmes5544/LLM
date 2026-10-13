#!/usr/bin/env python3
"""
05_derive_variants.py — derive paraphrased and obfuscated variants and check them (Section 3.2.3).

Development set only: the 100 dev `ephish_phish` emails (LLM-generated, personalized). The
script asserts before doing anything that none of them belongs to an evaluation partition.

Stages:
  1. protected spans per record (regex + spaCy NER; placeholders always protected)
  2. obfuscation conditions (deterministic script) + integrity replay of the edit log
  3. paraphrase conditions, attempt 0 (Phi-3.5-mini-instruct GGUF via llama.cpp, cached)
  4. checks: per rewritten sentence NLI both directions + its own protected spans;
     per variant cosine, length ratio, spans
  5. sentences that failed are rewritten once more with a new seed; a sentence that still
     fails is replaced by its original (fallback). achieved_fraction = retained rewrites /
     selected sentences. A variant is excluded if achieved_fraction is below the condition's
     minimum or the final body fails the variant-level checks; otherwise it is "regenerated".
  6. outputs, report and the manual-review sample (stratified 10 % + every excluded
     paraphrase + a seeded sample of regenerated ones, each flagged with auto_outcome)

Usage:  python scripts/05_derive_variants.py [--conditions a,b] [--limit N] [--selftest] [--skip-download]
Output: data/processed/variants_dev.jsonl, data/processed/obfuscation_log_dev.jsonl,
        reports/variants_dev_report.json, reports/manual_review_sample_dev.csv,
        reports/variants_dev_runtime.json (timings only; not byte-stable)
"""
import argparse
import csv
import gc
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from common import ROOT, load_config, open_utf8, read_text, write_json

os.environ.setdefault("HF_HOME", str(ROOT / "models" / "hf"))        # keep all model caches gitignored
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

from variants import obfuscate as ob                                   # noqa: E402
from variants import paraphrase as pp                                  # noqa: E402
from variants import spans as sp                                       # noqa: E402
from variants.checks import Checkers, check_sentence, check_variant    # noqa: E402
from variants.rng import derive_rng, llama_seed                        # noqa: E402

CFG = load_config()
VCFG = load_config("variants.yaml")
SEED = CFG["seed"]
PROC = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
EVAL_PARTITIONS = ("core_pos", "core_neg", "ctrl_para_legit", "ctrl_modern_legit", "gen_phish", "gen_legit")
VARIANT_CHECKS = ("sim_ok", "len_ok", "spans_ok")


# ---- helpers ---------------------------------------------------------------
def dist(values: list, keys=("min", "p5", "median")) -> dict:
    if not values:
        return {k: None for k in keys}
    a = np.array(values, dtype=float)
    f = {"min": a.min, "p5": lambda: np.percentile(a, 5), "median": lambda: np.median(a), "max": a.max,
         "mean": a.mean, "total": a.sum}
    return {k: round(float(f[k]()), 4) for k in keys}


def stats(values: list) -> dict:
    return dist(values, ("min", "median", "max", "total"))


def sha256_file(path: Path) -> str:
    """sha256 of a (large) file, memoised in a sidecar keyed by size and mtime."""
    side = path.with_suffix(path.suffix + ".sha256")
    stamp = f"{path.stat().st_size}:{int(path.stat().st_mtime)}"
    if side.exists():
        s, digest = read_text(side).split()
        if s == stamp:
            return digest
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    side.write_text(f"{stamp} {h.hexdigest()}", encoding="utf-8", newline="\n")
    return h.hexdigest()


# ---- stage 0: targets and the evaluation-partition assertion ----------------
def load_targets(limit: int) -> tuple:
    recs = [json.loads(l) for l in open_utf8(PROC / "records.jsonl")]
    by_id = {r["id"]: r for r in recs}
    parts = json.loads(read_text(PROC / "partitions.json"))
    t = VCFG["target"]
    targets = sorted(i for i in parts[t["partition"]] if by_id[i]["subclass"] == t["subclass"])
    eval_ids = set().union(*(set(parts[k]) for k in EVAL_PARTITIONS))
    assert set(targets).isdisjoint(eval_ids), "step 05 must never touch an evaluation partition"
    assert targets, f"no {t['subclass']} records in partition {t['partition']}"
    info = {"partition": t["partition"], "subclass": t["subclass"], "n_available": len(targets),
            "eval_partitions_checked": list(EVAL_PARTITIONS), "n_eval_ids": len(eval_ids), "disjoint": True}
    if limit:
        targets = targets[:limit]
    info["n_records"] = len(targets)
    return [by_id[i] for i in targets], info


# ---- stage 1: protected spans ----------------------------------------------
def compute_spans(records: list) -> dict:
    import spacy
    s = VCFG["spans"]
    nlp = spacy.load(s["spacy_model"], disable=["lemmatizer"])
    out = {r["id"]: sp.detect_spans(r["body"], nlp, s["placeholder_phrases"], s["ner_labels"]) for r in records}
    del nlp
    gc.collect()
    return out


# ---- stage 2: obfuscation --------------------------------------------------
def derive_obfuscation(records: list, cond: str, rate: float, spans_by_id: dict) -> tuple:
    rows, log = [], []
    for r in records:
        spans = spans_by_id[r["id"]]
        variant, edits, st = ob.obfuscate(r["body"], spans, rate, derive_rng(SEED, cond, r["id"]), VCFG["obfuscation"])
        try:
            integrity = ob.replay_reverse(variant, edits) == r["body"]
        except ValueError:
            integrity = False
        vid = f"{r['id']}#{cond}"
        log.extend({"variant_id": vid, **e} for e in edits)
        rows.append({"variant_id": vid, "source_id": r["id"], "condition": cond, "subject": r["subject"],
                     "body": variant, "checks": {"integrity_ok": integrity, **st,
                                                  "spans": [{"text": s["text"], "label": s["label"]} for s in spans]},
                     "status": "pass" if integrity else "excluded"})
    return rows, log


# ---- stages 3-5: paraphrase ---------------------------------------------------
class ParaState:
    """Everything about one (record, condition) pair across both attempts."""

    def __init__(self, rec: dict, cond: str, rate: float, spans: list):
        self.rec, self.cond, self.spans = rec, cond, spans
        self.masked, self.mapping = sp.mask(rec["body"], spans)
        self.segs = pp.split_segments(self.masked)
        el = VCFG["sentence_eligibility"]
        self.eligible = [i for i, s in enumerate(self.segs)
                         if pp.is_eligible(s["text"], el["min_alpha_words"], el["long_segment_words"])]
        self.selected = pp.select_indices(self.eligible, rate, derive_rng(SEED, cond, rec["id"]))
        self.rewrites = {}            # idx -> masked rewrite currently in the variant
        self.sent = {}                # idx -> {attempt, nli, nli_ok, spans_ok, ok}
        self.reverted = []            # idx list replaced by the original sentence
        self.truncated = 0
        self.attempt = {}             # attempt -> variant-level check dict

    def original_sentence(self, idx: int) -> str:
        return sp.restore(self.segs[idx]["text"], self.mapping)

    def rewritten_sentence(self, idx: int) -> str:
        return sp.restore(self.rewrites[idx], self.mapping)

    def sentence_spans_ok(self, idx: int) -> bool:
        need = Counter(sp.MASK_RE.findall(self.segs[idx]["text"]))
        have = Counter(sp.MASK_RE.findall(self.rewrites[idx]))
        return all(have[t] >= n for t, n in need.items())

    def generate(self, para: pp.Paraphraser, indices: list, attempt: int) -> None:
        for idx in indices:
            res = para.rewrite(self.segs[idx]["text"], llama_seed(SEED, self.rec["id"], idx, attempt))
            self.rewrites[idx] = res["text"]
            self.truncated += res["finish_reason"] == "length"

    def check_sentences(self, indices: list, attempt: int, ck: Checkers) -> None:
        for idx in indices:
            r = check_sentence(self.original_sentence(idx), self.rewritten_sentence(idx),
                               self.sentence_spans_ok(idx), VCFG["thresholds"]["thr_nli"], ck)
            self.sent[idx] = {"attempt": attempt, **r}

    def body(self) -> str:
        return sp.restore(pp.reassemble(self.segs, self.rewrites), self.mapping)

    def check_variant(self, attempt: int, ck: Checkers) -> dict:
        v = check_variant(self.rec["body"], self.body(), self.spans, VCFG["thresholds"], ck)
        retained = [i for i in self.selected if i in self.rewrites]
        v["nli_per_sentence"] = [self.sent[i]["nli"] for i in retained]
        v["nli_min"] = round(min(v["nli_per_sentence"]), 4) if v["nli_per_sentence"] else 1.0
        v["sentences"] = [{"idx": i, **self.sent[i]} for i in self.selected if i in self.sent]
        v["sentences_failed"] = [i for i in retained if not self.sent[i]["ok"]]
        v["passed"] = v["passed"] and not v["sentences_failed"]
        self.attempt[attempt] = v
        return v

    def failed_sentences(self) -> list:
        return [i for i in self.selected if i in self.rewrites and not self.sent[i]["ok"]]

    def revert_failed(self) -> None:
        for idx in self.failed_sentences():
            del self.rewrites[idx]
            self.reverted.append(idx)

    def achieved_fraction(self) -> float:
        return round((len(self.selected) - len(self.reverted)) / len(self.selected), 4) if self.selected else 1.0


def run_paraphrase(records: list, conds: dict, spans_by_id: dict, model_path: Path, model_sha: str, timings: dict) -> tuple:
    """Attempt 0 for all -> checks -> retry failed sentences -> checks + fallback. Returns (rows, meta)."""
    prompt_text = read_text(ROOT / VCFG["paths"]["prompt"]).strip()
    para = pp.Paraphraser(model_path, model_sha, prompt_text, VCFG["llama"], ROOT / VCFG["paths"]["cache"])
    ck = Checkers(VCFG["embedding"]["model"], VCFG["nli"]["model"])
    min_frac = VCFG["fallback"]["min_achieved_fraction"]
    states = [ParaState(r, c, conds[c]["rate"], spans_by_id[r["id"]]) for c in conds for r in records]

    t0 = time.time()
    for st in states:
        st.generate(para, st.selected, 0)
    para.close(); gc.collect()
    timings["paraphrase_attempt_0"] = round(time.time() - t0, 1)

    t0 = time.time()
    ck.load()
    for st in states:
        st.check_sentences(st.selected, 0, ck)
        st.check_variant(0, ck)
    entail_idx = ck.entail_idx
    ck.close(); gc.collect()
    timings["checks_attempt_0"] = round(time.time() - t0, 1)

    retry = {}                      # state -> indices to regenerate with the new seed
    for st in states:
        if not st.attempt[0]["passed"]:
            failed = st.failed_sentences()
            retry[id(st)] = failed if failed else list(st.selected)   # variant-level failure only: redo all
    if retry:
        t0 = time.time()
        for st in states:
            if id(st) in retry:
                st.generate(para, retry[id(st)], 1)
        para.close(); gc.collect()
        timings["paraphrase_attempt_1"] = round(time.time() - t0, 1)
        t0 = time.time()
        ck.load()
        for st in states:
            if id(st) in retry:
                st.check_sentences(retry[id(st)], 1, ck)
                st.revert_failed()                                     # sentence-level fallback
                st.check_variant(1, ck)
        ck.close(); gc.collect()
        timings["checks_attempt_1"] = round(time.time() - t0, 1)

    rows = []
    for st in states:
        final = 1 if 1 in st.attempt else 0
        frac = st.achieved_fraction()
        v = st.attempt[final]
        failed = [name for name, ok in (("cosine", v["sim_ok"]), ("length", v["len_ok"]), ("spans", v["spans_ok"]),
                                        ("fraction", frac >= min_frac[st.cond])) if not ok]
        if final == 0:
            status = "pass"
        else:
            status = "excluded" if failed else "regenerated"
        rows.append({"variant_id": f"{st.rec['id']}#{st.cond}", "source_id": st.rec["id"], "condition": st.cond,
                     "subject": st.rec["subject"], "body": st.body(),
                     "checks": {"attempt_0": st.attempt[0], "attempt_1": st.attempt.get(1), "final_attempt": final,
                                "n_segments": len(st.segs), "n_eligible": len(st.eligible),
                                "n_selected": len(st.selected), "n_retried": len(retry.get(id(st), [])),
                                "n_reverted": len(st.reverted), "reverted_idx": sorted(st.reverted),
                                "achieved_fraction": frac, "min_achieved_fraction": min_frac[st.cond],
                                "failed_tests": failed, "truncated": st.truncated,
                                "spans": [{"text": s["text"], "label": s["label"]} for s in st.spans]},
                     "status": status})
    meta = {"prompt_sha256": para.prompt_hash, "cache_hits": para.hits, "cache_misses": para.misses,
            "entailment_label_index": entail_idx}
    return rows, meta


# ---- model download ----------------------------------------------------------
def ensure_model(skip_download: bool) -> tuple:
    m = VCFG["model"]
    path = ROOT / m["local_dir"] / m["filename"]
    if not path.exists():
        if skip_download:
            raise SystemExit(f"model missing and --skip-download given: {path}")
        from huggingface_hub import hf_hub_download
        print(f"  downloading {m['repo_id']}/{m['filename']} -> {path.parent.relative_to(ROOT)}/")
        hf_hub_download(repo_id=m["repo_id"], filename=m["filename"], local_dir=str(path.parent))
    digest = sha256_file(path)
    if m.get("expected_sha256") and m["expected_sha256"] != digest:
        raise SystemExit(f"model sha256 mismatch: expected {m['expected_sha256']}, got {digest}")
    print(f"  model {path.name}  sha256 {digest[:16]}...  ({path.stat().st_size / 1e9:.2f} GB)")
    return path, digest


# ---- report and manual sample -------------------------------------------------
def summarise(rows: list, conds: dict, spans_by_id: dict, obf_rows_log_len: int) -> dict:
    out = {}
    for c, spec in conds.items():
        rs = [r for r in rows if r["condition"] == c]
        entry = {"family": spec["family"], "rate": spec["rate"], "produced": len(rs),
                 "status": dict(Counter(r["status"] for r in rs))}
        if spec["family"] == "obfuscation":
            entry.update({
                "integrity_pass": sum(r["checks"]["integrity_ok"] for r in rs),
                "ops": dict(sum((Counter(r["checks"]["ops"]) for r in rs), Counter())),
                "op_redraws": sum(r["checks"]["op_redraws"] for r in rs),
                "n_eligible_tokens": stats([r["checks"]["n_eligible"] for r in rs]),
                "n_selected_tokens": stats([r["checks"]["n_selected"] for r in rs]),
            })
        else:
            fails = {}
            for att in (0, 1):
                ch = [r["checks"][f"attempt_{att}"] for r in rs if r["checks"][f"attempt_{att}"]]
                fails[f"attempt_{att}"] = {
                    "variants_checked": len(ch),
                    **{k: sum(not x[k] for x in ch) for k in VARIANT_CHECKS},
                    "sentences_checked": sum(1 for x in ch for s in x["sentences"] if s["attempt"] == att),
                    "sentences_failed_nli": sum(1 for x in ch for s in x["sentences"] if s["attempt"] == att and not s["nli_ok"]),
                    "sentences_failed_spans": sum(1 for x in ch for s in x["sentences"] if s["attempt"] == att and not s["spans_ok"]),
                }
            final = [r["checks"][f"attempt_{r['checks']['final_attempt']}"] for r in rs]
            fracs = [r["checks"]["achieved_fraction"] for r in rs]
            entry.update({
                "min_achieved_fraction": VCFG["fallback"]["min_achieved_fraction"][c],
                "excluded_failed_tests": {r["variant_id"]: r["checks"]["failed_tests"] for r in rs if r["status"] == "excluded"},
                "exclusion_combos": dict(sorted(Counter("+".join(r["checks"]["failed_tests"]) for r in rs if r["status"] == "excluded").items())),
                "exclusions_involving": {t: sum(t in r["checks"]["failed_tests"] for r in rs if r["status"] == "excluded")
                                         for t in ("cosine", "length", "spans", "fraction")},
                "failures": fails,
                "achieved_fraction": dist(fracs, ("min", "p5", "median", "mean", "max")),
                "achieved_fraction_histogram": {f"{lo:.1f}-{lo + 0.2:.1f}": sum(lo <= f < lo + 0.2 or (f == 1.0 and lo == 0.8) for f in fracs)
                                                for lo in (0.0, 0.2, 0.4, 0.6, 0.8)},
                "n_retried": stats([r["checks"]["n_retried"] for r in rs]),
                "n_reverted": stats([r["checks"]["n_reverted"] for r in rs]),
                "sim_cos": dist([x["sim_cos"] for x in final]),
                "nli_min": dist([x["nli_min"] for x in final]),
                "len_ratio": dist([x["len_ratio"] for x in final], ("min", "median", "max")),
                "n_segments": stats([r["checks"]["n_segments"] for r in rs]),
                "n_eligible_segments": stats([r["checks"]["n_eligible"] for r in rs]),
                "n_selected_segments": stats([r["checks"]["n_selected"] for r in rs]),
                "truncated_generations": sum(r["checks"]["truncated"] for r in rs),
            })
        out[c] = entry
    out["_spans_per_record"] = {**stats([len(v) for v in spans_by_id.values()]),
                                "by_label": dict(sorted(Counter(s["label"] for v in spans_by_id.values() for s in v).items()))}
    out["_obfuscation_log_rows"] = obf_rows_log_len
    return out


def write_manual_sample(rows: list, by_id: dict, conds: dict, path: Path) -> dict:
    """Stratified 10 % per condition, plus every excluded paraphrase and a seeded sample of
    regenerated paraphrases; each row carries its automatic outcome."""
    ms = VCFG["target"]["manual_sample"]
    by_vid = {r["variant_id"]: r for r in rows}
    picked, origin = [], {}
    for c in conds:
        ids = sorted(r["variant_id"] for r in rows if r["condition"] == c)
        k = int(round(ms["fraction"] * len(ids)))
        for v in derive_rng(SEED, "manual_sample", c).sample(ids, k):
            picked.append(v); origin[v] = "stratified"
    para_ids = sorted(r["variant_id"] for r in rows if conds[r["condition"]]["family"] == "paraphrase")
    if ms["add_all_excluded"]:
        for v in para_ids:
            if by_vid[v]["status"] == "excluded" and v not in origin:
                picked.append(v); origin[v] = "all_excluded"
    pool = [v for v in para_ids if by_vid[v]["status"] == "regenerated" and v not in origin]
    k = min(ms["add_regenerated"], len(pool))
    for v in derive_rng(SEED, "manual_sample", "regenerated").sample(pool, k):
        picked.append(v); origin[v] = "regenerated_sample"
    order = {c: i for i, c in enumerate(VCFG["conditions"])}
    picked = sorted(set(picked), key=lambda v: (order[by_vid[v]["condition"]], v))
    with open_utf8(path, "w") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["variant_id", "condition", "auto_outcome", "failed_tests", "original_body", "variant_body",
                    "rating_A", "rating_B", "readability_A", "readability_B", "notes"])
        for vid in picked:
            r = by_vid[vid]
            readability = "" if conds[r["condition"]]["family"] == "obfuscation" else "n/a"
            w.writerow([vid, r["condition"], r["status"], "+".join(r["checks"].get("failed_tests", [])),
                        by_id[r["source_id"]]["body"], r["body"], "", "", readability, readability, ""])
    return {"file": str(path.relative_to(ROOT)), "rows": len(picked), "config": ms,
            "per_condition": dict(Counter(by_vid[v]["condition"] for v in picked)),
            "per_origin": dict(Counter(origin[v] for v in picked)),
            "per_auto_outcome": dict(Counter(by_vid[v]["status"] for v in picked))}


# ---- main -------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--conditions", default=",".join(VCFG["conditions"]), help="comma-separated subset")
    ap.add_argument("--limit", type=int, default=0, help="process only the first N target records")
    ap.add_argument("--selftest", action="store_true", help="run synthetic round-trip tests and exit")
    ap.add_argument("--skip-download", action="store_true", help="fail if the GGUF is not already present")
    args = ap.parse_args()
    if args.selftest:
        from variants.selftest import run
        return run()

    conds = {c: VCFG["conditions"][c] for c in args.conditions.split(",") if c}
    timings, t_start = {}, time.time()
    records, target = load_targets(args.limit)
    by_id = {r["id"]: r for r in records}
    print(f"targets: {target['n_records']} {target['subclass']} records from '{target['partition']}' "
          f"(disjoint from {len(EVAL_PARTITIONS)} evaluation partitions, {target['n_eval_ids']} ids)")

    model_info = {"paraphrase_model": VCFG["model"], "excluded_from_detectors": VCFG["excluded_from_detectors"],
                  "llama": VCFG["llama"], "embedding": VCFG["embedding"]["model"], "nli": VCFG["nli"]["model"]}
    if any(s["family"] == "paraphrase" for s in conds.values()):
        import llama_cpp
        model_path, model_sha = ensure_model(args.skip_download)
        model_info.update({"model_sha256": model_sha, "llama_cpp_version": llama_cpp.__version__})

    t0 = time.time()
    spans_by_id = compute_spans(records)
    timings["spans"] = round(time.time() - t0, 1)
    print(f"spans: {sum(len(v) for v in spans_by_id.values())} protected spans over {len(records)} records")

    rows, obf_log = [], []
    t0 = time.time()
    for c, spec in conds.items():
        if spec["family"] == "obfuscation":
            r, log = derive_obfuscation(records, c, spec["rate"], spans_by_id)
            rows.extend(r); obf_log.extend(log)
            print(f"{c}: {len(r)} variants, {len(log)} edits, integrity {sum(x['checks']['integrity_ok'] for x in r)}/{len(r)}")
    timings["obfuscation"] = round(time.time() - t0, 1)

    para_conds = {c: s for c, s in conds.items() if s["family"] == "paraphrase"}
    if para_conds:
        prow, meta = run_paraphrase(records, para_conds, spans_by_id, model_path, model_sha, timings)
        rows.extend(prow)
        model_info.update(meta)
        for c in para_conds:
            rs = [r for r in prow if r["condition"] == c]
            st = Counter(r["status"] for r in rs)
            fr = dist([r["checks"]["achieved_fraction"] for r in rs], ("min", "median", "mean"))
            print(f"{c}: {len(rs)} variants  pass {st['pass']}  regenerated {st['regenerated']}  excluded {st['excluded']}"
                  f"  | reverted sentences {sum(r['checks']['n_reverted'] for r in rs)}  achieved_fraction min/median/mean "
                  f"{fr['min']}/{fr['median']}/{fr['mean']}")

    order = {c: i for i, c in enumerate(VCFG["conditions"])}
    rows.sort(key=lambda r: (order[r["condition"]], r["source_id"]))
    obf_log.sort(key=lambda e: (order[e["variant_id"].split("#")[1]], e["variant_id"], e["position"]))
    PROC.mkdir(parents=True, exist_ok=True)
    with open_utf8(PROC / "variants_dev.jsonl", "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open_utf8(PROC / "obfuscation_log_dev.jsonl", "w") as fh:
        for e in obf_log:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    sample = write_manual_sample(rows, by_id, conds, REPORTS / "manual_review_sample_dev.csv")
    cache_stats = {k: model_info.pop(k, None) for k in ("cache_hits", "cache_misses")}   # run-dependent -> runtime file
    report = {"seed": SEED, "target": target, "model": model_info, "thresholds": VCFG["thresholds"],
              "fallback": VCFG["fallback"], "conditions": summarise(rows, conds, spans_by_id, len(obf_log)),
              "manual_sample": sample, "config": VCFG}
    write_json(REPORTS / "variants_dev_report.json", report)
    timings["total"] = round(time.time() - t_start, 1)
    write_json(REPORTS / "variants_dev_runtime.json",
               {"finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "seconds": timings,
                "cache": cache_stats})

    print(f"\nvariants -> {(PROC / 'variants_dev.jsonl').relative_to(ROOT)}  ({len(rows)} rows)")
    print(f"manual sample -> {sample['file']}  ({sample['rows']} rows: {sample['per_origin']})")
    print(f"report -> reports/variants_dev_report.json   runtime {timings['total']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
