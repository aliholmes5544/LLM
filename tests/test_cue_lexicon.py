"""
Unit tests for the CoT cue lexicon (configs/cue_lexicon.yaml, scripts/scoring/cues.py; TASK_07 step 2): the
file loads with the eight pre-registered categories and compiling, uniquely named patterns; hand-written
sentences assert the expected category and no other; the negation heuristic marks denied mentions as negated
and keeps "lacks X and uses Y" asserted; the rationale split matches the label rule; and the file's sha256 is
the one frozen in reports/cue_lexicon_dev_report.json (editing the lexicon without re-freezing fails here).
Run from the repo root with `python -m unittest discover tests`.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from common import cot_rationale  # noqa: E402
from scoring.cues import CATEGORIES, Lexicon, load_lexicon, lexicon_sha256  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LEXICON = ROOT / "configs" / "cue_lexicon.yaml"
REPORT = ROOT / "reports" / "cue_lexicon_dev_report.json"
LEX = load_lexicon(LEXICON)

# one asserted sentence per category; the expected set is exactly the categories asserted
ASSERTED = {
    "urgency": "The email creates a sense of urgency and demands immediate action.",
    "link_url": "The email asks the recipient to click a link.",
    "sender_mismatch": "The sender's email address does not match the company domain.",
    "credential_payment": "It requests the recipient's password and personal information.",
    "grammar_spelling": "The body contains several misspellings and grammatical errors.",
    "impersonation_authority": "The sender claims to be the CEO.",
    "attachment": "It asks the recipient to open the attached invoice.",
    "generic_greeting": "The email uses a generic greeting.",
}
EXPECTED = {
    "urgency": {"urgency"}, "link_url": {"link_url"}, "sender_mismatch": {"sender_mismatch"},
    "credential_payment": {"credential_payment"}, "grammar_spelling": {"grammar_spelling"},
    "impersonation_authority": {"impersonation_authority"},
    "attachment": {"attachment", "credential_payment"},  # "invoice" is a payment cue as well
    "generic_greeting": {"generic_greeting"},
}


def asserted(text):
    return {c for c, f in LEX.cue_flags(text).items() if f["asserted"]}


def mentioned(text):
    return {c for c, f in LEX.cue_flags(text).items() if f["mentioned"]}


def negated(text):
    return {c for c, f in LEX.cue_flags(text).items() if f["negated"]}


class TestLexiconFile(unittest.TestCase):
    def test_categories_and_patterns(self):
        self.assertEqual(tuple(LEX.spec["categories"]), CATEGORIES)
        for c in CATEGORIES:
            names = [n for n, _ in LEX.patterns[c]]
            self.assertTrue(names, c)
            self.assertEqual(len(names), len(set(names)), c)

    def test_wrong_category_set_refused(self):
        spec = {"negation": LEX.spec["negation"], "categories": {"urgency": LEX.spec["categories"]["urgency"]}}
        with self.assertRaises(ValueError):
            Lexicon(spec)

    def test_frozen_hash_matches_report(self):
        self.assertTrue(REPORT.exists(), "run scripts/07_freeze_lexicon.py first")
        rep = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(rep["lexicon_sha256"], lexicon_sha256(LEXICON),
                         "configs/cue_lexicon.yaml changed after it was frozen; re-run 07_freeze_lexicon.py and log the new hash")
        self.assertEqual(rep["lexicon_version"], LEX.spec["version"])


class TestMatching(unittest.TestCase):
    def test_each_category_asserted(self):
        for c, text in ASSERTED.items():
            self.assertEqual(asserted(text), EXPECTED[c], text)

    def test_neutral_text_has_no_cue(self):
        for text in ("The email confirms the meeting time and thanks the team for their work.",
                     "The message discusses the quarterly report and the project timeline.",
                     "The purpose of the proposal is to expand the partnership."):
            self.assertEqual(mentioned(text), set(), text)

    def test_word_boundaries(self):
        self.assertEqual(mentioned("The purpose of the proposed collaboration is unclear."), set())
        self.assertIn("impersonation_authority", asserted("The sender is posing as a bank manager."))
        self.assertEqual(mentioned("The ClickAtHome program is mentioned."), set())
        self.assertIn("link_url", asserted("Recipients are told to click here."))

    def test_matches_are_ordered_and_typed(self):
        ms = LEX.matches("It uses urgent language and a suspicious link.")
        self.assertEqual([m["category"] for m in ms], ["urgency", "link_url"])
        self.assertEqual(set(ms[0]), {"category", "pattern", "start", "end", "text", "negated"})
        self.assertFalse(any(m["negated"] for m in ms))

    def test_character_anomalies_count_as_grammar_spelling(self):
        for text in ("The body contains unusual spacing and character substitutions like '3' for 'e'.",
                     "Several words use Cyrillic letters that look like Latin ones."):
            self.assertIn("grammar_spelling", asserted(text), text)


class TestNegation(unittest.TestCase):
    def test_denied_list_is_negated(self):
        text = "There are no suspicious links, requests for personal information, or urgent calls to action."
        self.assertEqual(negated(text), {"link_url", "credential_payment", "urgency"})
        self.assertEqual(asserted(text), set())

    def test_does_not_contain(self):
        text = "It does not contain any suspicious links and is free of grammatical errors."
        self.assertEqual(asserted(text), set())
        self.assertEqual(negated(text), {"link_url", "grammar_spelling"})

    def test_lack_of_urgency(self):
        self.assertEqual(negated("The lack of urgency suggests a routine message."), {"urgency"})

    def test_scope_break_keeps_second_cue_asserted(self):
        text = "The email lacks personalization and uses a generic greeting."
        self.assertEqual(asserted(text), {"generic_greeting"})

    def test_clause_break_resets_negation(self):
        text = "The body is free of grammatical errors. However, the email contains a suspicious link."
        self.assertEqual(asserted(text), {"link_url"})
        self.assertEqual(negated(text), {"grammar_spelling"})

    def test_negation_inside_the_match_is_an_assertion(self):
        self.assertEqual(asserted("The email is not personalized."), {"generic_greeting"})
        self.assertEqual(asserted("It does not address the recipient by name."), {"generic_greeting"})

    def test_rather_than_is_negation(self):
        text = "The email is addressed to a specific person, rather than a generic recipient."
        self.assertEqual(negated(text), {"generic_greeting"})


class TestRationale(unittest.TestCase):
    def test_split_before_last_final(self):
        self.assertEqual(cot_rationale("Reason one.\nFINAL: PHISHING"), "Reason one.")
        self.assertEqual(cot_rationale("Step.\nFinal: legit\nFINAL: PHISHING"), "Step.\nFinal: legit")
        self.assertEqual(cot_rationale(" FINAL: LEGITIMATE\nLEGITIMATE"), "")
        self.assertEqual(cot_rationale("No marker at all"), "No marker at all")
        self.assertEqual(cot_rationale(""), "")

    def test_rationale_flags_ignore_the_verdict_line(self):
        f = LEX.rationale_flags("No red flags.\nFINAL: LEGITIMATE")
        self.assertFalse(any(v["mentioned"] for v in f.values()))


if __name__ == "__main__":
    unittest.main()
