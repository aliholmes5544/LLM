"""
Tests for the hard-core coding workbook (scripts/07_coding_sheet.py, scripts/07_import_coding.py,
scripts/scoring/hardcore_codes.py): the code lists equal the guide's tables, a built sheet reads back, a filled
code is imported into the two coding columns only, and bad codes or a missing note are refused. Toy rows; the
real sample is used only when its texts are present.
"""
import importlib
import re
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scoring.hardcore_codes import ORIGINAL_CODES, VARIANT_CODES  # noqa: E402

sheet_mod = importlib.import_module("07_coding_sheet")
import_mod = importlib.import_module("07_import_coding")

ROOT = Path(__file__).resolve().parents[1]
MODELS = ["llama31-8b", "mistral-7b", "gemma2-9b", "qwen25-7b", "qwen25-14b", "gemma2-27b"]


def toy_sample() -> pd.DataFrame:
    rows = []
    for sid, (s, cond, iid) in enumerate([("preregistered", "para_low", "a#para_low"), ("posthoc", "original", "b"),
                                          ("posthoc", "para_high", "c#para_high")], start=1):
        r = {"sample_id": str(sid), "set": s, "item_id": iid, "cluster": iid.split("#")[0], "group": "x", "item_class": "x",
             "condition": cond, "partition": "core_pos", "source": "nahmias", "subclass": "spear_llm", "label_true": "phish",
             "body_words": "10", "n_models_wrong": "6", "hard_group": "all_six"}
        for m in MODELS:
            r[f"pred_{m}"] = "legit"
        r["pred_gemma2-27b"] = "phish" if sid == 2 else "invalid"
        r["failure_type"], r["note"] = "", ""
        rows.append(r)
    return pd.DataFrame(rows)


def toy_texts() -> dict:
    return {1: {"sample_id": 1, "item_id": "a#para_low", "subject": "s1", "body": "variant one", "original_body": "orig one"},
            2: {"sample_id": 2, "item_id": "b", "subject": "s2", "body": "orig two", "original_body": "orig two"},
            3: {"sample_id": 3, "item_id": "c#para_high", "subject": "s3", "body": "variant three", "original_body": "orig three"}}


class TestCodes(unittest.TestCase):
    def test_code_lists_match_the_guide(self):
        guide = (ROOT / "docs" / "HARDCORE_CODING_GUIDE.md").read_text(encoding="utf-8")
        orig_part, var_part = guide.split("**Question for a variant")
        in_guide = lambda text: re.findall(r"^\| `([a-z_]+)` \|", text, flags=re.M)
        self.assertEqual(in_guide(orig_part), list(ORIGINAL_CODES))
        self.assertEqual(in_guide(var_part), list(VARIANT_CODES))
        self.assertLess(len(",".join(ORIGINAL_CODES)), 255)      # Excel's limit for an inline list
        self.assertLess(len(",".join(VARIANT_CODES)), 255)


class TestSheetRoundTrip(unittest.TestCase):
    def test_build_fill_import(self):
        sample, texts = toy_sample(), toy_texts()
        rows = sheet_mod.sheet_rows(sample, texts)
        self.assertEqual([r["variant_body"] for r in rows], ["variant one", "", "variant three"])
        self.assertEqual(rows[1]["models_missed"], "llama31-8b, mistral-7b, gemma2-9b, qwen25-7b, qwen25-14b")
        self.assertEqual(rows[0]["n_models_missed"], 6)
        with tempfile.TemporaryDirectory() as td:
            x = Path(td) / "c.xlsx"
            sheet_mod.build(rows, x)
            from openpyxl import load_workbook
            wb = load_workbook(x)
            ws = wb["coding"]
            self.assertEqual(ws.freeze_panes, "A2")
            self.assertEqual([c.value for c in ws[1]], [n for n, _ in sheet_mod.COLUMNS])
            self.assertEqual(len(ws.data_validations.dataValidation), 2)
            col = [n for n, _ in sheet_mod.COLUMNS].index("failure_type") + 1
            ws.cell(row=2, column=col, value="paraphrase_softened")
            ws.cell(row=2, column=col + 1, value="urgency gone")
            ws.cell(row=3, column=col, value="other")                 # original row, note missing -> refused
            wb.save(x)
            sheet = import_mod.read_sheet(x)
            problems = import_mod.validate(sheet, sample)
            self.assertEqual(len(problems), 1)
            self.assertIn("needs a note", problems[0])
            ws.cell(row=3, column=col + 1, value="why")
            ws.cell(row=4, column=col, value="plausible_business")    # variant row with an original code -> refused
            wb.save(x)
            sheet = import_mod.read_sheet(x)
            problems = import_mod.validate(sheet, sample)
            self.assertEqual(len(problems), 1)
            self.assertIn("not in the variant list", problems[0])
            ws.cell(row=4, column=col, value="meaning_shifted")
            wb.save(x)
            sheet = import_mod.read_sheet(x)
            self.assertEqual(import_mod.validate(sheet, sample), [])
            merged = import_mod.merge(sheet, sample)
            self.assertTrue(import_mod.unchanged_outside_coding(sample, merged))
            self.assertEqual(list(merged["failure_type"]), ["paraphrase_softened", "other", "meaning_shifted"])
            self.assertEqual(list(merged["note"]), ["urgency gone", "why", ""])
            summ = import_mod.summary(merged)
            self.assertEqual(int(summ["n"].sum()), 3)
            self.assertEqual(set(summ["set"]), {"preregistered", "posthoc"})

    def test_real_sample_texts_match_when_present(self):
        texts = ROOT / "data" / "processed" / "hardcore_sample_text.jsonl"
        if not texts.exists():
            self.skipTest("sample texts not present")
        sample = pd.read_csv(ROOT / "reports" / "hardcore_sample.csv", dtype=str, keep_default_na=False)
        rows = sheet_mod.sheet_rows(sample, sheet_mod.load_texts())
        self.assertEqual(len(rows), len(sample))
        self.assertTrue(all((r["variant_body"] == "") == (r["stratum"] == "original") for r in rows))
        self.assertTrue(all(r["n_models_missed"] >= 4 for r in rows))


if __name__ == "__main__":
    unittest.main()
