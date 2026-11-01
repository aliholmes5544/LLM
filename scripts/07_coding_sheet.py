#!/usr/bin/env python3
"""
07_coding_sheet.py — the author's coding workbook for the hard-core sample (TASK_07 section 4c; QUESTIONS.md items
12c and 17; docs/HARDCORE_CODING_GUIDE.md).

Reads reports/hardcore_sample.csv (38 rows: 8 pre-registered, 30 post hoc) and the sampled texts in
data/processed/hardcore_sample_text.jsonl (data, git-ignored) and writes reports/hardcore_coding.xlsx with one
row per item: sample_id, set, stratum, item_id, subject, the ORIGINAL body, the VARIANT body (empty for an
original), the number and names of the language models that missed the item under zero_shot, then the two coding
columns: failure_type (drop-down list with the guide's codes for the row's type, original or variant) and note
(free text). Codes already present in the CSV are carried into the sheet. A second sheet lists the codes with
their descriptions, a third the instructions. Nothing under results/ is read or written; no score changes.
The filled workbook is read back by scripts/07_import_coding.py.

Usage: python scripts/07_coding_sheet.py [--out reports/hardcore_coding.xlsx]
"""
import argparse
import json
import sys

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from common import ROOT, open_utf8
from scoring.hardcore_codes import ORIGINAL_CODES, VARIANT_CODES, codes_for, row_type
from scoring.score import MODELS

SAMPLE = ROOT / "reports" / "hardcore_sample.csv"
TEXTS = ROOT / "data" / "processed" / "hardcore_sample_text.jsonl"
OUT = ROOT / "reports" / "hardcore_coding.xlsx"
COLUMNS = [("sample_id", 10), ("set", 14), ("stratum", 11), ("item_id", 14), ("subject", 40), ("original_body", 72),
           ("variant_body", 72), ("n_models_missed", 10), ("models_missed", 26), ("failure_type", 26), ("note", 50)]
CODING_COLS = ("failure_type", "note")


def load_texts() -> dict:
    if not TEXTS.exists():
        raise SystemExit(f"{TEXTS.relative_to(ROOT)} missing; run scripts/07_secondary.py first (it writes the sampled texts)")
    with open_utf8(TEXTS) as fh:
        return {int(json.loads(line)["sample_id"]): json.loads(line) for line in fh if line.strip()}


def sheet_rows(sample: pd.DataFrame, texts: dict) -> list:
    rows = []
    for _, r in sample.iterrows():
        t = texts.get(int(r["sample_id"]))
        if t is None or t["item_id"] != r["item_id"]:
            raise SystemExit(f"sample_id {r['sample_id']}: text file does not match the CSV (re-run 07_secondary.py)")
        missed = [m for m in MODELS if r[f"pred_{m}"] != "phish"]
        is_orig = r["condition"] == "original"
        rows.append({"sample_id": int(r["sample_id"]), "set": r["set"], "stratum": r["condition"], "item_id": r["item_id"],
                     "subject": t["subject"], "original_body": t["original_body"],
                     "variant_body": "" if is_orig else t["body"],
                     "n_models_missed": len(missed), "models_missed": ", ".join(missed),
                     "failure_type": r.get("failure_type", ""), "note": r.get("note", "")})
    return rows


def build(rows: list, out) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "coding"
    head_font, head_fill = Font(bold=True), PatternFill("solid", fgColor="DDE6F2")
    code_fill = PatternFill("solid", fgColor="FFF6D5")
    for j, (name, width) in enumerate(COLUMNS, start=1):
        c = ws.cell(row=1, column=j, value=name)
        c.font, c.fill = head_font, head_fill
        c.alignment = Alignment(vertical="top", wrap_text=True)
        ws.column_dimensions[get_column_letter(j)].width = width
    wrap = Alignment(vertical="top", wrap_text=True)
    for i, r in enumerate(rows, start=2):
        for j, (name, _) in enumerate(COLUMNS, start=1):
            c = ws.cell(row=i, column=j, value=r[name])
            c.alignment = wrap
            if name in CODING_COLS:
                c.fill = code_fill
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{len(rows) + 1}"
    col_ft = get_column_letter([n for n, _ in COLUMNS].index("failure_type") + 1)
    dvs = {}
    for kind, codes in (("original", ORIGINAL_CODES), ("variant", VARIANT_CODES)):
        dv = DataValidation(type="list", formula1='"' + ",".join(codes) + '"', allow_blank=True, showDropDown=False)
        dv.error, dv.errorTitle = f"Use one code of the {kind} list (sheet 'codes').", "failure_type"
        dv.prompt, dv.promptTitle = f"{kind} item: pick one code; 'other' needs a note", "failure_type"
        ws.add_data_validation(dv)
        dvs[kind] = dv
    for i, r in enumerate(rows, start=2):
        dvs[row_type(r["stratum"])].add(f"{col_ft}{i}")

    wc = wb.create_sheet("codes")
    for j, h in enumerate(("code", "applies to", "use when"), start=1):
        c = wc.cell(row=1, column=j, value=h)
        c.font, c.fill = head_font, head_fill
    i = 2
    for kind, codes in (("original", ORIGINAL_CODES), ("variant (para_*, obf_*)", VARIANT_CODES)):
        for code, desc in codes.items():
            wc.cell(row=i, column=1, value=code)
            wc.cell(row=i, column=2, value=kind)
            wc.cell(row=i, column=3, value=desc).alignment = wrap
            i += 1
    wc.column_dimensions["A"].width, wc.column_dimensions["B"].width, wc.column_dimensions["C"].width = 26, 22, 110
    wc.freeze_panes = "A2"

    wr = wb.create_sheet("readme")
    lines = [
        "Hard-core coding sheet (docs/HARDCORE_CODING_GUIDE.md; QUESTIONS.md items 12c and 17).",
        "Fill only the two shaded columns of sheet 'coding': failure_type (drop-down; the list depends on the row: original or variant) and note (one sentence of evidence, quote a phrase; mandatory for 'other').",
        "Original rows (stratum = original): why does this spear-phishing e-mail look legitimate? Read subject and original_body.",
        "Variant rows (stratum = para_low, para_high, obf_low, obf_high): what changed relative to the original? Compare variant_body with original_body.",
        "set = preregistered (all six models wrong, phishing variants; 8 rows) or posthoc (at least 4 of 6 wrong, five strata; 30 rows). Code both in one pass; they are separated only in the report.",
        "Do not edit any other column and do not consult the models' rationales or the scores while coding.",
        "When done: python scripts/07_import_coding.py  (writes the two columns into reports/hardcore_sample.csv and the summary table).",
    ]
    for i, s in enumerate(lines, start=1):
        wr.cell(row=i, column=1, value=s).alignment = wrap
    wr.column_dimensions["A"].width = 140
    wb.save(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT.relative_to(ROOT)))
    a = ap.parse_args()
    sample = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    rows = sheet_rows(sample, load_texts())
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    build(rows, out)
    by = pd.DataFrame(rows).groupby(["set", "stratum"]).size()
    print(f"{len(rows)} rows -> {out.relative_to(ROOT)}; codes present {sum(1 for r in rows if r['failure_type'])}; "
          f"rows by set/stratum: {by.to_dict()}; code lists: original {len(ORIGINAL_CODES)}, variant {len(VARIANT_CODES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
