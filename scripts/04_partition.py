#!/usr/bin/env python3
"""
04_partition.py — build partitions and check for leakage (Section 3.2.4).

Partitions (ids only; one record belongs to exactly one evaluation role):
  core_pos          all spear_llm originals
  core_neg          all hard_ham + seeded sample of enron_ham  (total = config)
  ctrl_para_legit   seeded sample of core_neg (ids reused; transformation applied later)
  ctrl_modern_legit seeded sample of ephish_legit
  gen_phish/gen_legit  stratified seeded sample of E-PhishLLM (salutation preserved)
  dev               traditional + enron + ephish personalized phish + ephish legit
  train / valid     remaining traditional + enron, stratified validation split
  fewshot_pool      = train (traditional + enron only; never spear, never E-PhishLLM)

Leakage check: no item in any evaluation set (core, controls, generalization)
may have a near-duplicate (word-trigram Jaccard >= threshold) in train, valid,
dev or fewshot_pool. Offenders are removed from the NON-evaluation side and counted.

Usage:  python scripts/04_partition.py
Output: data/processed/partitions.json, reports/partition_report.json
"""
import json
import random
import sys
from collections import Counter, defaultdict

from datasketch import MinHash, MinHashLSH

from common import ROOT, load_config, open_utf8, write_json, trigrams

CFG = load_config()
PC, PP = CFG["partition"], CFG["preprocess"]
PROC = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"


def sample(rng: random.Random, pool: list, k: int, what: str) -> list:
    if len(pool) < k:
        raise SystemExit(f"not enough records for {what}: need {k}, have {len(pool)}")
    pool = sorted(pool)                      # deterministic regardless of input order
    return rng.sample(pool, k)


