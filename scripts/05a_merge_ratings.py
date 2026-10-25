#!/usr/bin/env python3
"""
05a_merge_ratings.py — merge the raters' workbooks into the manual-review sample (Section 3.2.3).

Three raters (A, B, C) each returned a copy of reports/manual_review_sample_dev.csv as an Excel
workbook with their meaning rating (preserved | partly | not) in whichever rating_* column they
used, plus free-text notes. This script

  * reads reports/ratings/{A,B,C}.xlsx as UTF-8, repairs the cp1252 mojibake that Excel introduced
    when it opened the UTF-8 CSV (e.g. "â€™" -> "’"), checks that every workbook holds exactly the
    sampled variant_ids, and copies each rater's labels and notes into rating_A/B/C and
    notes_A/B/C of the CSV; all other columns are kept from the CSV (the text columns on disk were
    never mojibaked; the repaired workbook text is checked against them);
  * adds rating_majority: the label given by at least two raters, or "split" when all three differ;
  * --make-readability-sheet writes reports/readability_dev.xlsx: one sheet per rater holding only
    the obfuscated rows (obf_low, obf_high) with a 2 / 1 / 0 drop-down, plus an instructions sheet;
  * --readability merges that workbook back as readability_A/B/C and readability_majority.

The CSV is re-read after writing and verified to be strict UTF-8 without mojibake markers.
Report: reports/ratings_merge_dev.json.

Usage:  python scripts/05a_merge_ratings.py [--readability] [--make-readability-sheet [--force]]
"""
import argparse
import csv
import sys
from collections import Counter

from common import ROOT, open_utf8, write_json

REPORTS = ROOT / "reports"
SAMPLE_CSV = REPORTS / "manual_review_sample_dev.csv"
RATINGS_DIR = REPORTS / "ratings"
READABILITY_XLSX = REPORTS / "readability_dev.xlsx"
RATERS = ("A", "B", "C")
MEANING_LABELS = ("preserved", "partly", "not")
READABILITY_LABELS = ("2", "1", "0")
OBF_CONDITIONS = ("obf_low", "obf_high")
# lead bytes 0xC3/0xD0/0xD1/0xE2 of UTF-8 as shown by cp1252 ("Ã", "Ð", "Ñ", "â") and cp1256 ("أ", "ذ", "ر", "â")
MOJIBAKE_MARKERS = ("â€", "Ã", "Â", "Ð", "Ñ", "أ", "ذ", "ر")
COLUMNS = ["variant_id", "condition", "auto_outcome", "failed_tests", "original_body", "variant_body",
           "rating_A", "rating_B", "rating_C", "rating_majority",
           "readability_A", "readability_B", "readability_C", "readability_majority",
           "notes_A", "notes_B", "notes_C"]
READABILITY_INSTRUCTIONS = [
    ("Readability rating of obfuscated variants (Section 3.2.3)", True),
    ("", False),
    ("Each sheet A, B, C is for one rater. Rate only your own sheet. The 20 rows are the obfuscated "
     "variants (obf_low, obf_high) of the development sample; original_body is the untouched email, "
     "variant_body the obfuscated one. Read variant_body as a recipient would, without the original.", False),
    ("", False),
    ("Choose one value in the readability column (drop-down):", True),
    ("2 = reads normally: nothing stands out, every word is read without effort.", False),
    ("1 = noticeably odd but every word readable: spelling, spacing or characters look wrong in places, "
     "yet every word can still be recognised.", False),
    ("0 = at least one word unrecognisable: at least one word cannot be read at all.", False),
    ("", False),
    ("Do not edit any other column. Do not correct the text. Save the workbook under the same name.", False),
]


# ---- mojibake repair -----------------------------------------------------------
# Excel opened the UTF-8 CSV in the system ANSI code page. On the raters' machines that was
# Windows-1256 (Arabic): "Müller" showed as "Mأ¼ller" and the Cyrillic homoglyphs of the obfuscated
# rows as Arabic letters. cp1252 is tried second for workbooks produced on a Western locale.
CODEPAGES = ("cp1256", "cp1252")


def _ansi_bytes(s: str, codepage: str) -> bytes:
    """Encode in a single-byte code page, mapping the code points the codec leaves undefined
    (e.g. U+0081 in cp1252) to the same byte value, as Excel does when it reads them."""
    out = bytearray()
    for ch in s:
        try:
            out += ch.encode(codepage)
        except UnicodeEncodeError:
            if ord(ch) < 256:
                out.append(ord(ch))
            else:
                raise
    return bytes(out)


