#!/usr/bin/env python3
"""
07_import_coding.py — read the author's filled coding workbook back into the sample file and summarise the codes
(TASK_07 section 4c; QUESTIONS.md items 12c and 17; docs/HARDCORE_CODING_GUIDE.md).

Reads reports/hardcore_coding.xlsx (sheet "coding", written by 07_coding_sheet.py and filled by hand), checks every
row against reports/hardcore_sample.csv (same sample_id and item_id), validates each code against the list for the
row's type (original or variant) and requires a note for "other", then writes ONLY the two coding columns
(failure_type, note) into reports/hardcore_sample.csv; every other byte of the file stays as it was (asserted).
It also writes reports/hardcore_coding_summary.csv (counts of each code by set and stratum, plus the number of
uncoded rows) and prints the same table. Nothing under results/ is touched; 07_secondary.py --check ignores the
two coding columns, so the re-run check stays IDENTICAL after import.

Usage: python scripts/07_import_coding.py [--xlsx reports/hardcore_coding.xlsx] [--dry-run]
"""
import argparse
import sys
import tempfile
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from common import ROOT
from scoring.hardcore_codes import NOTE_REQUIRED, codes_for, row_type
from scoring.output import write_csv

SAMPLE = ROOT / "reports" / "hardcore_sample.csv"
XLSX = ROOT / "reports" / "hardcore_coding.xlsx"
SUMMARY = ROOT / "reports" / "hardcore_coding_summary.csv"
CODING_COLS = ("failure_type", "note")


def read_sheet(path: Path) -> pd.DataFrame:
    wb = load_workbook(path, read_only=True, data_only=True)
    if "coding" not in wb.sheetnames:
        raise SystemExit(f"{path}: no sheet named 'coding'")
    rows = list(wb["coding"].iter_rows(values_only=True))
    header = [str(h) for h in rows[0]]
    df = pd.DataFrame([list(r) + [None] * (len(header) - len(r)) for r in rows[1:] if any(v not in (None, "") for v in r)],
                      columns=header)
    for c in ("sample_id", "item_id", "stratum", *CODING_COLS):
        if c not in df.columns:
            raise SystemExit(f"{path}: column {c} missing from sheet 'coding'")
    df["sample_id"] = df["sample_id"].astype(int)
    for c in CODING_COLS:
        df[c] = df[c].map(lambda v: "" if v is None or (isinstance(v, float) and v != v) else str(v).strip())
    return df


def validate(sheet: pd.DataFrame, sample: pd.DataFrame) -> list:
    """Problems as strings; empty when the workbook is consistent with the CSV and every code is allowed."""
    problems = []
    by_id = sample.set_index(sample["sample_id"].astype(int))
    if sorted(sheet["sample_id"]) != sorted(by_id.index):
        problems.append(f"sample_id set differs: sheet {len(sheet)} rows, CSV {len(by_id)} rows")
        return problems
    for _, r in sheet.iterrows():
        csv_row = by_id.loc[r["sample_id"]]
        if r["item_id"] != csv_row["item_id"]:
            problems.append(f"sample_id {r['sample_id']}: item_id differs from the CSV")
            continue
        code = r["failure_type"]
        if not code:
            continue
        allowed = codes_for(csv_row["condition"])
        if code not in allowed:
            problems.append(f"sample_id {r['sample_id']} ({row_type(csv_row['condition'])}): code {code!r} not in the "
                            f"{row_type(csv_row['condition'])} list {list(allowed)}")
        if code in NOTE_REQUIRED and not r["note"]:
            problems.append(f"sample_id {r['sample_id']}: code {code!r} needs a note")
    return problems


def merge(sheet: pd.DataFrame, sample: pd.DataFrame) -> pd.DataFrame:
    out = sample.copy()
    codes = sheet.set_index("sample_id")
    ids = out["sample_id"].astype(int)
    for c in CODING_COLS:
        out[c] = ids.map(codes[c]).fillna("").astype(str).to_numpy()
    return out


def summary(sample: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (s, cond), g in sample.groupby(["set", "condition"], sort=False):
        counts = g["failure_type"].replace("", "(uncoded)").value_counts()
        for code, n in counts.items():
            rows.append({"set": s, "stratum": cond, "type": row_type(cond), "failure_type": code, "n": int(n),
                         "n_rows_in_stratum": int(len(g)), "share": round(int(n) / len(g), 4)})
    order = {"preregistered": 0, "posthoc": 1}
    return pd.DataFrame(rows).sort_values(["set", "stratum", "n", "failure_type"], key=lambda col: col.map(order) if col.name == "set" else col,
                                          ascending=[True, True, False, True]).reset_index(drop=True)


def unchanged_outside_coding(before: pd.DataFrame, after: pd.DataFrame) -> bool:
    cols = [c for c in before.columns if c not in CODING_COLS]
    with tempfile.TemporaryDirectory() as td:
        return write_csv(before[cols], Path(td) / "a.csv") == write_csv(after[cols], Path(td) / "b.csv")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default=str(XLSX.relative_to(ROOT)))
    ap.add_argument("--dry-run", action="store_true", help="validate and print the summary; write nothing")
    a = ap.parse_args()
    sample = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    sheet = read_sheet(ROOT / a.xlsx)
    problems = validate(sheet, sample)
    if problems:
        print("\n".join(problems))
        raise SystemExit(f"{len(problems)} problem(s); nothing written")
    merged = merge(sheet, sample)
    if not unchanged_outside_coding(sample, merged):
        raise SystemExit("internal error: a column other than failure_type/note would change; nothing written")
    summ = summary(merged)
    n_coded = int((merged["failure_type"] != "").sum())
    print(summ.to_string(index=False))
    print(f"\ncoded {n_coded} of {len(merged)} rows ({(merged['failure_type'] == '').sum()} uncoded)")
    if a.dry_run:
        print("dry run: nothing written")
        return 0
    write_csv(merged, SAMPLE)
    write_csv(summ, SUMMARY)
    print(f"-> {SAMPLE.relative_to(ROOT)} (two columns updated), {SUMMARY.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
