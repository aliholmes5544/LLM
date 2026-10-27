"""
Unit tests for scripts/common.py: extract_label (TASK_06 section 4). Run from the repo root with
`python -m unittest discover tests` (or pytest, if installed). No model, no data needed.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from common import extract_label, INVALID  # noqa: E402


class CleanAnswers(unittest.TestCase):
    def test_upper_case_answers(self):
        self.assertEqual(extract_label("PHISHING", "zero_shot"), "phish")
        self.assertEqual(extract_label("LEGITIMATE", "zero_shot"), "legit")

    def test_lower_and_mixed_case(self):
        self.assertEqual(extract_label("phishing", "few_shot"), "phish")
        self.assertEqual(extract_label("Legitimate", "role"), "legit")

    def test_surrounding_whitespace_and_trailing_punctuation(self):
        self.assertEqual(extract_label("  PHISHING.\n", "zero_shot"), "phish")
        self.assertEqual(extract_label("LEGITIMATE!!!", "zero_shot"), "legit")
        self.assertEqual(extract_label("**PHISHING**", "zero_shot"), "phish")
        self.assertEqual(extract_label('"Legitimate".', "zero_shot"), "legit")

    def test_answer_followed_by_explanation_without_the_other_word(self):
        self.assertEqual(extract_label("PHISHING. The message urges the reader to act now.", "zero_shot"), "phish")

    def test_same_label_repeated_is_still_one_label(self):
        self.assertEqual(extract_label("PHISHING. Phishing.", "zero_shot"), "phish")


class InvalidAnswers(unittest.TestCase):
    def test_both_tokens(self):
        self.assertEqual(extract_label("PHISHING or LEGITIMATE", "zero_shot"), INVALID)
        self.assertEqual(extract_label("LEGITIMATE. It is not phishing.", "zero_shot"), INVALID)

    def test_neither_token(self):
        self.assertEqual(extract_label("I cannot decide from the text alone.", "zero_shot"), INVALID)
        self.assertEqual(extract_label("SPAM", "zero_shot"), INVALID)

    def test_whole_word_only(self):
        self.assertEqual(extract_label("legit", "zero_shot"), INVALID)
        self.assertEqual(extract_label("legitimately sent", "zero_shot"), INVALID)
        self.assertEqual(extract_label("antiphishing", "zero_shot"), INVALID)

    def test_empty_and_whitespace_and_none(self):
        self.assertEqual(extract_label("", "zero_shot"), INVALID)
        self.assertEqual(extract_label("   \n", "cot"), INVALID)
        self.assertEqual(extract_label(None, "zero_shot"), INVALID)


class ChainOfThought(unittest.TestCase):
    ANALYSIS = ("The message asks the recipient to confirm a password through a link and creates urgency. "
                "Although the sender claims to be legitimate, these are classic phishing signs.")

    def test_final_marker_decides_even_if_analysis_mentions_both_words(self):
        self.assertEqual(extract_label(self.ANALYSIS + "\nFINAL: PHISHING", "cot"), "phish")
        self.assertEqual(extract_label(self.ANALYSIS + "\nFINAL: LEGITIMATE", "cot"), "legit")

    def test_last_final_marker_wins(self):
        text = "FINAL: LEGITIMATE\nOn reflection the link is suspicious.\nFINAL: PHISHING"
        self.assertEqual(extract_label(text, "cot"), "phish")

    def test_marker_tolerates_markdown_case_and_spacing(self):
        self.assertEqual(extract_label("Analysis...\n**FINAL:** LEGITIMATE", "cot"), "legit")
        self.assertEqual(extract_label("Analysis...\nFinal : phishing.", "cot"), "phish")
        self.assertEqual(extract_label("Analysis...\nFINAL:PHISHING", "cot"), "phish")

    def test_without_marker_whole_output_is_used(self):
        self.assertEqual(extract_label("This looks like phishing because of the urgent tone.", "cot"), "phish")
        self.assertEqual(extract_label(self.ANALYSIS, "cot"), INVALID)   # both words, no marker

    def test_marker_with_empty_or_ambiguous_answer_is_invalid(self):
        self.assertEqual(extract_label(self.ANALYSIS + "\nFINAL:", "cot"), INVALID)
        self.assertEqual(extract_label("FINAL: PHISHING or LEGITIMATE", "cot"), INVALID)
        self.assertEqual(extract_label("FINAL: not sure", "cot"), INVALID)

    def test_marker_is_ignored_for_other_strategies(self):
        text = "The sender seems legitimate.\nFINAL: PHISHING"
        self.assertEqual(extract_label(text, "cot"), "phish")
        self.assertEqual(extract_label(text, "zero_shot"), INVALID)   # both words in the whole output


if __name__ == "__main__":
    unittest.main()
