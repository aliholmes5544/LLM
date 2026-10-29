"""
Unit tests for scripts/detect/resume.py: the skip / resume / refuse decision of 06_run_detection.py.
Run from the repo root with `python -m unittest discover tests`. No model, no data needed.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from detect.resume import decide, SKIP, RUN, FORCE  # noqa: E402

P, M = "prompt-hash-a", "model-sha-a"
EXPECTED = ["i1", "i2", "i3"]


def rows(ids, prompt_hash=P, model_hash=M):
    return [{"item_id": i, "prompt_hash": prompt_hash, "model_hash": model_hash} for i in ids]


class SkipCompleteCell(unittest.TestCase):
    def test_complete_with_matching_hashes_is_skipped(self):
        self.assertEqual(decide(rows(EXPECTED), EXPECTED, P, M, force=False, reason=""), SKIP)

    def test_complete_in_any_order_is_skipped(self):
        self.assertEqual(decide(rows(["i3", "i1", "i2"]), EXPECTED, P, M, force=False, reason=""), SKIP)

    def test_unpinned_model_hash_is_not_checked(self):
        self.assertEqual(decide(rows(EXPECTED, model_hash="whatever"), EXPECTED, P, None, force=False, reason=""), SKIP)


class ResumeIncompleteCell(unittest.TestCase):
    def test_no_rows_runs(self):
        self.assertEqual(decide([], EXPECTED, P, M, force=False, reason=""), RUN)

    def test_missing_items_resume(self):
        self.assertEqual(decide(rows(["i1"]), EXPECTED, P, M, force=False, reason=""), RUN)


class Refusals(unittest.TestCase):
    def test_prompt_hash_differs(self):
        with self.assertRaises(SystemExit):
            decide(rows(EXPECTED, prompt_hash="other"), EXPECTED, P, M, force=False, reason="")

    def test_model_hash_differs_even_when_incomplete(self):
        with self.assertRaises(SystemExit):
            decide(rows(["i1"], model_hash="other"), EXPECTED, P, M, force=False, reason="")

    def test_force_without_reason_is_refused(self):
        with self.assertRaises(SystemExit):
            decide(rows(EXPECTED), EXPECTED, P, M, force=True, reason="   ")


class Force(unittest.TestCase):
    def test_force_with_reason_archives_and_reruns(self):
        self.assertEqual(decide(rows(EXPECTED), EXPECTED, P, M, force=True, reason="prompt bug"), FORCE)

    def test_force_with_reason_overrides_hash_mismatch(self):
        self.assertEqual(decide(rows(EXPECTED, prompt_hash="other"), EXPECTED, P, M, force=True, reason="x"), FORCE)

    def test_force_on_empty_cell_just_runs(self):
        self.assertEqual(decide([], EXPECTED, P, M, force=True, reason="x"), RUN)


if __name__ == "__main__":
    unittest.main()
