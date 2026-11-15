"""Unit tests for the pure rules of scripts/07_coding_crosscheck.py (the hard-core coding cross-check)."""
import importlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
cc = importlib.import_module("07_coding_crosscheck")

THREAT = ["urgency", "link_or_url", "sender_claim_inconsistency", "credential_or_payment_request",
          "grammar_anomaly", "impersonation_authority", "attachment", "generic_greeting"]


def ind(**over):
    base = {k: "no" for k in THREAT}
    base.update(over)
    return base


class CrosscheckRules(unittest.TestCase):
    def test_original_of(self):
        self.assertEqual(cc.original_of("nah:x#para_low"), "nah:x")
        self.assertEqual(cc.original_of("nah:x"), "nah:x")

    def test_cue_dropped_needs_yes_to_no(self):
        self.assertTrue(cc.rule_result("paraphrase_cue_dropped", ind(link_or_url="no"), ind(link_or_url="yes"), THREAT))
        self.assertFalse(cc.rule_result("paraphrase_cue_dropped", ind(link_or_url="yes"), ind(link_or_url="yes"), THREAT))
        self.assertFalse(cc.rule_result("paraphrase_cue_dropped", ind(link_or_url="unclear"), ind(link_or_url="yes"), THREAT))

    def test_softened_accepts_no_or_unclear(self):
        self.assertTrue(cc.rule_result("paraphrase_softened", ind(urgency="unclear"), ind(urgency="yes"), THREAT))
        self.assertFalse(cc.rule_result("paraphrase_softened", ind(urgency="yes"), ind(urgency="yes"), THREAT))

    def test_neutral_means_no_change(self):
        self.assertTrue(cc.rule_result("paraphrase_neutral", ind(urgency="yes"), ind(urgency="yes"), THREAT))
        self.assertFalse(cc.rule_result("paraphrase_neutral", ind(attachment="yes"), ind(), THREAT))
        self.assertEqual(cc.threat_changes(ind(), ind(attachment="yes"), THREAT),
                         [{"indicator": "attachment", "original": "no", "variant": "yes"}])

    def test_no_call_to_action_and_descriptive(self):
        self.assertTrue(cc.rule_result("no_call_to_action", ind(), None, THREAT))
        self.assertFalse(cc.rule_result("no_call_to_action", ind(credential_or_payment_request="yes"), None, THREAT))
        self.assertIsNone(cc.rule_result("personalised_pretext", ind(), None, THREAT))
        self.assertEqual(cc.n_asserted(ind(urgency="yes", attachment="yes"), THREAT), 2)

    def test_crosscheck_counts_and_disagreements(self):
        coding = [{"sample_id": "1", "set": "posthoc", "stratum": "para_low", "item_id": "a#para_low",
                   "failure_type": "paraphrase_cue_dropped"},
                  {"sample_id": "2", "set": "posthoc", "stratum": "original", "item_id": "b",
                   "failure_type": "personalised_pretext"}]
        ex = {"m1": {"a": ind(link_or_url="yes"), "a#para_low": ind(), "b": ind(urgency="yes", attachment="yes")},
              "m2": {"a": ind(link_or_url="yes"), "a#para_low": ind(link_or_url="yes"), "b": ind()}}
        per_code, rows, dis = cc.crosscheck(coding, ex, THREAT)
        self.assertEqual(per_code["paraphrase_cue_dropped"]["per_model"]["m1"]["count_rule_met"], 1)
        self.assertEqual(per_code["paraphrase_cue_dropped"]["per_model"]["m2"]["count_rule_met"], 0)
        self.assertEqual([d["model"] for d in dis], ["m2"])
        self.assertEqual(per_code["personalised_pretext"]["per_model"]["m1"]["mean_threat_indicators_asserted"], 2.0)
        self.assertNotIn("count_rule_met", per_code["personalised_pretext"]["per_model"]["m1"])
        self.assertEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