def demojibake(value):
    """Undo UTF-8 text that was decoded in an ANSI code page: returns the repaired string for the first
    code page under which the cell round-trips to valid UTF-8, otherwise the cell unchanged (plain
    ASCII and text the rater typed are left as they are)."""
    if not isinstance(value, str) or not any(m in value for m in MOJIBAKE_MARKERS):
        return value
    for cp in CODEPAGES:
        try:
            return _ansi_bytes(value, cp).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return value


def majority(values: list) -> str:
    """Label given by at least two of the three raters; 'split' if all differ; '' if any is blank."""
    if any(v == "" for v in values):
        return ""
    top, n = Counter(values).most_common(1)[0]
    return top if n >= 2 else "split"


# ---- workbooks --------------------------------------------------------------------
def read_sheet(ws) -> tuple:
    """Rows of a worksheet as dicts keyed by the header row, every string cell mojibake-repaired.
    Returns (rows, n_cells_repaired)."""
    rows, fixed = [], 0
    it = ws.iter_rows(values_only=True)
    header = [str(h).strip() if h is not None else "" for h in next(it)]
    for raw in it:
        if all(c is None for c in raw):
            continue
        rec, garbled = {}, 0
        for h, c in zip(header, raw):
            if c is None:
                c = ""
            elif isinstance(c, float) and c.is_integer():
                c = str(int(c))
            else:
                c = str(c)
            repaired = demojibake(c)
            fixed += repaired != c
            garbled += repaired != c
            rec[h] = repaired.strip()
        rec["_garbled_cells"] = garbled        # cells the rater saw mis-decoded in Excel
        rows.append(rec)
    return rows, fixed


def rater_column(rows: list, prefix: str, rater: str) -> str:
    """The single `<prefix>_*` column a rater filled in (raters used rating_A or rating_B)."""
    cands = {h for h in rows[0] if h.startswith(prefix + "_")}
    filled = [h for h in sorted(cands) if any(r.get(h, "") not in ("", "n/a") for r in rows)]
    if len(filled) != 1:
        raise SystemExit(f"workbook {rater}: expected exactly one filled {prefix}_* column, found {filled}")
    return filled[0]


def load_meaning_workbooks(sample: list) -> tuple:
    """Rating and notes per rater keyed by variant_id, plus the per-workbook check report."""
    import openpyxl
    ids = [r["variant_id"] for r in sample]
    text = {r["variant_id"]: (r["original_body"].strip(), r["variant_body"].strip()) for r in sample}
    ratings, notes, report = {}, {}, {}
    for rater in RATERS:
        path = RATINGS_DIR / f"{rater}.xlsx"
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        rows, fixed = read_sheet(wb.worksheets[0])
        sheet = wb.sheetnames[0]
        wb.close()
        got = [r["variant_id"] for r in rows]
        if sorted(got) != sorted(ids) or len(got) != len(set(got)):
            raise SystemExit(f"workbook {rater}: variant_ids differ from the sample "
                             f"(missing {sorted(set(ids) - set(got))[:3]}, extra {sorted(set(got) - set(ids))[:3]})")
        col = rater_column(rows, "rating", rater)
        bad = [(r["variant_id"], r[col]) for r in rows if r[col].lower() not in MEANING_LABELS]
        if bad:
            raise SystemExit(f"workbook {rater}: ratings must be one of {MEANING_LABELS}; offending: {bad[:5]}")
        mismatch = [r["variant_id"] for r in rows
                    if (r["original_body"].replace("\r\n", "\n"), r["variant_body"].replace("\r\n", "\n"))
                    != text[r["variant_id"]]]
        ratings[rater] = {r["variant_id"]: r[col].lower() for r in rows}
        notes[rater] = {r["variant_id"]: r.get("notes", "") for r in rows}
        garbled = [r for r in rows if r["_garbled_cells"]]
        report[rater] = {"file": str(path.relative_to(ROOT)), "sheet": sheet, "rating_column": col,
                         "rows": len(rows), "cells_mojibake_repaired": fixed,
                         "text_cells_differing_from_csv": len(mismatch), "same_row_order": got == ids,
                         "rows_shown_garbled_in_excel": {"n": len(garbled),
                                                         "by_condition": dict(Counter(r["condition"] for r in garbled)),
                                                         "variant_ids": [r["variant_id"] for r in garbled]},
                         "labels": dict(Counter(ratings[rater].values())),
                         "n_notes": sum(bool(v) for v in notes[rater].values())}
    return ratings, notes, report


