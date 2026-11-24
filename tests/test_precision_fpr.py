"""Unit tests for scripts/07_precision_fpr.py (QUESTIONS.md item 19): the precision statistic, the confusion counts,
precision and FPR rows on toy data, the NaN rule when nothing is labelled phishing, the (1 - spec) - FPR identity and
the agreement of the recomputed sensitivity, specificity and f1_phish with scoring.score on the same toy items."""
import importlib
import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
pf = importlib.import_module("07_precision_fpr")
from scoring.score import annotate, cell_metrics  # noqa: E402

META = {
    "p1": ("core_pos", "original", "phish_original", "core", "phish"),
    "p2": ("core_pos", "original", "phish_original", "core", "phish"),
    "p3": ("core_pos", "original", "phish_original", "core", "phish"),
    "p1#para_high": ("core_pos", "para_high", "phish_variant", "core", "phish"),
    "n1": ("core_neg", "original", "legit_core_neg", "core", "legit"),
    "n2": ("core_neg", "original", "legit_core_neg", "core", "legit"),
    "n3": ("core_neg", "original", "legit_core_neg", "core", "legit"),
    "n1#para_high": ("ctrl_para_legit", "para_high", "legit_ctrl_para", "core", "legit"),
    "m1": ("ctrl_modern_legit", "original", "legit_ctrl_modern", "core", "legit"),
    "m2": ("ctrl_modern_legit", "original", "legit_ctrl_modern", "core", "legit"),
    "g1": ("gen_phish", "original", "gen_phish", "generalisation", "phish"),
    "g2": ("gen_legit", "original", "gen_legit", "generalisation", "legit"),
}
# p1 TP, p2 FN, p3 invalid; n1 TN, n2 FP, n3 invalid; m1 TN, m2 FP; g1 TP, g2 TN
PREDS = {"p1": "phish", "p2": "legit", "p3": "invalid", "p1#para_high": "phish", "n1": "legit", "n2": "phish", "n3": "invalid",
         "n1#para_high": "legit", "m1": "legit", "m2": "phish", "g1": "phish", "g2": "legit"}


def toy(preds=PREDS) -> pd.DataFrame:
    rows = []
    for iid, (part, cond, cls, pset, truth) in META.items():
        rows.append({"detector": "m1", "kind": "llm", "strategy": "zero_shot", "item_id": iid, "cluster": iid.split("#")[0],
                     "partition": part, "condition": cond, "item_class": cls, "partition_set": pset, "label_true": truth,
                     "label_pred": preds[iid], "invalid": preds[iid] == "invalid", "score": np.nan, "source": "x",
                     "subclass": "y", "body_words": 10, "latency_s": 0.1, "n_prompt_tokens": 5, "truncated_input": False,
                     "backend": "cuda"})
    return annotate(pd.DataFrame(rows))


CELL = ("m1", "llm", "zero_shot")


