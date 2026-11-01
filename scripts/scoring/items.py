"""
items.py — the scoring item table (TASK_07 sections 0, 1 and 7: scripts/07_build_items.py; Chapter 4
Section 4.2.2). Joins every raw prediction row of the 24 detector cells and the 3 baseline cells with the
partition, condition, item class, cluster (source e-mail id) and text length of its item, after asserting
that each input file has the sha256 and row count recorded by scripts/06_check_integrity.py.

Nothing here compares a prediction with the truth: the table carries label_true and label_pred side by side
and leaves every comparison, count and rate to scripts/07_score.py (TASK_07 section 8: step 1 computes no
metric). The only numbers reported are structural: files, rows, items per class, pairs per condition.
"""
import hashlib
import json
from collections import Counter

import pandas as pd

ACCEPTED = ("pass", "regenerated")
CORE_ORIGINALS = {"core_pos": "phish_original", "core_neg": "legit_core_neg", "ctrl_modern_legit": "legit_ctrl_modern"}
GENERALISATION = {"gen_phish": "gen_phish", "gen_legit": "gen_legit"}
VARIANT_CLASS = {"core_pos": "phish_variant", "ctrl_para_legit": "legit_ctrl_para"}
COLUMNS = ["detector", "kind", "strategy", "item_id", "cluster", "partition", "condition", "item_class",
           "partition_set", "label_true", "label_pred", "invalid", "score", "source", "subclass", "body_words",
           "latency_s", "n_prompt_tokens", "truncated_input", "backend"]
ROW_FIELDS = ("item_id", "partition", "condition", "label_true", "label_pred", "invalid", "latency_s",
              "n_prompt_tokens", "truncated_input", "backend")


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path) -> list:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def expected_files(integrity: dict) -> list:
    """The 27 input files with their frozen sha256 and row counts, from reports/integrity_check.json."""
    files = []
    for key, c in integrity["cells"].items():
        files.append({"file": c["file"], "sha256": c["file_sha256"], "n_rows": c["n_rows"], "detector": c["model"],
                      "kind": "llm", "strategy": c["strategy"]})
    for key, c in integrity["baselines"]["cells"].items():
        files.append({"file": c["file"], "sha256": c["file_sha256"], "n_rows": c["n_rows"], "detector": c["model"],
                      "kind": "baseline", "strategy": "supervised"})
    return files


def verify_file(root, spec: dict) -> None:
    path = root / spec["file"]
    if not path.exists():
        raise SystemExit(f"missing input {spec['file']}")
    sha = sha256_file(path)
    if sha != spec["sha256"]:
        raise SystemExit(f"{spec['file']}: sha256 {sha[:16]} differs from the integrity report {spec['sha256'][:16]}")


def item_meta(recs: dict, part: dict, variants: list) -> dict:
    """item_id -> cluster, partition, condition, item_class, partition_set, label, source, subclass, body_words."""
    meta = {}
    for p, cls in {**CORE_ORIGINALS, **GENERALISATION}.items():
        for i in part[p]:
            r = recs[i]
            meta[i] = {"cluster": i, "partition": p, "condition": "original", "item_class": cls,
                       "partition_set": "generalisation" if p in GENERALISATION else "core",
                       "label_true": r["class"], "source": r["source"], "subclass": r["subclass"],
                       "body_words": len(r["body"].split())}
    where = {i: p for p in VARIANT_CLASS for i in part[p]}
    for v in variants:
        if v["status"] not in ACCEPTED:
            continue
        p = where.get(v["source_id"])
        if p is None:
            raise SystemExit(f"variant {v['variant_id']}: source not in {list(VARIANT_CLASS)}")
        r = recs[v["source_id"]]
        meta[v["variant_id"]] = {"cluster": v["source_id"], "partition": p, "condition": v["condition"],
                                 "item_class": VARIANT_CLASS[p], "partition_set": "core", "label_true": r["class"],
                                 "source": r["source"], "subclass": r["subclass"],
                                 "body_words": len(v["body"].split())}
    return meta


def pairs_table(meta: dict) -> pd.DataFrame:
    """One row per accepted variant: cluster (original item id), condition, variant item id, item class."""
    rows = [{"cluster": m["cluster"], "condition": m["condition"], "variant_id": i, "item_class": m["item_class"]}
            for i, m in meta.items() if m["condition"] != "original"]
    return pd.DataFrame(rows, columns=["cluster", "condition", "variant_id", "item_class"]) \
        .sort_values(["item_class", "condition", "cluster"]).reset_index(drop=True)