def load_readability_workbook(sample: list) -> tuple:
    import openpyxl
    obf_ids = [r["variant_id"] for r in sample if r["condition"] in OBF_CONDITIONS]
    wb = openpyxl.load_workbook(READABILITY_XLSX, read_only=True, data_only=True)
    scores, report = {}, {}
    for rater in RATERS:
        if rater not in wb.sheetnames:
            raise SystemExit(f"{READABILITY_XLSX.name}: sheet {rater} missing")
        rows, fixed = read_sheet(wb[rater])
        got = [r["variant_id"] for r in rows]
        if sorted(got) != sorted(obf_ids):
            raise SystemExit(f"readability sheet {rater}: variant_ids differ from the obfuscated sample rows")
        unrated = [r["variant_id"] for r in rows if r.get("readability", "") == ""]
        if unrated:
            raise SystemExit(f"readability sheet {rater}: {len(unrated)} rows not rated yet, e.g. {unrated[:3]}")
        bad = [(r["variant_id"], r["readability"]) for r in rows if r["readability"] not in READABILITY_LABELS]
        if bad:
            raise SystemExit(f"readability sheet {rater}: values must be one of {READABILITY_LABELS}; offending: {bad[:5]}")
        scores[rater] = {r["variant_id"]: r["readability"] for r in rows}
        report[rater] = {"rows": len(rows), "cells_mojibake_repaired": fixed,
                         "labels": dict(Counter(scores[rater].values()))}
    wb.close()
    return scores, report


# ---- readability sheet ------------------------------------------------------------
def make_readability_sheet(sample: list, force: bool) -> dict:
    """One sheet per rater with the obfuscated rows only and a 2/1/0 drop-down (TASK_05 readability)."""
    import openpyxl
    from openpyxl.styles import Alignment, Font
    from openpyxl.worksheet.datavalidation import DataValidation

    if READABILITY_XLSX.exists() and not force:
        raise SystemExit(f"{READABILITY_XLSX.relative_to(ROOT)} exists; use --force to overwrite it")
    obf = [r for r in sample if r["condition"] in OBF_CONDITIONS]
    header = ["row", "variant_id", "condition", "original_body", "variant_body", "readability"]
    widths = {"A": 6, "B": 24, "C": 11, "D": 70, "E": 70, "F": 13}
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Instructions"
    ws.column_dimensions["A"].width = 110
    for i, (line, bold) in enumerate(READABILITY_INSTRUCTIONS, start=1):
        c = ws.cell(row=i, column=1, value=line)
        c.font = Font(bold=bold)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    for rater in RATERS:
        ws = wb.create_sheet(rater)
        ws.append(header)
        for c in ws[1]:
            c.font = Font(bold=True)
        for n, r in enumerate(obf, start=1):
            ws.append([n, r["variant_id"], r["condition"], r["original_body"], r["variant_body"], None])
        for col, w in widths.items():
            ws.column_dimensions[col].width = w
        for row in ws.iter_rows(min_row=2, max_row=len(obf) + 1):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        dv = DataValidation(type="list", formula1='"2,1,0"', allow_blank=True, showErrorMessage=True,
                            errorTitle="readability", error="Enter 2, 1 or 0 (see the Instructions sheet)")
        ws.add_data_validation(dv)
        dv.add(f"F2:F{len(obf) + 1}")
        ws.freeze_panes = "A2"
    wb.save(READABILITY_XLSX)
    return {"file": str(READABILITY_XLSX.relative_to(ROOT)), "sheets": ["Instructions", *RATERS],
            "rows_per_sheet": len(obf), "conditions": dict(Counter(r["condition"] for r in obf)),
            "columns": header, "scale": {"2": "reads normally", "1": "noticeably odd but every word readable",
                                         "0": "at least one word unrecognisable"}}


# ---- CSV ------------------------------------------------------------------------------
def load_sample() -> list:
    with open_utf8(SAMPLE_CSV) as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:                       # accept both the two-rater layout written by 05 and the merged one
        for col in COLUMNS:
            r.setdefault(col, "")
    return rows


