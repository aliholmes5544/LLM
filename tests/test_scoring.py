"""
Unit tests for step 07 scoring (scripts/scoring/stats.py, ensemble.py, score.py; TASK_07 section 7): metric
functions on toy data with hand-computed answers, exact McNemar and Holm against known values, bootstrap
determinism per table name, the ensemble voting rules, the a priori power figure, and (when the scored
tables exist) that a re-run of scripts/07_score.py reproduces every CSV byte for byte; the hard-core sample
allocation rule and (when present) the structure of reports/hardcore_sample.csv (item 17).
Run from the repo root with `python -m unittest discover tests`.
"""
import math
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scoring.ensemble import ensemble_rows  # noqa: E402
import importlib  # noqa: E402
secondary = importlib.import_module("07_secondary")  # noqa: E402
from scoring.score import prepare, cell_metrics, cell_deltas, family_of  # noqa: E402
from scoring.stats import (bootstrap_p, holm, mcnemar_exact, mcnemar_power, point_and_ci, stat_bal_acc,  # noqa: E402
                           stat_contrast, stat_delta, stat_f1, stat_rate, table_rng)

ROOT = Path(__file__).resolve().parents[1]
MODELS = ["m1", "m2", "m3", "m4", "m5", "m6"]


def toy_items():
    """Two phishing originals (p1, p2) with para_high variants, two legitimate originals (n1 with a control
    variant, n2), one gen item each; one llm detector 'm1' under zero_shot."""
    rows = []
    meta = {
        "p1": ("core_pos", "original", "phish_original", "core", "phish"),
        "p2": ("core_pos", "original", "phish_original", "core", "phish"),
        "p1#para_high": ("core_pos", "para_high", "phish_variant", "core", "phish"),
        "p2#para_high": ("core_pos", "para_high", "phish_variant", "core", "phish"),
        "n1": ("core_neg", "original", "legit_core_neg", "core", "legit"),
        "n2": ("core_neg", "original", "legit_core_neg", "core", "legit"),
        "n1#para_high": ("ctrl_para_legit", "para_high", "legit_ctrl_para", "core", "legit"),
        "m1": ("ctrl_modern_legit", "original", "legit_ctrl_modern", "core", "legit"),
        "g1": ("gen_phish", "original", "gen_phish", "generalisation", "phish"),
        "g2": ("gen_legit", "original", "gen_legit", "generalisation", "legit"),
    }
    preds = {"p1": "phish", "p2": "invalid", "p1#para_high": "legit", "p2#para_high": "phish", "n1": "legit", "n2": "phish",
             "n1#para_high": "legit", "m1": "legit", "g1": "phish", "g2": "legit"}
    for iid, (part, cond, cls, pset, truth) in meta.items():
        rows.append({"detector": "m1", "kind": "llm", "strategy": "zero_shot", "item_id": iid, "cluster": iid.split("#")[0],
                     "partition": part, "condition": cond, "item_class": cls, "partition_set": pset, "label_true": truth,
                     "label_pred": preds[iid], "invalid": preds[iid] == "invalid", "score": np.nan, "source": "x",
                     "subclass": "y", "body_words": 10, "latency_s": 0.1, "n_prompt_tokens": 5, "truncated_input": False,
                     "backend": "cuda"})
    pairs = pd.DataFrame([{"cluster": "p1", "condition": "para_high", "variant_id": "p1#para_high", "item_class": "phish_variant"},
                          {"cluster": "p2", "condition": "para_high", "variant_id": "p2#para_high", "item_class": "phish_variant"},
                          {"cluster": "n1", "condition": "para_high", "variant_id": "n1#para_high", "item_class": "legit_ctrl_para"}])
    return pd.DataFrame(rows), pairs


