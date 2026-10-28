"""
items.py — item lists for the detection stage (TASK_06 section 0; Section 3.6).

An item is {"item_id", "partition", "condition", "label_true", "subject", "body"}. Originals use the record
id and condition "original"; variants use the variant_id, the partition of their source record and their
condition. Detectors see subject and body only. The evaluation item set per (model, strategy) is built by
eval_items() from configs/detection.yaml (items.originals, items.variants with items.variant_sources,
items.generalization); counts are read from the data, never hard-coded. dev_items() builds the development
set (dev originals + accepted dev variants) for smoke tests and prompt development.
"""
import json
from collections import defaultdict
from pathlib import Path

from common import ROOT, open_utf8
from variants.rng import derive_rng

PROC = ROOT / "data" / "processed"
ACCEPTED = ("pass", "regenerated")      # step 05 statuses that make a variant an evaluation item


def load_records() -> dict:
    recs = {}
    for line in open_utf8(PROC / "records.jsonl"):
        r = json.loads(line)
        recs[r["id"]] = r
    return recs


def load_partitions() -> dict:
    return json.loads(open_utf8(PROC / "partitions.json").read())


def original_item(rec: dict, partition: str) -> dict:
    return {"item_id": rec["id"], "partition": partition, "condition": "original", "label_true": rec["class"],
            "subject": rec["subject"], "body": rec["body"]}


def variant_items(path: Path, recs: dict, part: dict, source_partitions: list) -> list:
    """Accepted variants of `path` whose source record lies in one of `source_partitions` (all must)."""
    where = {i: p for p in source_partitions for i in part[p]}
    items = []
    for line in open_utf8(path):
        v = json.loads(line)
        if v["status"] not in ACCEPTED:
            continue
        src = where.get(v["source_id"])
        if src is None:
            raise ValueError(f"{path.name}: source {v['source_id']} is not in {source_partitions}")
        items.append({"item_id": v["variant_id"], "partition": src, "condition": v["condition"],
                      "label_true": recs[v["source_id"]]["class"], "subject": v["subject"], "body": v["body"]})
    return items


def _check_unique(items: list) -> list:
    ids = [i["item_id"] for i in items]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate item ids in the item set")
    return items


def eval_items(recs: dict, part: dict, dcfg: dict) -> list:
    """Originals (items.originals), accepted variants (items.variants) and the generalization partitions."""
    it = dcfg["items"]
    items = [original_item(recs[i], p) for p in it["originals"] for i in part[p]]
    items += variant_items(ROOT / it["variants"], recs, part, it["variant_sources"])
    items += [original_item(recs[i], p) for p in it["generalization"] for i in part[p]]
    return _check_unique(items)


def dev_items(recs: dict, part: dict, dcfg: dict) -> list:
    """Development set: dev originals and the accepted dev variants (never an evaluation partition)."""
    it = dcfg["items"]
    items = [original_item(recs[i], "dev") for i in part["dev"]]
    items += variant_items(ROOT / it["dev_variants"], recs, part, it["dev_variant_sources"])
    return _check_unique(items)


def count_items(items: list) -> dict:
    """{partition: {condition: n}} for reports."""
    out = defaultdict(lambda: defaultdict(int))
    for i in items:
        out[i["partition"]][i["condition"]] += 1
    return {p: dict(c) for p, c in out.items()}


def smoke_items(recs: dict, part: dict, dcfg: dict, seed: int) -> list:
    """Seeded stratified sample of dev: per_class items per class, spread evenly over the class's subclasses."""
    sm = dcfg["smoke"]
    by_sub = defaultdict(list)
    for i in part[sm["partition"]]:
        by_sub[recs[i]["subclass"]].append(i)
    by_class = defaultdict(list)
    for sub in sorted(by_sub):
        by_class[recs[by_sub[sub][0]]["class"]].append(sub)
    items = []
    for cls in ("phish", "legit"):
        subs = by_class[cls]
        k, extra = divmod(sm["per_class"], len(subs))
        for n, sub in enumerate(subs):
            rng = derive_rng(seed, "smoke", sub)
            for i in rng.sample(sorted(by_sub[sub]), k + (1 if n < extra else 0)):
                items.append(original_item(recs[i], sm["partition"]))
    assert len(items) == sm["n_items"], f"smoke sample has {len(items)} items, expected {sm['n_items']}"
    return items
