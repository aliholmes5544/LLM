"""
Tests for the SpearShift extension path (scripts/07_score_model.py, `make evaluate MODEL=<key>`): scoring one
model alone with the same functions reproduces that model's frozen rows of results/scores/metrics_long.csv and
deltas_long.csv (every column except the family and its Holm-corrected p, which belong to the pre-registered
families), the frozen score files keep the hashes recorded in reports/scoring_report.json, and (when the data
are present) building the item rows from the raw files for one model reproduces its rows of items.parquet.
Run from the repo root with `python -m unittest discover tests`.
"""
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from common import load_config  # noqa: E402
from scoring.output import sha256_file, write_csv  # noqa: E402

score_model = importlib.import_module("07_score_model")

ROOT = Path(__file__).resolve().parents[1]
SCORES = ROOT / "results" / "scores"
MODEL = "qwen25-7b"          # any of the six; the smallest zero_shot sensitivity, so invalid and discordant counts vary


def roundtrip(df: pd.DataFrame) -> pd.DataFrame:
    """Write with the project's CSV writer and read back, so both sides carry the same six-digit values."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.csv"
        write_csv(df.reset_index(drop=True), p)
        return pd.read_csv(p)


class TestFrozenScores(unittest.TestCase):
    def setUp(self):
        if not (SCORES / "metrics_long.csv").exists():
            self.skipTest("scores not computed")

    def test_frozen_files_keep_their_recorded_hashes(self):
        rep = json.loads((ROOT / "reports" / "scoring_report.json").read_text(encoding="utf-8"))
        for name, sha in rep["outputs"].items():
            self.assertEqual(sha256_file(SCORES / name), sha, name)

    def test_additional_path_reproduces_frozen_rows_of_one_model(self):
        items = pd.read_parquet(SCORES / "items.parquet")
        pairs = pd.read_csv(SCORES / "pairs.csv")
        seed = load_config("data.yaml")["seed"]
        res = score_model.score_model(items, pairs, MODEL, seed, 2000, log=lambda s: None)
        frozen_m = pd.read_csv(SCORES / "metrics_long.csv")
        frozen_d = pd.read_csv(SCORES / "deltas_long.csv")
        fm = frozen_m[frozen_m["detector"] == MODEL]
        fd = frozen_d[frozen_d["detector"] == MODEL].drop(columns=["holm_p", "family"])
        pd.testing.assert_frame_equal(roundtrip(res["metrics_long"]), roundtrip(fm), check_dtype=False)
        pd.testing.assert_frame_equal(roundtrip(res["deltas_long"].drop(columns=["holm_p", "family"])), roundtrip(fd),
                                      check_dtype=False)
        self.assertEqual(res["families"], {f"A-{MODEL}": 5, f"A-{MODEL}-cot": 5, f"A-{MODEL}-few_shot": 5, f"A-{MODEL}-role": 5})

    def test_families_of_the_additional_model_are_its_own(self):
        self.assertEqual(score_model.family_for("x", "zero_shot"), "A-x")
        self.assertEqual(score_model.family_for("x", "cot"), "A-x-cot")
        self.assertEqual(score_model.family_for("twostage_qwen25-7b", "lr", "twostage"), "A-twostage-qwen25-7b")

    def test_explicit_default_strategies_reproduce_the_frozen_rows(self):
        """The one-strategy option (item 18c) must leave the four-strategy path unchanged."""
        items = pd.read_parquet(SCORES / "items.parquet")
        pairs = pd.read_csv(SCORES / "pairs.csv")
        seed = load_config("data.yaml")["seed"]
        res = score_model.score_model(items, pairs, MODEL, seed, 2000, log=lambda s: None,
                                      strategies=["zero_shot", "few_shot", "cot", "role"], kind="llm")
        frozen = pd.read_csv(SCORES / "deltas_long.csv")
        fd = frozen[frozen["detector"] == MODEL].drop(columns=["holm_p", "family"])
        pd.testing.assert_frame_equal(roundtrip(res["deltas_long"].drop(columns=["holm_p", "family"])), roundtrip(fd), check_dtype=False)

    def test_one_strategy_specs_for_the_twostage_kind(self):
        integ = {"cells": {"twostage_m/lr": {"model": "twostage_m", "strategy": "lr", "file": "f", "file_sha256": "0", "n_rows": 1, "pass": True}}}
        specs = score_model.model_specs(integ, "twostage_m", ["lr"], "twostage")
        self.assertEqual([(s["strategy"], s["kind"]) for s in specs], [("lr", "twostage")])
        with self.assertRaises(SystemExit):
            score_model.model_specs(integ, "twostage_m")          # the four strategies are not there

    def test_model_specs_require_four_passing_cells(self):
        integ = {"cells": {"m/zero_shot": {"model": "m", "strategy": "zero_shot", "file": "f", "file_sha256": "0", "n_rows": 1, "pass": True}}}
        with self.assertRaises(SystemExit):
            score_model.model_specs(integ, "m")
        integ["cells"]["m/zero_shot"]["pass"] = False
        with self.assertRaises(SystemExit):
            score_model.model_specs(integ, "m")


class TestBuildFromRaw(unittest.TestCase):
    def test_model_rows_rebuild_from_raw_files(self):
        integrity = ROOT / "reports" / "integrity_check.json"
        variants = ROOT / "data" / "processed" / "variants_eval.jsonl"
        if not (integrity.exists() and variants.exists() and (SCORES / "items.parquet").exists()):
            self.skipTest("raw results or data not present")
        from detect.items import load_records, load_partitions
        from scoring.items import load_jsonl
        integ = json.loads(integrity.read_text(encoding="utf-8"))
        built = score_model.build_model_items(ROOT, integ, MODEL, load_records(), load_partitions(), load_jsonl(variants))
        frozen = pd.read_parquet(SCORES / "items.parquet")
        frozen = frozen[frozen["detector"] == MODEL].reset_index(drop=True)
        pd.testing.assert_frame_equal(built, frozen, check_dtype=False)


if __name__ == "__main__":
    unittest.main()
