#!/usr/bin/env python3
"""
07_secondary.py — step 07, step 3, the pre-registered secondary analyses (TASK_07 section 4; QUESTIONS.md
item 12 a to d with refinements 3, 4 and 7; item 16 decisions). Runs after 07_score.py and reads its outputs.

  (a) ensemble      results/scores/ensemble_votes.csv       vote composition per strategy (the ensemble's
                                                           metrics are in metrics_long / deltas_long)
  (b) cue analysis  results/scores/cues_frequency.csv       per model x item group x category: rationales with
                                                           text, asserted, negated-only, empty-rationale rate
                    results/scores/cues_change.csv          per model x condition x category x outcome: pairs
                                                           with the cue kept / lost / gained / never asserted
                    results/scores/cues_pairs.csv           pairs used and excluded (empty rationale) per cell
  (c) hard core     results/scores/hardcore_items.csv       zero_shot, six models: items by number of models wrong
                    results/scores/hardcore_summary.csv     all-six vs none by item group, source, body length
                    reports/hardcore_sample.csv             seeded stratified sample of 30 all-six failures for
                                                           the author's coding (failure_type, note empty)
                    data/processed/hardcore_sample_text.jsonl  the sampled texts (data, git-ignored)
  (d) frontier      results/scores/frontier.csv             median GPU latency vs delta-sens per model x strategy
  reports/secondary_report.json                             inputs, hashes, counts, runtime
--check recomputes everything and compares the CSVs byte for byte with disk.

Usage: python scripts/07_secondary.py [--check]
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from common import ROOT, load_config, read_text, write_json, cot_rationale, open_utf8
from detect.items import load_records
from scoring.cues import CATEGORIES, load_lexicon, lexicon_sha256
from scoring.ensemble import vote_summary
from scoring.items import load_jsonl
from scoring.output import compare_outputs, sha256_file, write_csv
from scoring.score import MODELS, STRATEGIES, PHISH_CONDITIONS, CONTROL, BASELINES, group_of, GROUPS
from variants.rng import derive_rng

SCORES = ROOT / "results" / "scores"
LEXICON = ROOT / "configs" / "cue_lexicon.yaml"
INTEGRITY = ROOT / "reports" / "integrity_check.json"
RUN_REPORT = ROOT / "reports" / "detection_run_report.json"
BASE_REPORT = ROOT / "reports" / "baselines_report.json"
REPORT = ROOT / "reports" / "secondary_report.json"
SAMPLE = ROOT / "reports" / "hardcore_sample.csv"
SAMPLE_TEXT = ROOT / "data" / "processed" / "hardcore_sample_text.jsonl"
VARIANTS = ROOT / "data" / "processed" / "variants_eval.jsonl"
OUTPUTS = ("ensemble_votes.csv", "cues_frequency.csv", "cues_change.csv", "cues_pairs.csv", "hardcore_items.csv",
           "hardcore_summary.csv", "frontier.csv")
OUTCOMES = ["stayed_correct", "flipped_to_incorrect", "stayed_incorrect", "flipped_to_correct"]
SAMPLE_N, SAMPLE_MIN = 30, 5


def git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def load_scored() -> tuple:
    rep = json.loads(read_text(ROOT / "reports" / "scoring_report.json"))
    for name in ("metrics_long.csv", "deltas_long.csv", "ensemble_predictions.csv"):
        if sha256_file(SCORES / name) != rep["outputs"][name]:
            raise SystemExit(f"{name} differs from scoring_report.json; run 07_score.py first")
    items = pd.read_parquet(SCORES / "items.parquet")
    items["group"] = [group_of(a, b) for a, b in zip(items["item_class"], items["condition"])]
    items["correct"] = (items["label_pred"] == items["label_true"]) & ~items["invalid"]
    pairs = pd.read_csv(SCORES / "pairs.csv")
    ens = pd.read_csv(SCORES / "ensemble_predictions.csv")
    deltas = pd.read_csv(SCORES / "deltas_long.csv")
    return items, pairs, ens, deltas, rep


# ---------------------------------------------------------------- (b) cue analysis

def cot_raw(integrity: dict) -> tuple:
    """raw cot eval rows of the six models, hash-verified against the integrity report; {(model, item_id): raw}."""
    raw, hashes = {}, {}
    for key, c in integrity["cells"].items():
        if c["strategy"] != "cot":
            continue
        p = ROOT / c["file"]
        sha = sha256_file(p)
        if sha != c["file_sha256"]:
            raise SystemExit(f"{c['file']}: sha256 differs from the integrity report")
        hashes[c["file"]] = sha
        for r in load_jsonl(p):
            raw[(c["model"], r["item_id"])] = r["raw_output"]
    return raw, hashes


def cue_tables(items: pd.DataFrame, pairs: pd.DataFrame, raw: dict, lex) -> tuple:
    cot = items[(items["kind"] == "llm") & (items["strategy"] == "cot")].set_index(["detector", "item_id"], drop=False)
    flags = {}
    for (m, iid) in cot.index:
        text = cot_rationale(raw[(m, iid)])
        if not text:
            flags[(m, iid)] = (None, None)          # empty rationale: no cue, excluded from the denominators
            continue
        f = lex.cue_flags(text)
        flags[(m, iid)] = ({c: f[c]["asserted"] for c in CATEGORIES}, {c: f[c]["negated"] for c in CATEGORIES})
    # frequency per model x group x category
    rows = []
    for m in MODELS:
        d = cot.loc[m]
        for grp in GROUPS:
            ids = d[d["group"] == grp]["item_id"].tolist()
            fl = [flags[(m, i)] for i in ids]
            n_text = sum(1 for a, _ in fl if a is not None)
            for c in CATEGORIES:
                n_as = sum(1 for a, _ in fl if a is not None and a[c])
                n_ng = sum(1 for a, g in fl if a is not None and g[c])
                rows.append({"model": m, "group": grp, "category": c, "n_rows": len(ids), "n_text": n_text,
                             "n_empty": len(ids) - n_text, "empty_rate": (len(ids) - n_text) / len(ids),
                             "n_asserted": n_as, "n_negated_only": n_ng,
                             "freq_asserted": n_as / n_text if n_text else np.nan,
                             "freq_negated_only": n_ng / n_text if n_text else np.nan})
    freq = pd.DataFrame(rows)
    # change per pair, split by outcome
    change, used = [], []
    for m in MODELS:
        d = cot.loc[m].set_index("item_id")
        for cond in PHISH_CONDITIONS + [CONTROL]:
            pp = pairs[pairs["item_class"] == "legit_ctrl_para"] if cond == CONTROL else \
                pairs[(pairs["item_class"] == "phish_variant") & (pairs["condition"] == cond)]
            cnt = Counter()
            n_used = n_excl = 0
            for o_id, v_id in zip(pp["cluster"], pp["variant_id"]):
                fo, fv = flags[(m, o_id)][0], flags[(m, v_id)][0]
                if fo is None or fv is None:
                    n_excl += 1
                    continue
                n_used += 1
                oc, vc = bool(d.at[o_id, "correct"]), bool(d.at[v_id, "correct"])
                outcome = OUTCOMES[0] if oc and vc else OUTCOMES[1] if oc and not vc else OUTCOMES[2] if not oc and not vc else OUTCOMES[3]
                cnt[("_pairs", outcome)] += 1
                for c in CATEGORIES:
                    state = "kept" if fo[c] and fv[c] else "lost" if fo[c] else "gained" if fv[c] else "never"
                    cnt[(c, outcome, state)] += 1
            for outcome in OUTCOMES:
                for c in CATEGORIES:
                    r = {"model": m, "condition": cond, "category": c, "outcome": outcome, "n_pairs": cnt[("_pairs", outcome)]}
                    for st in ("kept", "lost", "gained", "never"):
                        r[st] = cnt[(c, outcome, st)]
                    r["share_lost"] = r["lost"] / r["n_pairs"] if r["n_pairs"] else np.nan
                    r["share_gained"] = r["gained"] / r["n_pairs"] if r["n_pairs"] else np.nan
                    r["net_change"] = (r["gained"] - r["lost"]) / r["n_pairs"] if r["n_pairs"] else np.nan
                    change.append(r)
            used.append({"model": m, "condition": cond, "n_pairs_total": len(pp), "n_pairs_used": n_used,
                         "n_pairs_excluded_empty_rationale": n_excl,
                         **{o: cnt[("_pairs", o)] for o in OUTCOMES}})
    return freq, pd.DataFrame(change), pd.DataFrame(used)


# ---------------------------------------------------------------- (c) hard core

def hardcore(items: pd.DataFrame, seed: int) -> tuple:
    zs = items[(items["kind"] == "llm") & (items["strategy"] == "zero_shot")]
    wrong = (~zs["correct"]).groupby(zs["item_id"]).sum()
    meta = zs.drop_duplicates("item_id").set_index("item_id")
    hc = meta[["cluster", "group", "item_class", "condition", "partition", "source", "subclass", "label_true", "body_words"]].copy()
    hc["n_models_wrong"] = wrong.reindex(hc.index).astype(int)
    hc["hard_group"] = np.where(hc["n_models_wrong"] == 6, "all_six", np.where(hc["n_models_wrong"] == 0, "none", "some"))
    preds = zs.pivot(index="item_id", columns="detector", values="label_pred")
    for m in MODELS:
        hc[f"pred_{m}"] = preds.loc[hc.index, m]
    hc = hc.reset_index().sort_values(["group", "item_id"]).reset_index(drop=True)
    rows = []
    for grp in GROUPS:
        d = hc[hc["group"] == grp]
        for hg in ("all_six", "none", "some"):
            s = d[d["hard_group"] == hg]
            rows.append({"group": grp, "hard_group": hg, "n": len(s), "share": len(s) / len(d) if len(d) else np.nan,
                         "body_words_median": float(s["body_words"].median()) if len(s) else np.nan,
                         "body_words_q1": float(s["body_words"].quantile(0.25)) if len(s) else np.nan,
                         "body_words_q3": float(s["body_words"].quantile(0.75)) if len(s) else np.nan,
                         **{f"source_{src}": int((s["source"] == src).sum()) for src in sorted(hc["source"].unique())},
                         **{f"subclass_{sc}": int((s["subclass"] == sc).sum()) for sc in sorted(hc["subclass"].unique())}})
    summary = pd.DataFrame(rows)
    # stratified sample of all-six failures, strata = the four phishing variant conditions
    fails = hc[(hc["hard_group"] == "all_six") & (hc["item_class"] == "phish_variant")]
    avail = {c: int((fails["condition"] == c).sum()) for c in PHISH_CONDITIONS}
    alloc = allocate(avail, SAMPLE_N, SAMPLE_MIN)
    sample = []
    for c in PHISH_CONDITIONS:
        ids = sorted(fails[fails["condition"] == c]["item_id"])
        pick = derive_rng(seed, "hardcore_sample", c).sample(ids, alloc[c]) if alloc[c] else []
        for iid in pick:
            sample.append(iid)
    smp = hc.set_index("item_id").loc[sample].reset_index()
    smp.insert(0, "sample_id", range(1, len(smp) + 1))
    smp["failure_type"], smp["note"] = "", ""
    return hc, summary, smp, avail, alloc


def allocate(avail: dict, total: int, minimum: int) -> dict:
    """Proportional allocation (largest remainder) with a minimum per stratum when available, capped at availability."""
    strata = list(avail)
    n_avail = sum(avail.values())
    if n_avail <= total:
        return dict(avail)
    exact = {s: total * avail[s] / n_avail for s in strata}
    alloc = {s: int(exact[s]) for s in strata}
    for s in sorted(strata, key=lambda s: exact[s] - alloc[s], reverse=True):
        if sum(alloc.values()) >= total:
            break
        alloc[s] += 1
    for s in strata:                                   # minimum where available
        if alloc[s] < minimum and avail[s] >= minimum:
            alloc[s] = minimum
    alloc = {s: min(alloc[s], avail[s]) for s in strata}
    while sum(alloc.values()) > total:                 # take the excess from the largest stratum
        s = max(strata, key=lambda s: (alloc[s], s))
        alloc[s] -= 1
    while sum(alloc.values()) < total:                 # fill from strata with spare items, largest first
        cand = [s for s in strata if alloc[s] < avail[s]]
        s = max(cand, key=lambda s: (avail[s], s))
        alloc[s] += 1
    return alloc


def sample_text(smp: pd.DataFrame) -> list:
    recs = load_records()
    variants = {v["variant_id"]: v for v in load_jsonl(VARIANTS)}
    out = []
    for _, r in smp.iterrows():
        src = recs[r["cluster"]]
        v = variants.get(r["item_id"])
        out.append({"sample_id": int(r["sample_id"]), "item_id": r["item_id"], "condition": r["condition"],
                    "subject": src["subject"], "body": v["body"] if v else src["body"], "original_body": src["body"]})
    return out


# ---------------------------------------------------------------- (d) frontier

def frontier(deltas: pd.DataFrame) -> pd.DataFrame:
    rr = json.loads(read_text(RUN_REPORT))["cells"]
    br = json.loads(read_text(BASE_REPORT))["baselines"]
    prim = deltas[(deltas["analysis"] == "primary") & deltas["condition"].isin(["para_high", "obf_high"])]
    rows = []
    for m in MODELS:
        for s in STRATEGIES:
            c = rr[f"{m}/{s}/eval"]
            rows.append({"detector": m, "kind": "llm", "strategy": s, "latency_median_s": c["latency_median_s"],
                         "latency_mean_s": c["latency_mean_s"], "backend": c["backend"], "gpu": c["gpu"], "tier": c["tier"]})
    for b in BASELINES:
        c = br[b.replace("baseline_", "")]["cells"]["eval"]
        rows.append({"detector": b, "kind": "baseline", "strategy": "supervised", "latency_median_s": c["latency_median_s"],
                     "latency_mean_s": c["latency_mean_s"], "backend": c["backend"], "gpu": c.get("gpu") or "", "tier": c["tier"]})
    fr = pd.DataFrame(rows)
    for cond in ("para_high", "obf_high"):
        d = prim[prim["condition"] == cond].set_index(["detector", "strategy"])
        key = list(zip(fr["detector"], fr["strategy"]))
        for col in ("delta", "ci_lo", "ci_hi"):
            fr[f"delta_sens_{cond}" if col == "delta" else f"{col}_{cond}"] = [d.at[k, col] for k in key]
    return fr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    seed = load_config("data.yaml")["seed"]
    items, pairs, ens, deltas, score_rep = load_scored()
    integrity = json.loads(read_text(INTEGRITY))
    lex = load_lexicon(LEXICON)
    lex_sha = lexicon_sha256(LEXICON)
    frozen = json.loads(read_text(ROOT / "reports" / "cue_lexicon_dev_report.json"))["lexicon_sha256"]
    if lex_sha != frozen:
        raise SystemExit("configs/cue_lexicon.yaml differs from the frozen lexicon")
    raw, raw_hashes = cot_raw(integrity)
    out = {}
    out["ensemble_votes"] = vote_summary(ens.rename(columns={}))
    out["cues_frequency"], out["cues_change"], out["cues_pairs"] = cue_tables(items, pairs, raw, lex)
    hc, summary, smp, avail, alloc = hardcore(items, seed)
    out["hardcore_items"], out["hardcore_summary"] = hc, summary
    out["frontier"] = frontier(deltas)
    runtime = time.time() - t0

    def write_all(d: Path) -> dict:
        h = {name: write_csv(out[name[:-4]], d / name) for name in OUTPUTS}
        h["hardcore_sample.csv"] = write_csv(smp, d / "hardcore_sample.csv")
        return h

    if a.check:
        with tempfile.TemporaryDirectory() as td:
            fresh = write_all(Path(td))
        cmp = compare_outputs({k: v for k, v in fresh.items() if k != "hardcore_sample.csv"}, SCORES)
        cmp["hardcore_sample.csv"] = "identical" if sha256_file(SAMPLE) == fresh["hardcore_sample.csv"] else "differs"
        ok = all(v == "identical" for v in cmp.values())
        print(f"re-run {'IDENTICAL' if ok else 'DIFFERS'}: {cmp}")
        return 0 if ok else 1
    hashes = {name: write_csv(out[name[:-4]], SCORES / name) for name in OUTPUTS}
    hashes["reports/hardcore_sample.csv"] = write_csv(smp, SAMPLE)
    with open_utf8(SAMPLE_TEXT, "w") as fh:
        for r in sample_text(smp):
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    cp = out["cues_pairs"]
    report = {"computed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "inputs": {"scoring_report_outputs": score_rep["outputs"], "cot_eval_files": raw_hashes,
                         "lexicon_sha256": lex_sha, "items_parquet": sha256_file(SCORES / "items.parquet")},
              "seed": seed,
              "cues": {"n_cot_rows": len(raw), "n_empty_rationale_by_model": {
                           m: int(out["cues_frequency"][(out["cues_frequency"]["model"] == m) & (out["cues_frequency"]["category"] == CATEGORIES[0])]["n_empty"].sum()) for m in MODELS},
                       "pairs_used": int(cp["n_pairs_used"].sum()), "pairs_excluded_empty_rationale": int(cp["n_pairs_excluded_empty_rationale"].sum())},
              "hardcore": {"n_items": len(hc), "by_hard_group": hc["hard_group"].value_counts().to_dict(),
                           "all_six_by_group": hc[hc["hard_group"] == "all_six"]["group"].value_counts().to_dict(),
                           "sample_available_by_condition": avail, "sample_allocation": alloc, "sample_n": len(smp),
                           "sample_text_file": SAMPLE_TEXT.relative_to(ROOT).as_posix() + " (git-ignored data)"},
              "frontier_rows": len(out["frontier"]), "outputs": hashes, "runtime_s": round(runtime, 1),
              "versions": {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__},
              "git_commit": git("rev-parse", "--short", "HEAD"), "git_describe": git("describe", "--tags", "--always")}
    write_json(REPORT, report)
    print(json.dumps({k: report[k] for k in ("cues", "hardcore")}, indent=1))
    print(f"runtime {runtime:.0f} s; outputs {', '.join(hashes)}; {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