class TestPrecisionFpr(unittest.TestCase):
    def test_stat_precision(self):
        self.assertAlmostEqual(float(pf.stat_precision(np.array([3, 1]))), 0.75)
        self.assertTrue(math.isnan(float(pf.stat_precision(np.array([0, 0])))))
        boot = pf.stat_precision(np.array([[2, 2], [0, 0], [1, 0]]))
        self.assertAlmostEqual(boot[0], 0.5)
        self.assertTrue(math.isnan(boot[1]))
        self.assertAlmostEqual(boot[2], 1.0)

    def test_confusion_counts_primary(self):
        d = pf.analysis_frame(toy(), "primary")
        conf = pd.DataFrame(pf.confusion_rows(CELL, d, "primary")).set_index("group")
        self.assertEqual(conf.loc["phish_original"][["n", "pred_phish", "pred_legit", "invalid", "correct"]].tolist(), [3, 1, 1, 1, 1])
        self.assertEqual(conf.loc["legit_core_neg"][["n", "pred_phish", "pred_legit", "invalid", "correct"]].tolist(), [3, 1, 1, 1, 1])
        self.assertEqual(conf.loc["legit_ctrl_modern"][["n", "pred_phish", "pred_legit", "invalid", "correct"]].tolist(), [2, 1, 1, 0, 1])
        self.assertEqual(conf.loc["phish_obf_low"]["n"], 0)

    def test_precision_and_fpr_values(self):
        for analysis, tp, fp in (("primary", 1, 2), ("no_invalid", 1, 2)):
            d = pf.analysis_frame(toy(), analysis)
            rows = pd.DataFrame(pf.metric_rows(CELL, d, analysis, 2026, 50)).set_index(["metric", "condition"])
            self.assertAlmostEqual(rows.loc[("precision", "core_originals"), "value"], tp / (tp + fp))
            self.assertEqual(rows.loc[("precision", "core_originals"), ["num", "den"]].tolist(), [tp, tp + fp])
            self.assertAlmostEqual(rows.loc[("precision", "generalisation"), "value"], 1.0)
            self.assertAlmostEqual(rows.loc[("fpr", "legit_ctrl_modern"), "value"], 0.5)
            self.assertAlmostEqual(rows.loc[("fpr", "legit_ctrl_para"), "value"], 0.0)
            self.assertAlmostEqual(rows.loc[("fpr", "gen_legit"), "value"], 0.0)
        # primary: the invalid legit item stays in n (FPR 1/3 on core_neg, pooled 2/5); no_invalid: it is dropped (1/2, 2/4)
        prim = pd.DataFrame(pf.metric_rows(CELL, pf.analysis_frame(toy(), "primary"), "primary", 2026, 50)).set_index(["metric", "condition"])
        noinv = pd.DataFrame(pf.metric_rows(CELL, pf.analysis_frame(toy(), "no_invalid"), "no_invalid", 2026, 50)).set_index(["metric", "condition"])
        self.assertAlmostEqual(prim.loc[("fpr", "legit_core_neg"), "value"], 1 / 3)
        self.assertAlmostEqual(prim.loc[("fpr", pf.POOLED_LEGIT), "value"], 2 / 5)
        self.assertAlmostEqual(noinv.loc[("fpr", "legit_core_neg"), "value"], 1 / 2)
        self.assertAlmostEqual(noinv.loc[("fpr", pf.POOLED_LEGIT), "value"], 2 / 4)

    def test_precision_nan_when_nothing_labelled_phishing(self):
        preds = {k: ("invalid" if k == "p3" else "legit") for k in PREDS}
        d = pf.analysis_frame(toy(preds), "primary")
        rows = pd.DataFrame(pf.metric_rows(CELL, d, "primary", 2026, 50)).set_index(["metric", "condition"])
        self.assertTrue(math.isnan(rows.loc[("precision", "core_originals"), "value"]))
        self.assertTrue(math.isnan(rows.loc[("precision", "core_originals"), "ci_lo"]))
        self.assertEqual(rows.loc[("precision", "core_originals"), "den"], 0)

    def test_recomputed_metrics_match_scoring_code(self):
        items = toy()
        stored = []
        for analysis in ("primary", "no_invalid"):
            stored += cell_metrics(CELL, items.set_index("item_id", drop=False), analysis, 2026, 50)
        stored = pd.DataFrame(stored)
        recomputed = []
        for analysis in ("primary", "no_invalid"):
            recomputed += pf.recomputed_metrics(CELL, pf.analysis_frame(items, analysis), analysis)
        res = pf.compare_with_stored(recomputed, stored)
        self.assertEqual(res["n_mismatch"], 0, res["mismatches"])
        self.assertGreater(res["n_compared"], 10)

    def test_fpr_identity(self):
        items = toy()
        conf, rows, stored = [], [], []
        for analysis in ("primary", "no_invalid"):
            d = pf.analysis_frame(items, analysis)
            conf += pf.confusion_rows(CELL, d, analysis)
            rows += pf.metric_rows(CELL, d, analysis, 2026, 50)
            stored += cell_metrics(CELL, items.set_index("item_id", drop=False), analysis, 2026, 50)
        stored = pd.DataFrame(stored)
        res = pf.fpr_identity(pd.DataFrame(conf), pd.DataFrame(rows), stored[stored["analysis"] == "primary"])
        self.assertEqual(res["exact_count_identity"]["n_fail"], 0, res)
        self.assertEqual(res["against_stored_invalid_rate"]["n_fail"], 0, res)
        self.assertEqual(res["against_stored_invalid_rate"]["n"], 4)   # the four legitimate groups, primary analysis


if __name__ == "__main__":
    unittest.main()