def write_sample(rows: list) -> dict:
    with open_utf8(SAMPLE_CSV, "w") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    raw = SAMPLE_CSV.read_bytes()
    text = raw.decode("utf-8")           # strict: raises on any invalid byte
    markers = {m: text.count(m) for m in MOJIBAKE_MARKERS}
    return {"file": str(SAMPLE_CSV.relative_to(ROOT)), "bytes": len(raw), "utf8_strict": True,
            "has_bom": raw.startswith(b"\xef\xbb\xbf"), "mojibake_markers": markers,
            "non_ascii_chars": sum(ord(ch) > 127 for ch in text), "clean": not any(markers.values())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--readability", action="store_true", help="also merge reports/readability_dev.xlsx")
    ap.add_argument("--make-readability-sheet", action="store_true", help="write reports/readability_dev.xlsx")
    ap.add_argument("--force", action="store_true", help="overwrite an existing readability workbook")
    args = ap.parse_args()

    sample = load_sample()
    report = {"n_sample": len(sample), "meaning": {}, "readability": {}}
    ratings, notes, report["meaning"]["workbooks"] = load_meaning_workbooks(sample)
    for r in sample:
        vid = r["variant_id"]
        for rater in RATERS:
            r[f"rating_{rater}"] = ratings[rater][vid]
            r[f"notes_{rater}"] = notes[rater][vid]
        r["rating_majority"] = majority([r[f"rating_{x}"] for x in RATERS])
        obf = r["condition"] in OBF_CONDITIONS
        for rater in RATERS:
            if not obf:
                r[f"readability_{rater}"] = "n/a"
            elif r[f"readability_{rater}"] == "n/a":
                r[f"readability_{rater}"] = ""
        r["readability_majority"] = "" if obf else "n/a"
    report["meaning"]["majority"] = dict(Counter(r["rating_majority"] for r in sample))
    report["meaning"]["majority_by_condition"] = {
        c: dict(Counter(r["rating_majority"] for r in sample if r["condition"] == c))
        for c in sorted({r["condition"] for r in sample})}
    report["meaning"]["unanimous"] = sum(len({r[f"rating_{x}"] for x in RATERS}) == 1 for r in sample)
    report["meaning"]["split"] = [r["variant_id"] for r in sample if r["rating_majority"] == "split"]

    if args.readability:
        scores, report["readability"]["sheets"] = load_readability_workbook(sample)
        for r in sample:
            if r["condition"] in OBF_CONDITIONS:
                for rater in RATERS:
                    r[f"readability_{rater}"] = scores[rater][r["variant_id"]]
                r["readability_majority"] = majority([r[f"readability_{x}"] for x in RATERS])
        obf_rows = [r for r in sample if r["condition"] in OBF_CONDITIONS]
        report["readability"]["majority"] = dict(Counter(r["readability_majority"] for r in obf_rows))
        report["readability"]["majority_by_condition"] = {
            c: dict(Counter(r["readability_majority"] for r in obf_rows if r["condition"] == c)) for c in OBF_CONDITIONS}
    else:
        report["readability"]["status"] = "pending (run with --readability once reports/readability_dev.xlsx is rated)"

    report["csv"] = write_sample(sample)
    if args.make_readability_sheet:
        report["readability"]["sheet_written"] = make_readability_sheet(sample, args.force)
    write_json(REPORTS / "ratings_merge_dev.json", report)

    for rater, s in report["meaning"]["workbooks"].items():
        g = s["rows_shown_garbled_in_excel"]
        print(f"rater {rater}: {s['rating_column']:8s} {s['labels']}  notes {s['n_notes']}  "
              f"mojibake cells repaired {s['cells_mojibake_repaired']}  text mismatches vs CSV {s['text_cells_differing_from_csv']}  "
              f"rows shown garbled {g['n']} {g['by_condition']}")
    print(f"majority: {report['meaning']['majority']}  unanimous {report['meaning']['unanimous']}/{len(sample)}")
    for c, d in report["meaning"]["majority_by_condition"].items():
        print(f"  {c:10s} {d}")
    if args.readability:
        print(f"readability majority: {report['readability']['majority']}")
    else:
        print("readability: pending")
    if args.make_readability_sheet:
        s = report["readability"]["sheet_written"]
        print(f"readability sheet: {s['file']} ({s['rows_per_sheet']} rows x sheets {s['sheets']})")
    c = report["csv"]
    print(f"CSV: {c['file']}  utf-8 strict OK, BOM {c['has_bom']}, mojibake markers {c['mojibake_markers']}, "
          f"{'CLEAN' if c['clean'] else 'NOT CLEAN'}")
    print("written to reports/ratings_merge_dev.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
