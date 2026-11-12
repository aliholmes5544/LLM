"""
Tests for scripts/07_twostage_compare.py (TASK_08 section 7): on a toy item table the difference of deltas equals the
two-stage delta minus the direct delta on the same pairs, the no_invalid analysis drops a pair when any arm is invalid,
the rate differences and the disagreement counts match hand counts, the families are the fits' own and Holm is applied
within them. Run from the repo root with `python -m unittest discover tests`.
"""
import importlib
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scoring.score import annotate, apply_holm  # noqa: E402

cmp = importlib.import_module("07_twostage_compare")

MODEL, TS = "m", "twostage_m"
TCFG = {"models": [MODEL], "fits": {"clean": {"rows": "originals", "strategy_key": "lr_clean", "primary": True},
                                    "all": {"rows": "all", "strategy_key": "lr_all", "primary": False}}}


def toy_cells():
    """8 phishing originals with a para_high variant each, 4 legitimate controls with a para_high variant, 4 modern legit.
    direct: originals right on 6/8, variants right on 2/8 (delta +0.5); control originals 4/4 right, variants 2/4.
    lr_clean: originals right on 4/8, variants right on 4/8 (delta 0); control 3/4 and 3/4. lr_all: like direct but one
    original invalid (item p0) and all variants right."""
    rows = []

    def add(det, strat, kind, item_id, cluster, cond, cls, true, pred, invalid=False):
        rows.append({"detector": det, "kind": kind, "strategy": strat, "item_id": item_id, "cluster": cluster, "partition": "x",
                     "condition": cond, "item_class": cls, "partition_set": "core", "label_true": true, "label_pred": pred, "invalid": invalid})

    for i in range(8):
        o, v = f"p{i}", f"p{i}#para_high"
        add(MODEL, "zero_shot", "llm", o, o, "original", "phish_original", "phish", "phish" if i < 6 else "legit")
        add(MODEL, "zero_shot", "llm", v, o, "para_high", "phish_variant", "phish", "phish" if i < 2 else "legit")
        add(TS, "lr_clean", "twostage", o, o, "original", "phish_original", "phish", "phish" if i < 4 else "legit")
        add(TS, "lr_clean", "twostage", v, o, "para_high", "phish_variant", "phish", "phish" if i < 4 else "legit")
        add(TS, "lr_all", "twostage", o, o, "original", "phish_original", "phish", "invalid" if i == 0 else ("phish" if i < 6 else "legit"), i == 0)
        add(TS, "lr_all", "twostage", v, o, "para_high", "phish_variant", "phish", "phish")
    for i in range(4):
        o, v = f"c{i}", f"c{i}#para_high"
        add(MODEL, "zero_shot", "llm", o, o, "original", "legit_core_neg", "legit", "legit")
        add(MODEL, "zero_shot", "llm", v, o, "para_high", "legit_ctrl_para", "legit", "legit" if i < 2 else "phish")
        for s in ("lr_clean", "lr_all"):
            add(TS, s, "twostage", o, o, "original", "legit_core_neg", "legit", "legit" if i < 3 else "phish")
            add(TS, s, "twostage", v, o, "para_high", "legit_ctrl_para", "legit", "legit" if i < 3 else "phish")
    for i in range(4):
        o = f"n{i}"
        add(MODEL, "zero_shot", "llm", o, o, "original", "legit_ctrl_modern", "legit", "legit")
        for s in ("lr_clean", "lr_all"):
            add(TS, s, "twostage", o, o, "original", "legit_ctrl_modern", "legit", "legit" if i < 2 else "phish")
    items = annotate(pd.DataFrame(rows))
    cells = {k: d.set_index("item_id", drop=False).sort_index() for k, d in items.groupby(["detector", "strategy"], sort=False)}
    pairs = pd.DataFrame([{"cluster": f"p{i}", "condition": "para_high", "variant_id": f"p{i}#para_high", "item_class": "phish_variant"} for i in range(8)] +
                         [{"cluster": f"c{i}", "condition": "para_high", "variant_id": f"c{i}#para_high", "item_class": "legit_ctrl_para"} for i in range(4)])
    return cells, pairs