class TestStats(unittest.TestCase):
    def test_stat_functions(self):
        self.assertAlmostEqual(float(stat_rate(np.array([3, 4]))), 0.75)
        self.assertAlmostEqual(float(stat_delta(np.array([8, 6, 10]))), 0.2)
        self.assertAlmostEqual(float(stat_bal_acc(np.array([9, 10, 3, 4]))), 0.5 * (0.9 + 0.75))
        self.assertAlmostEqual(float(stat_f1(np.array([6, 2, 2]))), 12 / 16)
        self.assertAlmostEqual(float(stat_contrast(np.array([8, 6, 9, 8, 10]))), (9 - 8) / 10 - (8 - 6) / 10)
        self.assertTrue(math.isnan(float(stat_rate(np.array([0, 0])))))

    def test_mcnemar_exact(self):
        self.assertEqual(mcnemar_exact(0, 0), 1.0)
        self.assertAlmostEqual(mcnemar_exact(5, 0), 2 / 32)          # 0.0625
        self.assertAlmostEqual(mcnemar_exact(0, 5), 2 / 32)
        self.assertAlmostEqual(mcnemar_exact(10, 2), 2 * (1 + 12 + 66) / 4096)
        self.assertEqual(mcnemar_exact(3, 3), 1.0)

    def test_holm(self):
        adj = holm([0.01, 0.04, 0.03, 0.20])
        self.assertAlmostEqual(adj[0], 0.04)   # 4 x 0.01
        self.assertAlmostEqual(adj[2], 0.09)   # 3 x 0.03
        self.assertAlmostEqual(adj[1], 0.09)   # 2 x 0.04 = 0.08 < 0.09 -> monotone
        self.assertAlmostEqual(adj[3], 0.20)
        self.assertTrue(math.isnan(holm([0.5, float("nan")])[1]))
        self.assertAlmostEqual(holm([0.5, float("nan")])[0], 0.5)

    def test_bootstrap_is_deterministic_per_table(self):
        counts = np.column_stack([np.arange(40) % 3 == 0, np.ones(40, dtype=int)]).astype(int)
        a = point_and_ci(counts, stat_rate, 2026, "t/a", B=300)
        b = point_and_ci(counts, stat_rate, 2026, "t/a", B=300)
        c = point_and_ci(counts, stat_rate, 2026, "t/b", B=300)
        self.assertEqual((a["ci_lo"], a["ci_hi"]), (b["ci_lo"], b["ci_hi"]))
        self.assertNotEqual(a["boot"].tolist(), c["boot"].tolist())
        self.assertAlmostEqual(a["value"], 14 / 40)
        self.assertLessEqual(a["ci_lo"], a["value"])
        self.assertGreaterEqual(a["ci_hi"], a["value"])
        self.assertEqual(table_rng(2026, "x").integers(0, 1000), table_rng(2026, "x").integers(0, 1000))

    def test_bootstrap_p(self):
        self.assertAlmostEqual(bootstrap_p(np.array([1.0, 2.0, 3.0, 4.0]), B=4), 0.25)   # floored at 1/B
        self.assertAlmostEqual(bootstrap_p(np.array([-1.0, 1.0, -2.0, 2.0]), B=4), 1.0)
        self.assertAlmostEqual(bootstrap_p(np.array([-1.0, 1.0, 1.0, 1.0]), B=4), 0.5)

    def test_power_note(self):
        p = mcnemar_power(334, 0.10, 0.05)
        self.assertGreater(p, 0.5)
        self.assertLess(p, 1.0)
        self.assertGreater(mcnemar_power(334, 0.10, 0.08), p)   # a larger drop is easier to detect


