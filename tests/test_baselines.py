"""
Unit tests for scripts/baselines/ (TASK_06 section 3): the fixed decision rule, the selection metrics and the
C tie rule, the config hash, the resume adapter, and the determinism of the TF-IDF fit and model_hash on a toy
corpus. No project data, no network. Run from the repo root with `python -m unittest discover tests`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from baselines.core import (label_from_score, prf, select_C, config_hash, rows_for_decide, item_text)  # noqa: E402
from detect.resume import decide, SKIP  # noqa: E402

TOY = [("Urgent: verify your account now", "Your account is suspended. Click the link to verify your password today.", "phish"),
       ("Payroll update required", "Please confirm your bank details through the link to receive your salary.", "phish"),
       ("Invoice overdue", "Final notice: pay the attached invoice immediately or your service stops.", "phish"),
       ("Security alert", "Unusual sign in detected. Reset your password using the link below.", "phish"),
       ("Lunch tomorrow", "Are we still on for lunch tomorrow at noon? Let me know if the time works.", "legit"),
       ("Meeting notes", "Attached are the notes from this morning. The next review is on Thursday.", "legit"),
       ("Gas nomination", "The nomination for the pipeline volumes for next week is confirmed as discussed.", "legit"),
       ("Schedule change", "The Friday call moves to 3 pm. Same dial in as usual. Thanks.", "legit")]
TEXT_CFG = {"fields": ["subject", "body"], "join": "\n\n"}
BCFG = {"text": TEXT_CFG, "positive_class": "phish",
        "baselines": {"a": {"features": {"min_df": 1}}, "b": {"features": {"min_df": 2}}}}


class DecisionRule(unittest.TestCase):
    def test_probability_rule_is_inclusive_at_half(self):
        self.assertEqual(label_from_score(0.5, ">= 0.5"), "phish")
        self.assertEqual(label_from_score(0.4999, ">= 0.5"), "legit")

    def test_svm_rule_sends_zero_to_legit(self):
        self.assertEqual(label_from_score(0.0, "> 0"), "legit")
        self.assertEqual(label_from_score(1e-9, "> 0"), "phish")
        self.assertEqual(label_from_score(-2.0, "> 0"), "legit")


class SelectionMetrics(unittest.TestCase):
    def test_prf_counts(self):
        m = prf(["phish", "phish", "legit", "legit"], ["phish", "legit", "phish", "legit"])
        self.assertEqual((m["tp"], m["fp"], m["fn"], m["tn"]), (1, 1, 1, 1))
        self.assertEqual((m["precision"], m["recall"], m["f1"], m["accuracy"]), (0.5, 0.5, 0.5, 0.5))

    def test_prf_no_positive_predictions(self):
        m = prf(["phish", "legit"], ["legit", "legit"])
        self.assertEqual((m["precision"], m["recall"], m["f1"]), (0.0, 0.0, 0.0))

    def test_tie_goes_to_smallest_C(self):
        self.assertEqual(select_C({0.1: 0.9, 1.0: 0.95, 10.0: 0.95}), 1.0)
        self.assertEqual(select_C({10.0: 0.8, 0.3: 0.8, 1.0: 0.8}), 0.3)
        self.assertEqual(select_C({0.1: 0.7, 1.0: 0.9}), 1.0)


class ConfigHashAndText(unittest.TestCase):
    def test_hash_depends_only_on_own_block_text_and_seed(self):
        h = config_hash("a", BCFG, 2026)
        other = {**BCFG, "baselines": {**BCFG["baselines"], "b": {"features": {"min_df": 5}}}}
        self.assertEqual(config_hash("a", other, 2026), h)            # editing b leaves a's hash alone
        self.assertNotEqual(config_hash("a", BCFG, 2027), h)          # seed is part of it
        changed = {**BCFG, "baselines": {**BCFG["baselines"], "a": {"features": {"min_df": 2}}}}
        self.assertNotEqual(config_hash("a", changed, 2026), h)
        self.assertEqual(len(h), 64)

    def test_item_text_is_subject_and_body_only(self):
        item = {"subject": "S", "body": "B", "sender": "x@y", "item_id": "i"}
        self.assertEqual(item_text(item, TEXT_CFG), "S\n\nB")

    def test_resume_adapter_lets_complete_cell_skip(self):
        rows = [{"item_id": i, "config_hash": "c", "model_hash": "m"} for i in ("i1", "i2")]
        self.assertEqual(decide(rows_for_decide(rows), ["i1", "i2"], "c", "m", force=False, reason=""), SKIP)
        with self.assertRaises(SystemExit):
            decide(rows_for_decide(rows), ["i1", "i2"], "c-other", "m", force=False, reason="")


class TfidfFitDeterminism(unittest.TestCase):
    ENTRY = {"features": {"analyzer": "word", "ngram_range": [1, 2], "min_df": 1, "lowercase": True,
                          "sublinear_tf": True, "max_features": None},
             "classifier": {"type": "LogisticRegression", "solver": "lbfgs", "max_iter": 1000, "class_weight": None},
             "C_grid": [0.1, 1.0, 10.0], "selection": {"metric": "f1_phish", "partition": "valid", "tie": "smallest_C"},
             "threshold": {"score": "p_phish", "rule": ">= 0.5"}}

    def _fit(self, entry):
        from baselines import tfidf
        texts = [s + "\n\n" + b for s, b, _ in TOY]
        y = [c for _, _, c in TOY]
        return tfidf.fit(entry, texts, y, texts, y, 2026, "phish")

    def test_refit_gives_same_hash_and_scores(self):
        from baselines import tfidf
        m1, m2 = self._fit(self.ENTRY), self._fit(self.ENTRY)
        self.assertEqual(tfidf.model_hash(m1), tfidf.model_hash(m2))
        s1 = tfidf.score_one(m1, "verify your password via the link", "phish")
        s2 = tfidf.score_one(m2, "verify your password via the link", "phish")
        self.assertEqual(s1, s2)
        self.assertIn(m1["C"], self.ENTRY["C_grid"])
        self.assertEqual(set(m1["selection_table"]), set(self.ENTRY["C_grid"]))

    def test_svm_scores_are_signed_towards_phish(self):
        from baselines import tfidf
        entry = {**self.ENTRY, "classifier": {"type": "LinearSVC", "loss": "squared_hinge", "max_iter": 10000,
                                              "class_weight": None}, "threshold": {"score": "decision_function", "rule": "> 0"}}
        m = self._fit(entry)
        phish_score, _ = tfidf.score_one(m, "verify your account password through the link now", "phish")
        legit_score, _ = tfidf.score_one(m, "lunch tomorrow at noon, let me know", "phish")
        self.assertGreater(phish_score, legit_score)
        self.assertNotEqual(tfidf.model_hash(m), tfidf.model_hash(self._fit(self.ENTRY)))


if __name__ == "__main__":
    unittest.main()