class TestTwostageCompare(unittest.TestCase):
    def setUp(self):
        self.cells, self.pairs = toy_cells()

    def test_contrast_is_twostage_delta_minus_direct_delta(self):
        rows = cmp.contrast_rows(self.cells, self.pairs, MODEL, "clean", "lr_clean", "primary", 2026, 50)
        r = {x["condition"]: x for x in rows}
        self.assertEqual(sorted(r), sorted(cmp.CONDITIONS))
        ph = r["para_high"]
        self.assertEqual((ph["n_pairs"], ph["metric"], ph["family"], ph["arm_a"], ph["arm_b"]), (8, "sens", "A-twostage-m-clean", "m/zero_shot", "twostage_m/lr_clean"))
        self.assertAlmostEqual(ph["delta_direct"], 6 / 8 - 2 / 8)
        self.assertAlmostEqual(ph["delta_twostage"], 0.0)
        self.assertAlmostEqual(ph["value"], ph["delta_twostage"] - ph["delta_direct"])
        self.assertTrue(ph["ci_lo"] <= ph["value"] <= ph["ci_hi"])
        self.assertTrue(0 < ph["boot_p"] <= 1)
        ctrl = r["para_high_ctrl"]
        self.assertEqual((ctrl["n_pairs"], ctrl["metric"]), (4, "spec"))
        self.assertAlmostEqual(ctrl["delta_direct"], 4 / 4 - 2 / 4)
        self.assertAlmostEqual(ctrl["delta_twostage"], 0.0)
        self.assertTrue(np.isnan(r["obf_high"]["value"]))          # no obf pairs in the toy table

    def test_no_invalid_drops_the_pair_when_any_arm_is_invalid(self):
        prim = {x["condition"]: x for x in cmp.contrast_rows(self.cells, self.pairs, MODEL, "all", "lr_all", "primary", 2026, 50)}["para_high"]
        noinv = {x["condition"]: x for x in cmp.contrast_rows(self.cells, self.pairs, MODEL, "all", "lr_all", "no_invalid", 2026, 50)}["para_high"]
        self.assertEqual((prim["n_pairs"], noinv["n_pairs"]), (8, 7))
        self.assertAlmostEqual(prim["delta_twostage"], 5 / 8 - 1.0)          # invalid counts as incorrect
        self.assertAlmostEqual(noinv["delta_twostage"], 5 / 7 - 1.0)
        self.assertAlmostEqual(noinv["delta_direct"], 5 / 7 - 1 / 7)          # p0 dropped: its variant was one of the two direct hits
        self.assertEqual(prim["family"], "A-twostage-m-all")

    def test_rate_differences_and_balanced_accuracy(self):
        rows = {(x["metric"], x["condition"]): x for x in cmp.rate_diff_rows(self.cells, MODEL, "clean", "lr_clean", 2026, 50)}
        s = rows[("sens", "original")]
        self.assertEqual((s["n"], s["n_clusters"]), (8, 8))
        self.assertAlmostEqual(s["rate_direct"], 6 / 8); self.assertAlmostEqual(s["rate_twostage"], 4 / 8); self.assertAlmostEqual(s["value"], -2 / 8)
        v = rows[("sens", "para_high")]
        self.assertAlmostEqual(v["value"], 4 / 8 - 2 / 8)
        c = rows[("spec", "para_high_ctrl")]
        self.assertAlmostEqual(c["value"], 3 / 4 - 2 / 4)
        acc = rows[("acc", "core_originals")]
        self.assertEqual(acc["n"], 16)
        self.assertAlmostEqual(acc["value"], (4 + 3 + 2) / 16 - (6 + 4 + 4) / 16)
        ba = rows[("bal_acc", "core_originals")]
        self.assertAlmostEqual(ba["rate_direct"], 0.5 * (6 / 8 + 8 / 8))
        self.assertAlmostEqual(ba["rate_twostage"], 0.5 * (4 / 8 + 5 / 8))
        self.assertAlmostEqual(ba["value"], ba["rate_twostage"] - ba["rate_direct"])
        self.assertTrue(np.isnan(rows[("gen_sens", "gen_phish")]["value"]))

    def test_disagreement_counts(self):
        rows = {x["group"]: x for x in cmp.disagreement_rows(self.cells, MODEL, "clean", "lr_clean")}
        o = rows["phish_original"]
        self.assertEqual((o["n"], o["n_disagree"], o["direct_only_correct"], o["twostage_only_correct"], o["both_correct"], o["neither_correct"]), (8, 2, 2, 0, 4, 2))
        self.assertEqual(rows["all"]["n"], 28)
        self.assertEqual(rows["all"]["n_disagree"], sum(rows[g]["n_disagree"] for g in rows if g != "all"))

    def test_run_applies_holm_within_the_fit_family(self):
        res = cmp.run(self.cells, self.pairs, TCFG, 2026, 50, log=lambda s: None)
        C = res["contrasts"]
        self.assertEqual(set(C["family"]), {"A-twostage-m-clean", "A-twostage-m-all"})
        self.assertEqual(res["families"], {"A-twostage-m-all": 5, "A-twostage-m-clean": 5})
        prim = C[(C["analysis"] == "primary") & (C["family"] == "A-twostage-m-clean")]
        self.assertTrue((prim["holm_p"].dropna() >= prim.loc[prim["holm_p"].notna(), "boot_p"]).all())
        again = apply_holm(C.drop(columns="holm_p").assign(holm_p=np.nan), "boot_p", ["analysis", "family"])
        pd.testing.assert_series_equal(again["holm_p"], C["holm_p"])
        self.assertEqual(len(res["rate_differences"]), 2 * (len(cmp.DIFF_METRICS) + 2))
        self.assertEqual(len(res["disagreement"]), 2 * 11)

    def test_fits_order_puts_the_primary_first(self):
        self.assertEqual(cmp.fits_of(TCFG), [("clean", "lr_clean", True), ("all", "lr_all", False)])


if __name__ == "__main__":
    unittest.main()
