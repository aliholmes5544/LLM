"""
items.py — item lists for the detection stage (TASK_06 section 0; Section 3.6).

An item is {"item_id", "partition", "condition", "label_true", "subject", "body"}. Originals use the record
id and condition "original"; variants use the variant_id and their condition. Detectors see subject and body
only. The development items here serve the smoke test and prompt development; the evaluation item set is
built by 06_run_detection.py from the same helpers once the prompts are frozen.
"""
import json
from collections import defaultdict

from common import ROOT, open_utf8
from variants.rng import derive_rng

PROC = ROOT / "data" / "processed"


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