def main() -> int:
    recs = [json.loads(l) for l in open_utf8(PROC / "records.jsonl")]
    by_id = {r["id"]: r for r in recs}
    rng = random.Random(CFG["seed"])
    ids = defaultdict(list)
    for r in recs:
        ids[r["subclass"]].append(r["id"])
    sal = {r["id"]: r["salutation"] for r in recs}

    part, used = {}, set()

    def take(name, chosen):
        part[name] = sorted(chosen)
        used.update(chosen)

    # --- core test set -----------------------------------------------------
    take("core_pos", ids["spear_llm"])
    hard = ids["hard_ham"]
    need_enron = PC["core_negatives_total"] - len(hard)
    enron_test = sample(rng, [i for i in ids["enron_ham"] if i not in used], need_enron, "core_neg enron")
    take("core_neg", hard + enron_test)

    # --- controls ----------------------------------------------------------
    part["ctrl_para_legit"] = sorted(sample(rng, part["core_neg"], PC["control_paraphrased_legit"], "ctrl_para_legit"))
    modern = sample(rng, [i for i in ids["ephish_legit"] if i not in used], PC["control_modern_legit"], "ctrl_modern_legit")
    take("ctrl_modern_legit", modern)

    # --- generalization set (stratified by salutation for phishing) --------
    gp = PC["generalization"]["phish"]
    pool_ph = [i for i in ids["ephish_phish"] if i not in used]
    strata = defaultdict(list)
    for i in pool_ph:
        strata[sal[i]].append(i)
    gen_ph = []
    tot = len(pool_ph)
    alloc = {s: round(gp * len(v) / tot) for s, v in strata.items()}
    alloc[max(alloc, key=alloc.get)] += gp - sum(alloc.values())      # fix rounding
    for s, k in alloc.items():
        gen_ph += sample(rng, strata[s], k, f"gen_phish[{s}]")
    take("gen_phish", gen_ph)
    gen_lg = sample(rng, [i for i in ids["ephish_legit"] if i not in used], PC["generalization"]["legit"], "gen_legit")
    take("gen_legit", gen_lg)

    # --- development set ---------------------------------------------------
    d = PC["dev"]
    dev = []
    dev += sample(rng, [i for i in ids["traditional"] if i not in used], d["traditional"], "dev traditional")
    dev += sample(rng, [i for i in ids["enron_ham"] if i not in used], d["enron"], "dev enron")
    dev += sample(rng, [i for i in ids["ephish_phish"] if i not in used and sal[i] == "named"],
                  d["ephish_personalized_phish"], "dev ephish personalized phish")
    dev += sample(rng, [i for i in ids["ephish_legit"] if i not in used], d["ephish_legit"], "dev ephish legit")
    take("dev", dev)

    # --- training / validation (traditional + enron remaining) -------------
    train_pool = [i for i in ids["traditional"] + ids["enron_ham"] if i not in used]
    valid = []
    for sub in ("traditional", "enron_ham"):
        p = [i for i in train_pool if by_id[i]["subclass"] == sub]
        valid += sample(rng, p, round(len(p) * PC["validation_fraction"]), f"valid {sub}")
    vset = set(valid)
    take("valid", valid)
    take("train", [i for i in train_pool if i not in vset])
    part["fewshot_pool"] = part["train"]

    # --- leakage check: evaluation vs non-evaluation ------------------------
    eval_ids = set(part["core_pos"] + part["core_neg"] + part["ctrl_modern_legit"]
                   + part["gen_phish"] + part["gen_legit"])
    other_names = ["train", "valid", "dev"]
    thr, perm = PP["near_dup_jaccard"], PP["minhash_perm"]
    lsh = MinHashLSH(threshold=thr, num_perm=perm)
    grams = {}
    for i in eval_ids:
        g = trigrams(by_id[i]["body"])
        grams[i] = g
        m = MinHash(num_perm=perm)
        for t in g:
            m.update(t.encode())
        lsh.insert(i, m)
    leaked = Counter()
    removed = defaultdict(list)
    for name in other_names:
        keep = []
        for i in part[name]:
            g = trigrams(by_id[i]["body"])
            m = MinHash(num_perm=perm)
            for t in g:
                m.update(t.encode())
            hit = False
            for cand in lsh.query(m):
                c = grams[cand]
                if g and c and len(g & c) / len(g | c) >= thr:
                    hit = True
                    break
            if hit:
                leaked[name] += 1
                removed[name].append(i)
            else:
                keep.append(i)
        part[name] = keep
    part["fewshot_pool"] = part["train"]

    # --- consistency assertions -------------------------------------------
    roles = ["core_pos", "core_neg", "ctrl_modern_legit", "gen_phish", "gen_legit", "dev", "train", "valid"]
    seen = Counter(i for n in roles for i in part[n])
    assert max(seen.values()) == 1, "a record appears in two roles"
    assert set(part["ctrl_para_legit"]) <= set(part["core_neg"])

    counts = {n: len(v) for n, v in part.items()}
    counts["core_neg_by_subclass"] = dict(Counter(by_id[i]["subclass"] for i in part["core_neg"]))
    counts["gen_phish_by_salutation"] = dict(Counter(sal[i] for i in part["gen_phish"]))
    counts["train_by_subclass"] = dict(Counter(by_id[i]["subclass"] for i in part["train"]))
    report = {"seed": CFG["seed"], "counts": counts,
              "leakage_removed_from": dict(leaked), "leakage_removed_ids": dict(removed),
              "near_dup_jaccard": thr}
    write_json(PROC / "partitions.json", part, indent=1)
    write_json(REPORTS / "partition_report.json", report)

    for n in roles + ["ctrl_para_legit", "fewshot_pool"]:
        print(f"{n:18s} {len(part[n]):6d}")
    print(f"core_neg by subclass:      {counts['core_neg_by_subclass']}")
    print(f"gen_phish by salutation:   {counts['gen_phish_by_salutation']}")
    print(f"train by subclass:         {counts['train_by_subclass']}")
    print(f"leakage (near-dups of evaluation items removed from): {dict(leaked) or 'none'}")
    print(f"\npartitions -> {(PROC / 'partitions.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
