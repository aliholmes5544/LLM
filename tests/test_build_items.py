"""
Unit tests for scripts/scoring/items.py (TASK_07 step 1): item classes and clusters, pairing table, hash and
row-count assertions, metadata disagreement, and byte-identical rebuilds. Toy inputs in a temporary directory;
no project data. Run from the repo root with `python -m unittest discover tests`.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scoring.items import build, write_outputs, sha256_file, item_meta, pairs_table  # noqa: E402

RECS = {
    "p1": {"id": "p1", "class": "phish", "source": "nahmias", "subclass": "spear_llm", "body": "one two three"},
    "p2": {"id": "p2", "class": "phish", "source": "nahmias", "subclass": "spear_llm", "body": "a b c d"},
    "n1": {"id": "n1", "class": "legit", "source": "nahmias", "subclass": "enron_ham", "body": "lunch at noon"},
    "n2": {"id": "n2", "class": "legit", "source": "nahmias", "subclass": "hard_ham", "body": "x y"},
    "m1": {"id": "m1", "class": "legit", "source": "ephishllm", "subclass": "ephish_legit", "body": "hi"},
    "g1": {"id": "g1", "class": "phish", "source": "ephishllm", "subclass": "ephish_phish", "body": "z"},
    "g2": {"id": "g2", "class": "legit", "source": "ephishllm", "subclass": "ephish_legit", "body": "w"},
}
PART = {"core_pos": ["p1", "p2"], "core_neg": ["n1", "n2"], "ctrl_para_legit": ["n1"], "ctrl_modern_legit": ["m1"],
        "gen_phish": ["g1"], "gen_legit": ["g2"]}
VARIANTS = [
    {"variant_id": "p1#para_low", "source_id": "p1", "condition": "para_low", "body": "one two three four", "status": "pass"},
    {"variant_id": "p1#obf_high", "source_id": "p1", "condition": "obf_high", "body": "0ne two three", "status": "regenerated"},
    {"variant_id": "p2#para_low", "source_id": "p2", "condition": "para_low", "body": "a b", "status": "excluded"},
    {"variant_id": "n1#para_high", "source_id": "n1", "condition": "para_high", "body": "lunch at twelve", "status": "pass"},
]
ITEMS = ["p1", "p2", "n1", "n2", "m1", "g1", "g2", "p1#para_low", "p1#obf_high", "n1#para_high"]


def row(meta, item_id, pred, detector, strategy, score=None):
    m = meta[item_id]
    r = {"item_id": item_id, "partition": m["partition"], "condition": m["condition"], "label_true": m["label_true"],
         "model": detector, "strategy": strategy, "raw_output": pred, "label_pred": pred, "invalid": pred == "invalid",
         "latency_s": 0.1, "n_prompt_tokens": 5, "truncated_input": False, "backend": "cuda"}
    if score is not None:
        r["score"] = score
    return r


class Fixture:
    def __init__(self, root: Path):
        self.root = root
        self.meta = item_meta(RECS, PART, VARIANTS)
        self.integrity = {"all_pass": True, "checked_at": "t", "cells": {}, "baselines": {"cells": {}}}

    def cell(self, detector, strategy, preds, kind="llm"):
        rel = f"results/raw/{detector}/{strategy}/eval.jsonl"
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            for i in ITEMS:
                f.write(json.dumps(row(self.meta, i, preds.get(i, "legit"), detector, strategy,
                                       0.5 if kind == "baseline" else None)) + "\n")
        entry = {"file": rel, "file_sha256": sha256_file(p), "n_rows": len(ITEMS), "model": detector, "strategy": strategy}
        if kind == "llm":
            self.integrity["cells"][f"{detector}/{strategy}"] = entry
        else:
            self.integrity["baselines"]["cells"][detector.replace("baseline_", "")] = entry
        return p


class ItemTable(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.fx = Fixture(Path(self.td.name))
        self.fx.cell("m-a", "zero_shot", {"p1": "phish", "p1#para_low": "invalid"})
        self.fx.cell("m-a", "cot", {"p1": "phish"})
        self.fx.cell("baseline_x", "supervised", {"g1": "phish"}, kind="baseline")

    def tearDown(self):
        self.td.cleanup()

    def test_classes_clusters_and_sets(self):
        items, pairs, rep = build(self.fx.root, self.fx.integrity, RECS, PART, VARIANTS)
        self.assertEqual(len(items), 3 * len(ITEMS))
        one = items[(items.detector == "m-a") & (items.strategy == "zero_shot")].set_index("item_id")
        self.assertEqual(one.loc["p1#para_low", "cluster"], "p1")
        self.assertEqual(one.loc["p1#para_low", "item_class"], "phish_variant")
        self.assertEqual(one.loc["n1#para_high", "item_class"], "legit_ctrl_para")
        self.assertEqual(one.loc["n1#para_high", "partition"], "ctrl_para_legit")
        self.assertEqual(one.loc["n1", "item_class"], "legit_core_neg")
        self.assertEqual(one.loc["m1", "item_class"], "legit_ctrl_modern")
        self.assertEqual(one.loc["g1", "partition_set"], "generalisation")
        self.assertEqual(one.loc["p1", "partition_set"], "core")
        self.assertTrue(bool(one.loc["p1#para_low", "invalid"]))
        self.assertEqual(one.loc["p1#para_low", "body_words"], 4)
        self.assertEqual(rep["items_by_class"], {"gen_legit": 1, "gen_phish": 1, "legit_core_neg": 2, "legit_ctrl_modern": 1,
                                                 "legit_ctrl_para": 1, "phish_original": 2, "phish_variant": 2})
        self.assertEqual(rep["n_clusters"], 7)
        self.assertEqual(rep["pairs_by_condition"], {"legit_ctrl_para/para_high": 1, "phish_variant/obf_high": 1,
                                                     "phish_variant/para_low": 1})
        # the excluded variant is not an item
        self.assertNotIn("p2#para_low", set(items.item_id))
        # baseline rows carry a score, detector rows do not
        self.assertTrue(items[items.kind == "baseline"]["score"].notna().all())
        self.assertTrue(items[items.kind == "llm"]["score"].isna().all())
        # no column compares prediction with truth
        self.assertNotIn("correct", items.columns)

    def test_pairs_table(self):
        pairs = pairs_table(item_meta(RECS, PART, VARIANTS))
        self.assertEqual(list(pairs.columns), ["cluster", "condition", "variant_id", "item_class"])
        self.assertEqual(len(pairs), 3)
        self.assertEqual(set(pairs.cluster), {"p1", "n1"})

    def test_rebuild_is_byte_identical(self):
        items, pairs, _ = build(self.fx.root, self.fx.integrity, RECS, PART, VARIANTS)
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            ha = write_outputs(items, pairs, Path(a))
            items2, pairs2, _ = build(self.fx.root, self.fx.integrity, RECS, PART, VARIANTS)
            hb = write_outputs(items2, pairs2, Path(b))
        self.assertEqual(ha, hb)

    def test_hash_mismatch_is_refused(self):
        self.fx.integrity["cells"]["m-a/cot"]["file_sha256"] = "0" * 64
        with self.assertRaises(SystemExit):
            build(self.fx.root, self.fx.integrity, RECS, PART, VARIANTS)

    def test_row_count_mismatch_is_refused(self):
        p = self.fx.cell("m-b", "zero_shot", {})
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(row(self.fx.meta, "p1", "phish", "m-b", "zero_shot")) + "\n")
        self.fx.integrity["cells"]["m-b/zero_shot"]["file_sha256"] = sha256_file(p)   # hash ok, count wrong
        with self.assertRaises(SystemExit):
            build(self.fx.root, self.fx.integrity, RECS, PART, VARIANTS)

    def test_metadata_disagreement_is_refused(self):
        p = self.fx.root / "results/raw/m-a/cot/eval.jsonl"
        with open(p, encoding="utf-8") as f:
            rows = [json.loads(l) for l in f]
        rows[0]["label_true"] = "legit" if rows[0]["label_true"] == "phish" else "phish"
        with open(p, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
        self.fx.integrity["cells"]["m-a/cot"]["file_sha256"] = sha256_file(p)
        with self.assertRaises(SystemExit):
            build(self.fx.root, self.fx.integrity, RECS, PART, VARIANTS)


if __name__ == "__main__":
    unittest.main()