class TestScoring(unittest.TestCase):
    def test_toy_metrics_and_deltas(self):
        items, pairs = toy_items()
        items["group"] = [f"phish_{c}" if k == "phish_variant" else k for k, c in zip(items["item_class"], items["condition"])]
        items["correct"] = (items["label_pred"] == items["label_true"]) & ~items["invalid"]
        d = items.set_index("item_id", drop=False)
        cell = ("m1", "llm", "zero_shot")
        m = pd.DataFrame(cell_metrics(cell, d, "primary", 2026, 50)).set_index(["metric", "condition"])
        self.assertAlmostEqual(m.loc[("sens", "original"), "value"], 0.5)          # p1 right, p2 invalid
        self.assertAlmostEqual(m.loc[("sens", "para_high"), "value"], 0.5)
        self.assertAlmostEqual(m.loc[("spec", "original_core_neg"), "value"], 0.5)
        self.assertAlmostEqual(m.loc[("spec", "para_high_ctrl"), "value"], 1.0)
        self.assertAlmostEqual(m.loc[("acc", "core_originals"), "value"], 3 / 5)    # p1, n1, m1 of 5 core originals
        self.assertAlmostEqual(m.loc[("bal_acc", "core_originals"), "value"], 0.5 * (0.5 + 2 / 3))
        self.assertAlmostEqual(m.loc[("f1_phish", "core_originals"), "value"], 2 * 1 / (2 * 1 + 1 + 1))  # tp 1, fp n2, fn p2
        self.assertAlmostEqual(m.loc[("invalid_rate", "all"), "value"], 0.1)
        self.assertAlmostEqual(m.loc[("gen_sens", "gen_phish"), "value"], 1.0)
        mn = pd.DataFrame(cell_metrics(cell, d, "no_invalid", 2026, 50)).set_index(["metric", "condition"])
        self.assertAlmostEqual(mn.loc[("sens", "original"), "value"], 1.0)         # p2 dropped
        self.assertNotIn(("invalid_rate", "all"), mn.index)
        dl = pd.DataFrame(cell_deltas(cell, d, pairs, "primary", 2026, 50)).set_index("condition")
        self.assertEqual(dl.loc["para_high", "n_pairs"], 2)
        self.assertAlmostEqual(dl.loc["para_high", "delta"], 0.0)                 # p1 lost, p2 gained
        self.assertEqual((dl.loc["para_high", "b_orig_only"], dl.loc["para_high", "c_var_only"]), (1, 1))
        self.assertAlmostEqual(dl.loc["para_high", "mcnemar_p"], 1.0)
        self.assertAlmostEqual(dl.loc["para_high_ctrl", "delta"], 0.0)
        self.assertEqual(dl.loc["para_high", "family"], "F-RQ4")
        dn = pd.DataFrame(cell_deltas(cell, d, pairs, "no_invalid", 2026, 50)).set_index("condition")
        self.assertEqual(dn.loc["para_high", "n_pairs"], 1)                        # the p2 pair is dropped
        self.assertAlmostEqual(dn.loc["para_high", "delta"], 1.0)

    def test_families(self):
        self.assertEqual(family_of("llm", "zero_shot"), "F-RQ4")
        self.assertEqual(family_of("llm", "cot"), "S-cot")
        self.assertEqual(family_of("ensemble", "role"), "S-ensemble")
        self.assertEqual(family_of("baseline", "supervised"), "S-baselines")

    def test_ensemble_rules(self):
        items, _ = toy_items()
        base = items[items["item_id"].isin(["p1", "p2", "n1"])]
        votes = {"p1": ["phish", "phish", "phish", "phish", "legit", "legit"],    # 4-2 -> phish
                 "p2": ["phish", "phish", "phish", "legit", "legit", "legit"],    # 3-3 -> invalid
                 "n1": ["legit", "legit", "legit", "invalid", "invalid", "invalid"]}  # 3 valid -> invalid
        rows = []
        for i, mdl in enumerate(MODELS):
            d = base.copy()
            d["detector"] = mdl
            d["label_pred"] = [votes[iid][i] for iid in d["item_id"]]
            d["invalid"] = d["label_pred"] == "invalid"
            rows.append(d)
        ens = ensemble_rows(pd.concat(rows), MODELS).set_index("item_id")
        self.assertEqual(ens.loc["p1", "label_pred"], "phish")
        self.assertEqual(ens.loc["p2", "label_pred"], "invalid")
        self.assertEqual(ens.loc["n1", "label_pred"], "invalid")
        self.assertEqual(int(ens.loc["n1", "n_valid_votes"]), 3)
        self.assertTrue((ens["kind"] == "ensemble").all())

    @unittest.skipUnless((ROOT / "results/scores/metrics_long.csv").exists() and (ROOT / "results/scores/items.parquet").exists(),
                         "scored tables not present")
    def test_rerun_reproduces_csvs(self):
        r = subprocess.run([sys.executable, "scripts/07_score.py", "--check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-500:] + r.stderr[-500:])
        self.assertIn("IDENTICAL", r.stdout)


class TestHardcoreSample(unittest.TestCase):
    def test_allocate_rule(self):
        # fewer available than requested: take all
        self.assertEqual(secondary.allocate({"a": 5, "b": 3, "c": 0, "d": 0}, 30, 5), {"a": 5, "b": 3, "c": 0, "d": 0})
        # the post hoc population of item 17: proportional with largest remainder, minimum 5 where available
        alloc = secondary.allocate({"original": 119, "para_low": 65, "para_high": 44, "obf_low": 3, "obf_high": 0}, 30, 5)
        self.assertEqual(alloc, {"original": 16, "para_low": 8, "para_high": 6, "obf_low": 0, "obf_high": 0})
        self.assertEqual(sum(alloc.values()), 30)
        # a stratum with at least 5 available is lifted to 5
        alloc = secondary.allocate({"a": 100, "b": 5}, 30, 5)
        self.assertEqual(alloc, {"a": 25, "b": 5})

    def test_sample_file_structure(self):
        path = ROOT / "reports" / "hardcore_sample.csv"
        if not path.exists():
            self.skipTest("sample not computed")
        s = pd.read_csv(path, dtype={"failure_type": str, "note": str}, keep_default_na=False)
        self.assertEqual(list(s.columns[:3]), ["sample_id", "set", "item_id"])
        self.assertEqual(list(s["sample_id"]), list(range(1, len(s) + 1)))
        self.assertFalse(s["item_id"].duplicated().any())
        pre, post = s[s["set"] == "preregistered"], s[s["set"] == "posthoc"]
        self.assertEqual(len(pre) + len(post), len(s))
        self.assertTrue((pre["n_models_wrong"] == 6).all())
        self.assertTrue(pre["item_class"].eq("phish_variant").all())
        self.assertEqual(len(post), 30)
        self.assertTrue((post["n_models_wrong"] >= 4).all())
        self.assertTrue(post["item_class"].isin(["phish_original", "phish_variant"]).all())
        self.assertTrue((s["label_true"] == "phish").all())


if __name__ == "__main__":
    unittest.main()
