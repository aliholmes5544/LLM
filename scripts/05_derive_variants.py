#!/usr/bin/env python3
"""
05_derive_variants.py — derive paraphrased and obfuscated variants and check them (Section 3.2.3).

Two targets:
  --target dev  (default): the 100 dev `ephish_phish` emails (LLM-generated, personalized), used to
                calibrate the checks; asserted disjoint from every evaluation partition.
  --target eval: the partitions and conditions named in configs/variants_eval.yaml (Table 3.2):
                core_pos x four conditions, ctrl_para_legit x para_high only. Run once with the frozen
                configs/variants.yaml (run_variants_eval.sh checks it is identical to HEAD, runs twice
                and compares hashes). No manual sample is drawn; the dev residual-error estimate stands.

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
     Logical rule for every condition: a body byte-identical to its original is not a variant
     and is excluded with reason "unchanged" (e.g. every selected sentence reverted, or no
     eligible sentence at all).
  6. outputs, report and the manual-review sample (stratified 10 % + every excluded
     paraphrase + a seeded sample of regenerated ones, each flagged with auto_outcome)

Usage:  python scripts/05_derive_variants.py [--target dev|eval] [--conditions a,b] [--limit N] [--dry-run]
                                             [--selftest] [--skip-download]
Output (dev):  data/processed/variants_dev.jsonl, data/processed/obfuscation_log_dev.jsonl,
               reports/variants_dev_report.json, reports/manual_review_sample_dev.csv,
               reports/variants_dev_runtime.json (timings only; not byte-stable)
Output (eval): the paths in configs/variants_eval.yaml (variants_eval.jsonl, obfuscation_log_eval.jsonl,
               reports/variants_eval_report.json with the comparison against the dev exclusion rates)
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
ECFG = load_config("variants_eval.yaml")                               # eval targets and output paths only
SEED = CFG["seed"]
PROC = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
EVAL_PARTITIONS = ("core_pos", "core_neg", "ctrl_para_legit", "ctrl_modern_legit", "gen_phish", "gen_legit")
VARIANT_CHECKS = ("sim_ok", "len_ok", "spans_ok")
PROGRESS_EVERY = 50                                                     # states between progress lines


def progress(i: int, n: int, t0: float, label: str) -> None:
    """One stdout line every PROGRESS_EVERY items (and at the end) for the long eval run."""
    if i % PROGRESS_EVERY == 0 or i == n:
        el = time.time() - t0
        eta = el / i * (n - i) if i else 0.0
        print(f"  {label}: {i}/{n}  elapsed {el / 60:.1f} min  eta {eta / 60:.1f} min", flush=True)


def sha256_text(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
def load_targets(target: str, limit: int, cond_filter: list) -> tuple:
    """Plan of (record, condition) pairs. dev: the configured partition/subclass (variants.yaml: target),
    asserted disjoint from every evaluation partition. eval: the partitions and conditions named in
    configs/variants_eval.yaml, asserted to touch no training or development item. Returns
    (records, by_cond, pairs, info): unique records, records per condition, paraphrase/obfuscation pairs
    in condition order, and the description written to the report."""
    recs = [json.loads(l) for l in open_utf8(PROC / "records.jsonl")]
    by_id = {r["id"]: r for r in recs}
    parts = json.loads(read_text(PROC / "partitions.json"))
    eval_ids = set().union(*(set(parts[k]) for k in EVAL_PARTITIONS))
    if target == "dev":
        t = VCFG["target"]
        ids = sorted(i for i in parts[t["partition"]] if by_id[i]["subclass"] == t["subclass"])
        assert set(ids).isdisjoint(eval_ids), "step 05 must never touch an evaluation partition"
        assert ids, f"no {t['subclass']} records in partition {t['partition']}"
        info = {"partition": t["partition"], "subclass": t["subclass"], "n_available": len(ids),
                "eval_partitions_checked": list(EVAL_PARTITIONS), "n_eval_ids": len(eval_ids), "disjoint": True}
        if limit:
            ids = ids[:limit]
        info["n_records"] = len(ids)
        groups = {t["partition"]: {"ids": ids, "conditions": [c for c in VCFG["conditions"] if c in cond_filter]}}
    else:
        groups, info = {}, {"target": "eval", "partitions": {}}
        for part, spec in ECFG["targets"].items():
            assert part in EVAL_PARTITIONS, f"{part} is not an evaluation partition"
            bad = [c for c in spec["conditions"] if c not in VCFG["conditions"]]
            assert not bad, f"unknown conditions {bad} for {part}"
            ids = sorted(parts[part])
            if limit:
                ids = ids[:limit]
            groups[part] = {"ids": ids, "conditions": list(spec["conditions"])}
            info["partitions"][part] = {"n_available": len(parts[part]), "n_records": len(ids),
                                        "conditions": list(spec["conditions"]),
                                        "subclasses": dict(Counter(by_id[i]["subclass"] for i in ids))}
        touched = set().union(*(set(g["ids"]) for g in groups.values()))
        overlap = {k: len(touched & set(parts[k])) for k in parts if k not in groups}
        protected = {k: n for k, n in overlap.items() if k not in EVAL_PARTITIONS and n}
        assert not protected, f"evaluation variants would touch non-evaluation items: {protected}"
        # ctrl_para_legit is by design a seeded sample of core_neg (Table 3.2), so an overlap with core_neg is expected
        info.update({"n_records_unique": len(touched), "overlap_with_other_partitions": overlap,
                     "disjoint_from_train_dev_valid": True})
    order = list(VCFG["conditions"])
    by_cond = {c: [by_id[i] for g in groups.values() if c in g["conditions"] for i in g["ids"]] for c in order}
    by_cond = {c: rs for c, rs in by_cond.items() if rs}
    pairs = [(r, c) for c in by_cond for r in by_cond[c]]
    seen, records = set(), []
    for g in groups.values():
        for i in g["ids"]:
            if i not in seen:
                seen.add(i); records.append(by_id[i])
    return records, by_cond, pairs, info


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
        failed = ([] if integrity else ["integrity"]) + unchanged_test(variant, r["body"])
        rows.append({"variant_id": vid, "source_id": r["id"], "condition": cond, "subject": r["subject"],
                     "body": variant, "checks": {"integrity_ok": integrity, **st,
                                                  "spans": [{"text": s["text"], "label": s["label"]} for s in spans],
                                                  "failed_tests": failed},
                     "status": "excluded" if failed else "pass"})
    return rows, log


def unchanged_test(variant_body: str, original_body: str) -> list:
    """Logical rule, not a threshold: a body byte-identical to its original is not a variant and is
    excluded with reason "unchanged" (all partitions and conditions). Returns [] or ["unchanged"]."""
    return ["unchanged"] if variant_body == original_body else []


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


def run_paraphrase(pairs: list, conds: dict, spans_by_id: dict, model_path: Path, model_sha: str,
                   timings: dict, cache_path: Path) -> tuple:
    """Attempt 0 for all (record, condition) pairs -> checks -> retry failed sentences -> checks + fallback.
    Returns (rows, meta)."""
    prompt_text = read_text(ROOT / VCFG["paths"]["prompt"]).strip()
    para = pp.Paraphraser(model_path, model_sha, prompt_text, VCFG["llama"], cache_path)
    ck = Checkers(VCFG["embedding"]["model"], VCFG["nli"]["model"])
    min_frac = VCFG["fallback"]["min_achieved_fraction"]
    states = [ParaState(r, c, conds[c]["rate"], spans_by_id[r["id"]]) for r, c in pairs]
    n = len(states)

    t0 = time.time()
    for i, st in enumerate(states, start=1):
        st.generate(para, st.selected, 0)
        progress(i, n, t0, "paraphrase attempt 0")
    para.close(); gc.collect()
    timings["paraphrase_attempt_0"] = round(time.time() - t0, 1)

    t0 = time.time()
    ck.load()
    for i, st in enumerate(states, start=1):
        st.check_sentences(st.selected, 0, ck)
        st.check_variant(0, ck)
        progress(i, n, t0, "checks attempt 0")
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
        todo = [st for st in states if id(st) in retry]
        for i, st in enumerate(todo, start=1):
            st.generate(para, retry[id(st)], 1)
            progress(i, len(todo), t0, "paraphrase attempt 1")
        para.close(); gc.collect()
        timings["paraphrase_attempt_1"] = round(time.time() - t0, 1)
        t0 = time.time()
        ck.load()
        for i, st in enumerate(todo, start=1):
            st.check_sentences(retry[id(st)], 1, ck)
            st.revert_failed()                                     # sentence-level fallback
            st.check_variant(1, ck)
            progress(i, len(todo), t0, "checks attempt 1")
        ck.close(); gc.collect()
        timings["checks_attempt_1"] = round(time.time() - t0, 1)

    rows = []
    for st in states:
        final = 1 if 1 in st.attempt else 0
        frac = st.achieved_fraction()
        v = st.attempt[final]
        failed = [name for name, ok in (("cosine", v["sim_ok"]), ("length", v["len_ok"]), ("spans", v["spans_ok"]),
                                        ("fraction", frac >= min_frac[st.cond])) if not ok]
        failed += unchanged_test(st.body(), st.rec["body"])
        if "unchanged" in failed:
            status = "excluded"
        elif final == 0:
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
                "excluded_failed_tests": {r["variant_id"]: r["checks"]["failed_tests"] for r in rs if r["status"] == "excluded"},
                "exclusion_combos": dict(sorted(Counter("+".join(r["checks"]["failed_tests"]) for r in rs if r["status"] == "excluded").items())),
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
                                         for t in ("cosine", "length", "spans", "fraction", "unchanged")},
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
    if path.exists():                    # never overwrite a sample that already carries ratings (frozen after rating)
        with open_utf8(path) as fh:
            rated = sum(any(v.strip() for k, v in row.items() if k.startswith("rating_")) for row in csv.DictReader(fh))
        if rated:
            print(f"manual sample kept: {path.relative_to(ROOT)} already holds {rated} rated rows (not rewritten)")
            return {"file": str(path.relative_to(ROOT)), "kept_existing_rated_sample": True, "rows_rated": rated,
                    "would_pick_now": {"rows": len(picked), "per_origin": dict(Counter(origin[v] for v in picked)),
                                       "per_auto_outcome": dict(Counter(by_vid[v]["status"] for v in picked))}}
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
    ap.add_argument("--target", choices=("dev", "eval"), default="dev",
                    help="dev: calibration target from variants.yaml; eval: partitions from variants_eval.yaml")
    ap.add_argument("--dry-run", action="store_true", help="print the plan (records, conditions, pairs) and exit")
    args = ap.parse_args()
    if args.selftest:
        from variants.selftest import run
        return run()

    cond_filter = [c for c in args.conditions.split(",") if c]
    if args.target == "eval" and cond_filter != list(VCFG["conditions"]):
        raise SystemExit("--conditions is not accepted with --target eval; the conditions come from configs/variants_eval.yaml")
    timings, t_start = {}, time.time()
    records, by_cond, pairs, target = load_targets(args.target, args.limit, cond_filter)
    by_id = {r["id"]: r for r in records}
    conds = {c: VCFG["conditions"][c] for c in by_cond}
    if args.target == "dev":
        out = {"variants": PROC / "variants_dev.jsonl", "obfuscation_log": PROC / "obfuscation_log_dev.jsonl",
               "report": REPORTS / "variants_dev_report.json", "runtime": REPORTS / "variants_dev_runtime.json",
               "cache": ROOT / VCFG["paths"]["cache"]}
        print(f"targets: {target['n_records']} {target['subclass']} records from '{target['partition']}' "
              f"(disjoint from {len(EVAL_PARTITIONS)} evaluation partitions, {target['n_eval_ids']} ids)")
    else:
        out = {k: ROOT / v for k, v in ECFG["outputs"].items()}
        for part, p in target["partitions"].items():
            print(f"targets: {part}: {p['n_records']} records {p['subclasses']} -> {p['conditions']}")
        print(f"targets: {target['n_records_unique']} unique records; overlap with other partitions "
              f"{target['overlap_with_other_partitions']} (ctrl_para_legit is a sample of core_neg by design)")
    plan = {c: len(rs) for c, rs in by_cond.items()}
    print(f"plan: {plan}  paraphrase pairs {sum(n for c, n in plan.items() if conds[c]['family'] == 'paraphrase')}  "
          f"cache {out['cache'].relative_to(ROOT)}")
    if args.dry_run:
        return 0

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
            r, log = derive_obfuscation(by_cond[c], c, spec["rate"], spans_by_id)
            rows.extend(r); obf_log.extend(log)
            print(f"{c}: {len(r)} variants, {len(log)} edits, integrity {sum(x['checks']['integrity_ok'] for x in r)}/{len(r)}")
    timings["obfuscation"] = round(time.time() - t0, 1)

    para_conds = {c: s for c, s in conds.items() if s["family"] == "paraphrase"}
    para_pairs = [(r, c) for r, c in pairs if c in para_conds]
    if para_pairs:
        prow, meta = run_paraphrase(para_pairs, para_conds, spans_by_id, model_path, model_sha, timings, out["cache"])
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
    with open_utf8(out["variants"], "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open_utf8(out["obfuscation_log"], "w") as fh:
        for e in obf_log:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    cache_stats = {k: model_info.pop(k, None) for k in ("cache_hits", "cache_misses")}   # run-dependent -> runtime file
    if args.target == "dev":
        sample = write_manual_sample(rows, by_id, conds, REPORTS / "manual_review_sample_dev.csv")
        report = {"seed": SEED, "target": target, "model": model_info, "thresholds": VCFG["thresholds"],
                  "fallback": VCFG["fallback"], "conditions": summarise(rows, conds, spans_by_id, len(obf_log)),
                  "manual_sample": sample, "config": VCFG}
    else:
        sample = None
        report = eval_report(rows, obf_log, spans_by_id, target, model_info)
    write_json(out["report"], report)
    timings["total"] = round(time.time() - t_start, 1)
    write_json(out["runtime"], {"finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                "seconds": timings, "cache": cache_stats,
                                "config_sha256": report.get("config_sha256")})

    print(f"\nvariants -> {out['variants'].relative_to(ROOT)}  ({len(rows)} rows)")
    if sample is None:
        print("manual sample: none (evaluation data are not reviewed; the dev residual-error estimate stands)")
        for key, flag in report["dev_comparison"]["flags"].items():
            if flag:
                print(f"FLAG: {key} exclusion rate exceeds the dev rate by more than {ECFG['flag_exclusion_rate_above_dev_pp']} points")
    elif sample.get("kept_existing_rated_sample"):
        print(f"manual sample -> {sample['file']}  (kept: {sample['rows_rated']} rated rows; a fresh draw would give {sample['would_pick_now']})")
    else:
        print(f"manual sample -> {sample['file']}  ({sample['rows']} rows: {sample['per_origin']})")
    print(f"report -> {out['report'].relative_to(ROOT)}   runtime {timings['total']} s")
    return 0


def eval_report(rows: list, obf_log: list, spans_by_id: dict, target: dict, model_info: dict) -> dict:
    """Per-partition summaries (same fields as the dev report), the exclusion list with reasons, and the
    comparison of exclusion rates with the dev run (flag above the configured margin). The cache spot check
    written by scripts/05c_spot_check_cache.py is re-attached when present, so a rerun keeps it."""
    parts = json.loads(read_text(PROC / "partitions.json"))
    partitions = {}
    for part, spec in ECFG["targets"].items():
        ids = set(parts[part])
        prow = [r for r in rows if r["source_id"] in ids and r["condition"] in spec["conditions"]]
        conds = {c: VCFG["conditions"][c] for c in spec["conditions"]}
        vids = {r["variant_id"] for r in prow}
        n_log = sum(e["variant_id"] in vids for e in obf_log)
        partitions[part] = summarise(prow, conds, {i: spans_by_id[i] for i in ids if i in spans_by_id}, n_log)
    exclusions = [{"variant_id": r["variant_id"], "condition": r["condition"],
                   "partition": next(p for p, s in ECFG["targets"].items() if r["source_id"] in set(parts[p])),
                   "reasons": r["checks"]["failed_tests"],
                   "sim_cos": r["checks"].get(f"attempt_{r['checks'].get('final_attempt', 0)}", {}).get("sim_cos"),
                   "achieved_fraction": r["checks"].get("achieved_fraction")}
                  for r in rows if r["status"] == "excluded"]
    dev = json.loads(read_text(ROOT / ECFG["dev_report"]))
    margin = ECFG["flag_exclusion_rate_above_dev_pp"]
    comparison, flags = {}, {}
    for part, summ in partitions.items():
        for c, entry in summ.items():
            if c.startswith("_"):
                continue
            d = dev["conditions"][c]
            dev_rate = d["status"].get("excluded", 0) / d["produced"]
            rate = entry["status"].get("excluded", 0) / entry["produced"]
            key = f"{part}/{c}"
            comparison[key] = {"eval_excluded": entry["status"].get("excluded", 0), "eval_produced": entry["produced"],
                               "eval_rate": round(rate, 4), "dev_excluded": d["status"].get("excluded", 0),
                               "dev_produced": d["produced"], "dev_rate": round(dev_rate, 4),
                               "difference_pp": round(100 * (rate - dev_rate), 2)}
            flags[key] = 100 * (rate - dev_rate) > margin
    config_sha = {"configs/variants.yaml": sha256_text(ROOT / "configs" / "variants.yaml"),
                  "configs/variants_eval.yaml": sha256_text(ROOT / "configs" / "variants_eval.yaml"),
                  VCFG["paths"]["prompt"]: sha256_text(ROOT / VCFG["paths"]["prompt"])}
    spot = ROOT / "reports" / "variants_eval_spot_check.json"
    spot_check = json.loads(read_text(spot)) if spot.exists() else None
    fixed = ROOT / "reports" / "variants_eval_fixed_artifacts.json"          # written by 05d; re-attached here
    fixed_artifacts = json.loads(read_text(fixed)) if fixed.exists() else None
    return {"seed": SEED, "target": target, "config_sha256": config_sha, "model": model_info,
            "thresholds": VCFG["thresholds"], "fallback": VCFG["fallback"], "partitions": partitions,
            "exclusions": exclusions,
            "dev_comparison": {"dev_report": ECFG["dev_report"], "dev_thresholds": dev["thresholds"],
                               "margin_pp": margin, "per_condition": comparison, "flags": flags},
            "config": VCFG, "eval_config": ECFG, "cache_spot_check": spot_check,
            "fixed_artifacts": fixed_artifacts}


if __name__ == "__main__":
    sys.exit(main())