def file_rows(root, spec: dict, meta: dict) -> list:
    """Rows of one results file joined with the item metadata; metadata disagreements are refused."""
    rows = load_jsonl(root / spec["file"])
    if len(rows) != spec["n_rows"]:
        raise SystemExit(f"{spec['file']}: {len(rows)} rows, integrity report says {spec['n_rows']}")
    out, seen = [], set()
    for r in rows:
        if any(k not in r for k in ROW_FIELDS):
            raise SystemExit(f"{spec['file']}: row without the runner fields: {r.get('item_id')}")
        m = meta.get(r["item_id"])
        if m is None:
            raise SystemExit(f"{spec['file']}: item {r['item_id']} is not an evaluation item")
        if (r["partition"], r["condition"], r["label_true"]) != (m["partition"], m["condition"], m["label_true"]):
            raise SystemExit(f"{spec['file']}: metadata of {r['item_id']} disagrees with partitions/variants")
        if r["item_id"] in seen:
            raise SystemExit(f"{spec['file']}: duplicate item {r['item_id']}")
        seen.add(r["item_id"])
        out.append({"detector": spec["detector"], "kind": spec["kind"], "strategy": spec["strategy"],
                    "item_id": r["item_id"], "cluster": m["cluster"], "partition": m["partition"],
                    "condition": m["condition"], "item_class": m["item_class"], "partition_set": m["partition_set"],
                    "label_true": r["label_true"], "label_pred": r["label_pred"], "invalid": bool(r["invalid"]),
                    "score": r.get("score"), "source": m["source"], "subclass": m["subclass"],
                    "body_words": m["body_words"], "latency_s": r["latency_s"], "n_prompt_tokens": r["n_prompt_tokens"],
                    "truncated_input": bool(r["truncated_input"]), "backend": r["backend"]})
    return out


def build(root, integrity: dict, recs: dict, part: dict, variants: list) -> tuple:
    """(items DataFrame, pairs DataFrame, structural report). Every input file is hash-verified first."""
    files = expected_files(integrity)
    for spec in files:
        verify_file(root, spec)
    meta = item_meta(recs, part, variants)
    expected_items = set(meta)
    rows = []
    for spec in files:
        fr = file_rows(root, spec, meta)
        if {r["item_id"] for r in fr} != expected_items:
            raise SystemExit(f"{spec['file']}: item set differs from the expected evaluation item set")
        rows.extend(fr)
    items = pd.DataFrame(rows, columns=COLUMNS).sort_values(["kind", "detector", "strategy", "item_id"]).reset_index(drop=True)
    items["score"] = items["score"].astype("float64")
    pairs = pairs_table(meta)
    classes = Counter(m["item_class"] for m in meta.values())
    report = {"n_files": len(files), "n_rows": len(items), "n_items_per_cell": len(expected_items),
              "detectors": sorted({(f["detector"], f["kind"]) for f in files}),
              "cells": [f"{f['detector']}/{f['strategy']}" for f in files],
              "files": [{"file": f["file"], "sha256": f["sha256"], "n_rows": f["n_rows"]} for f in files],
              "items_by_class": dict(sorted(classes.items())),
              "items_by_partition_condition": {p: dict(Counter(m["condition"] for m in meta.values() if m["partition"] == p))
                                               for p in sorted({m["partition"] for m in meta.values()})},
              "n_clusters": len({m["cluster"] for m in meta.values()}),
              "pairs_by_condition": {f"{c}/{cond}": int(n) for (c, cond), n in
                                     pairs.groupby(["item_class", "condition"]).size().items()},
              "columns": COLUMNS}
    return items, pairs, report


def write_outputs(items: pd.DataFrame, pairs: pd.DataFrame, out_dir) -> dict:
    """items.parquet (pyarrow, snappy) and pairs.csv; returns their sha256 so a rebuild can be compared."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ip, pp = out_dir / "items.parquet", out_dir / "pairs.csv"
    items.to_parquet(ip, engine="pyarrow", index=False, compression="snappy")
    pairs.to_csv(pp, index=False, lineterminator="\n")
    return {"items.parquet": sha256_file(ip), "pairs.csv": sha256_file(pp)}
