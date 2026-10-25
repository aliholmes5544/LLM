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
    the obfuscated rows (obf_low, obf_high) with a readability drop-down (2 / 1 / 0) and a meaning
    drop-down (preserved / partly / not), plus an instructions sheet. The obfuscated rows are
    re-rated for meaning from this sheet because Excel showed the raters the first-round CSV in
    Windows-1256, which turned the Cyrillic homoglyphs into Arabic letters;
  * the same workbook carries sheets para_changed_A/B/C with the 8 paraphrases whose accepted body
    changed when thr_cos was frozen at 0.68 (PARA_CHANGED below), showing the NEW accepted body with
    a meaning drop-down only;
  * --readability merges that workbook back: readability_A/B/C and readability_majority; for the
    obfuscated rows the new meaning ratings overwrite rating_A/B/C (and rating_majority) while the
    first-round values stay in rating_A/B/C_cp1256; for the 8 changed paraphrases the new body
    replaces variant_body (old body in variant_body_prov), the current status replaces auto_outcome /
    failed_tests (provisional ones in *_prov), the first-round ratings of the superseded body move to
    rating_A/B/C_prov, and the three variants outside the first-round sample are appended as rows.
    Without --readability the script rebuilds the first-round state (57 rows); with it, the final one.

The CSV is re-read after writing and verified to be strict UTF-8 without mojibake markers.
Report: reports/ratings_merge_dev.json.

Usage:  python scripts/05a_merge_ratings.py [--readability] [--make-readability-sheet [--force]]
"""
import argparse
import csv
import json
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
COLUMNS = ["variant_id", "condition", "auto_outcome", "failed_tests", "auto_outcome_prov", "failed_tests_prov",
           "original_body", "variant_body", "variant_body_prov",
           "rating_A", "rating_B", "rating_C", "rating_majority",
           "rating_A_prov", "rating_B_prov", "rating_C_prov",
           "rating_A_cp1256", "rating_B_cp1256", "rating_C_cp1256",
           "readability_A", "readability_B", "readability_C", "readability_majority",
           "notes_A", "notes_B", "notes_C"]
# Paraphrase variants whose accepted body changed when thr_cos was frozen at 0.68 (dev re-run of
# 2026-10-25, docs/CHANGES_FOR_THESIS.md): under the provisional 0.80 their first attempt failed the
# cosine test alone and was regenerated; under 0.68 the first attempt is kept. Their body in
# data/processed/variants_dev.jsonl is therefore not the body the raters saw. They are re-rated for
# meaning from the "para_changed_*" sheets; value = (status, failed tests) in the provisional run.
PARA_CHANGED = {
    "eph:12308#para_low": ("excluded", "cosine"), "eph:16367#para_low": ("regenerated", ""),
    "eph:11434#para_high": ("regenerated", ""), "eph:12308#para_high": ("excluded", "cosine"),
    "eph:14108#para_high": ("regenerated", ""), "eph:15264#para_high": ("regenerated", ""),
    "eph:16367#para_high": ("regenerated", ""), "eph:4123#para_high": ("regenerated", ""),
}
PARA_SHEET = "para_changed_{}"
VARIANTS_JSONL = ROOT / "data" / "processed" / "variants_dev.jsonl"
RECORDS_JSONL = ROOT / "data" / "processed" / "records.jsonl"
READABILITY_INSTRUCTIONS = [
    ("Readability and meaning rating of obfuscated variants (Section 3.2.3)", True),
    ("", False),
    ("Each sheet A, B, C is for one rater. Rate only your own sheet. The 20 rows are the obfuscated "
     "variants (obf_low, obf_high) of the development sample; original_body is the untouched email, "
     "variant_body the obfuscated one. This workbook shows the text exactly as stored (the first-round "
     "file was displayed by Excel in the wrong code page, so these rows are rated again here).", False),
    ("", False),
    ("Step 1, readability: read variant_body as a recipient would, without the original, and choose one "
     "value in the readability column (drop-down):", True),
    ("2 = reads normally: nothing stands out, every word is read without effort.", False),
    ("1 = noticeably odd but every word readable: spelling, spacing or characters look wrong in places, "
     "yet every word can still be recognised.", False),
    ("0 = at least one word unrecognisable: at least one word cannot be read at all.", False),
    ("", False),
    ("Step 2, meaning: compare variant_body with original_body and choose one value in the meaning column "
     "(drop-down), using the same scale as in the first round:", True),
    ("preserved = the variant conveys the same information and the same request as the original.", False),
    ("partly = some information is changed, lost or added, but the main request is still the same.", False),
    ("not = the main request or a key fact (who, what, when, how much, where to act) is changed or missing.", False),
    ("", False),
    ("Sheets para_changed_A / _B / _C: 8 paraphrased variants whose accepted text changed when the "
     "similarity threshold was fixed (the text you rated in the first round was a different rewrite of the "
     "same email). Rate the meaning of the NEW variant_body against original_body with the same scale. "
     "These rows have no readability column.", True),
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
            raise SystemExit(f"workbook {rater}: variant_ids differ from the first-round sample "
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
        unrated = [r["variant_id"] for r in rows if r.get("readability", "") == "" or r.get("meaning", "") == ""]
        if unrated:
            raise SystemExit(f"readability sheet {rater}: {len(unrated)} rows missing readability or meaning, e.g. {unrated[:3]}")
        bad = [(r["variant_id"], r["readability"]) for r in rows if r["readability"] not in READABILITY_LABELS]
        if bad:
            raise SystemExit(f"readability sheet {rater}: readability must be one of {READABILITY_LABELS}; offending: {bad[:5]}")
        bad = [(r["variant_id"], r["meaning"]) for r in rows if r["meaning"].lower() not in MEANING_LABELS]
        if bad:
            raise SystemExit(f"readability sheet {rater}: meaning must be one of {MEANING_LABELS}; offending: {bad[:5]}")
        scores[rater] = {r["variant_id"]: {"readability": r["readability"], "meaning": r["meaning"].lower()} for r in rows}
        report[rater] = {"rows": len(rows), "cells_mojibake_repaired": fixed,
                         "readability": dict(Counter(v["readability"] for v in scores[rater].values())),
                         "meaning": dict(Counter(v["meaning"] for v in scores[rater].values()))}
        # paraphrases whose accepted body changed: meaning only
        name = PARA_SHEET.format(rater)
        if name not in wb.sheetnames:
            raise SystemExit(f"{READABILITY_XLSX.name}: sheet {name} missing")
        prow, pfixed = read_sheet(wb[name])
        if sorted(r["variant_id"] for r in prow) != sorted(PARA_CHANGED):
            raise SystemExit(f"sheet {name}: variant_ids differ from the {len(PARA_CHANGED)} changed paraphrases")
        unrated = [r["variant_id"] for r in prow if r.get("meaning", "") == ""]
        if unrated:
            raise SystemExit(f"sheet {name}: {len(unrated)} rows not rated yet, e.g. {unrated[:3]}")
        bad = [(r["variant_id"], r["meaning"]) for r in prow if r["meaning"].lower() not in MEANING_LABELS]
        if bad:
            raise SystemExit(f"sheet {name}: meaning must be one of {MEANING_LABELS}; offending: {bad[:5]}")
        for r in prow:
            scores[rater][r["variant_id"]] = {"meaning": r["meaning"].lower(), "body": r["variant_body"]}
        report[rater]["para_changed"] = {"rows": len(prow), "cells_mojibake_repaired": pfixed,
                                         "meaning": dict(Counter(r["meaning"].lower() for r in prow))}
    wb.close()
    return scores, report


# ---- readability sheet ------------------------------------------------------------
def make_readability_sheet(sample: list, force: bool) -> dict:
    """One sheet per rater with the obfuscated rows only and a 2/1/0 drop-down (TASK_05 readability)."""
    import openpyxl
    from openpyxl.styles import Alignment, Font
    from openpyxl.worksheet.datavalidation import DataValidation

    if READABILITY_XLSX.exists():
        if not force:
            raise SystemExit(f"{READABILITY_XLSX.relative_to(ROOT)} exists; use --force to overwrite it")
        old = openpyxl.load_workbook(READABILITY_XLSX, read_only=True)
        filled = sum(1 for ws in old.worksheets if ws.title != "Instructions"
                     for row in ws.iter_rows(min_row=2, min_col=6, values_only=True) for c in row if c is not None)
        old.close()
        if filled:
            raise SystemExit(f"{READABILITY_XLSX.relative_to(ROOT)} already holds {filled} rating cells; not overwritten")
    obf = [r for r in sample if r["condition"] in OBF_CONDITIONS]
    changed = para_changed_rows(sample)
    widths = {"A": 6, "B": 24, "C": 11, "D": 70, "E": 70, "F": 13, "G": 13}
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Instructions"
    ws.column_dimensions["A"].width = 110
    for i, (line, bold) in enumerate(READABILITY_INSTRUCTIONS, start=1):
        c = ws.cell(row=i, column=1, value=line)
        c.font = Font(bold=bold)
        c.alignment = Alignment(wrap_text=True, vertical="top")

    def block(title: str, rows: list, header: list, validations: dict) -> None:
        ws = wb.create_sheet(title)
        ws.append(header)
        for c in ws[1]:
            c.font = Font(bold=True)
        for n, r in enumerate(rows, start=1):
            ws.append([n, r["variant_id"], r["condition"], r["original_body"], r["variant_body"]] + [None] * (len(header) - 5))
        for col, w in widths.items():
            ws.column_dimensions[col].width = w
        for row in ws.iter_rows(min_row=2, max_row=len(rows) + 1):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        for col, (name, options) in validations.items():
            dv = DataValidation(type="list", formula1=f'"{",".join(options)}"', allow_blank=True, showErrorMessage=True,
                                errorTitle=name, error=f"Enter one of {', '.join(options)} (see the Instructions sheet)")
            ws.add_data_validation(dv)
            dv.add(f"{col}2:{col}{len(rows) + 1}")
        ws.freeze_panes = "A2"

    base = ["row", "variant_id", "condition", "original_body", "variant_body"]
    for rater in RATERS:
        block(rater, obf, base + ["readability", "meaning"],
              {"F": ("readability", READABILITY_LABELS), "G": ("meaning", MEANING_LABELS)})
    for rater in RATERS:
        block(PARA_SHEET.format(rater), changed, base + ["meaning"], {"F": ("meaning", MEANING_LABELS)})
    wb.save(READABILITY_XLSX)
    return {"file": str(READABILITY_XLSX.relative_to(ROOT)),
            "sheets": ["Instructions", *RATERS, *(PARA_SHEET.format(r) for r in RATERS)],
            "obfuscation_rows_per_sheet": len(obf), "conditions": dict(Counter(r["condition"] for r in obf)),
            "para_changed_rows_per_sheet": len(changed), "para_changed_ids": [r["variant_id"] for r in changed],
            "scale": {"readability": {"2": "reads normally", "1": "noticeably odd but every word readable",
                                      "0": "at least one word unrecognisable"},
                      "meaning": list(MEANING_LABELS)}}


def load_current_variants() -> dict:
    """Current accepted body and status per variant (data/processed/variants_dev.jsonl), plus source bodies."""
    variants = {}
    for line in open_utf8(VARIANTS_JSONL):
        v = json.loads(line)
        variants[v["variant_id"]] = {"source_id": v["source_id"], "condition": v["condition"], "body": v["body"],
                                     "status": v["status"], "failed_tests": "+".join(v["checks"].get("failed_tests", []))}
    need = {v["source_id"] for k, v in variants.items() if k in PARA_CHANGED}
    for line in open_utf8(RECORDS_JSONL):
        r = json.loads(line)
        if r["id"] in need:
            for v in variants.values():
                if v["source_id"] == r["id"]:
                    v["original_body"] = r["body"]
    return variants


def para_changed_rows(sample: list) -> list:
    """The PARA_CHANGED variants with their NEW accepted body, in condition order; checks that each is
    accepted now and that the body differs from the rated one where the variant is in the sample."""
    cur = load_current_variants()
    by_vid = {r["variant_id"]: r for r in sample}
    rows = []
    for vid in PARA_CHANGED:
        v = cur.get(vid)
        if v is None or v["status"] == "excluded":
            raise SystemExit(f"{vid}: not an accepted variant in {VARIANTS_JSONL.name} (status {v and v['status']})")
        if vid in by_vid and by_vid[vid]["variant_body"].strip() == v["body"].strip():
            raise SystemExit(f"{vid}: body in the sample equals the current body; it is not a changed variant")
        rows.append({"variant_id": vid, "condition": v["condition"], "original_body": v["original_body"],
                     "variant_body": v["body"], "auto_outcome": v["status"], "failed_tests": v["failed_tests"]})
    order = {c: i for i, c in enumerate(("para_low", "para_high"))}
    rows.sort(key=lambda r: (order[r["condition"]], r["variant_id"]))
    return rows


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
    # rows appended by an earlier --readability merge (changed paraphrases outside the first-round
    # sample) are rebuilt below from the current variants, so the first-round state is restored first
    appended = [r["variant_id"] for r in sample
                if r["variant_id"] in PARA_CHANGED and r["auto_outcome_prov"] and r["variant_body_prov"] == ""]
    sample = [r for r in sample if r["variant_id"] not in appended]
    for r in sample:                     # superseded body and provisional outcome back in place
        if r["variant_body_prov"]:
            r.update({"variant_body": r["variant_body_prov"], "auto_outcome": r["auto_outcome_prov"],
                      "failed_tests": r["failed_tests_prov"]})
    report = {"n_sample": len(sample), "meaning": {}, "readability": {}}
    ratings, notes, report["meaning"]["workbooks"] = load_meaning_workbooks(sample)
    for r in sample:
        vid = r["variant_id"]
        for rater in RATERS:
            r[f"rating_{rater}"] = ratings[rater][vid]
            r[f"notes_{rater}"] = notes[rater][vid]
            r[f"rating_{rater}_prov"] = ""
        r["rating_majority"] = majority([r[f"rating_{x}"] for x in RATERS])
        for col in ("auto_outcome_prov", "failed_tests_prov", "variant_body_prov"):
            r[col] = ""
        obf = r["condition"] in OBF_CONDITIONS
        for rater in RATERS:
            # first-round meaning rating of the obfuscated rows, made on text Excel showed in cp1256
            r[f"rating_{rater}_cp1256"] = ratings[rater][vid] if obf else "n/a"
            r[f"readability_{rater}"] = "" if obf else "n/a"      # filled only by --readability
        r["readability_majority"] = "" if obf else "n/a"
    report["meaning"]["majority"] = dict(Counter(r["rating_majority"] for r in sample))
    report["meaning"]["majority_by_condition"] = {
        c: dict(Counter(r["rating_majority"] for r in sample if r["condition"] == c))
        for c in sorted({r["condition"] for r in sample})}
    report["meaning"]["unanimous"] = sum(len({r[f"rating_{x}"] for x in RATERS}) == 1 for r in sample)
    report["meaning"]["split"] = [r["variant_id"] for r in sample if r["rating_majority"] == "split"]

    if args.readability:
        scores, report["readability"]["sheets"] = load_readability_workbook(sample)
        changed = Counter()
        for r in sample:
            if r["condition"] in OBF_CONDITIONS:
                for rater in RATERS:
                    s = scores[rater][r["variant_id"]]
                    r[f"readability_{rater}"] = s["readability"]
                    r[f"rating_{rater}"] = s["meaning"]            # clean-text re-rating replaces the cp1256 one
                    changed[rater] += s["meaning"] != r[f"rating_{rater}_cp1256"]
                r["readability_majority"] = majority([r[f"readability_{x}"] for x in RATERS])
                r["rating_majority"] = majority([r[f"rating_{x}"] for x in RATERS])
        # paraphrases whose accepted body changed under the frozen thr_cos: the new body replaces the
        # rated one, the first-round ratings (of the superseded attempt-1 body) move to rating_*_prov
        by_vid = {r["variant_id"]: r for r in sample}
        changed_rows, moved, added = para_changed_rows(sample), [], []
        for new in changed_rows:
            vid = new["variant_id"]
            prov_status, prov_failed = PARA_CHANGED[vid]
            r = by_vid.get(vid)
            if r is None:
                r = {c: "" for c in COLUMNS}
                r.update({"variant_id": vid, "condition": new["condition"], "original_body": new["original_body"],
                          "rating_majority": "", "readability_majority": "n/a"})
                for x in RATERS:
                    r[f"readability_{x}"] = "n/a"
                    r[f"rating_{x}_cp1256"] = "n/a"
                sample.append(r); added.append(vid)
            else:
                if r["auto_outcome"] != prov_status or r["failed_tests"] != prov_failed:
                    raise SystemExit(f"{vid}: sample row outcome {r['auto_outcome']}/{r['failed_tests']} differs from "
                                     f"the recorded provisional outcome {prov_status}/{prov_failed}")
                r["variant_body_prov"] = r["variant_body"]
                for x in RATERS:
                    r[f"rating_{x}_prov"] = r[f"rating_{x}"]
                moved.append(vid)
            r.update({"auto_outcome": new["auto_outcome"], "failed_tests": new["failed_tests"],
                      "auto_outcome_prov": prov_status, "failed_tests_prov": prov_failed, "variant_body": new["variant_body"]})
            for x in RATERS:
                s = scores[x][vid]
                if s["body"].replace("\r\n", "\n").strip() != new["variant_body"].strip():
                    raise SystemExit(f"sheet {PARA_SHEET.format(x)}: body of {vid} differs from the current accepted body")
                r[f"rating_{x}"] = s["meaning"]
            r["rating_majority"] = majority([r[f"rating_{x}"] for x in RATERS])
        order = {c: i for i, c in enumerate(("para_low", "para_high", "obf_low", "obf_high"))}
        sample.sort(key=lambda r: (order[r["condition"]], r["variant_id"]))
        report["n_sample"] = len(sample)
        report["readability"]["para_changed_rerated"] = {
            "rows": len(changed_rows), "ratings_moved_to_prov": moved, "rows_added": added,
            "majority": {r["variant_id"]: r["rating_majority"] for r in sample if r["variant_id"] in PARA_CHANGED},
            "majority_prov": {v: majority([by_vid[v][f"rating_{x}_prov"] for x in RATERS]) for v in moved}}
        obf_rows = [r for r in sample if r["condition"] in OBF_CONDITIONS]
        report["readability"]["majority"] = dict(Counter(r["readability_majority"] for r in obf_rows))
        report["readability"]["majority_by_condition"] = {
            c: dict(Counter(r["readability_majority"] for r in obf_rows if r["condition"] == c)) for c in OBF_CONDITIONS}
        report["readability"]["meaning_rerated"] = {
            "rows": len(obf_rows), "ratings_changed_vs_cp1256": dict(changed),
            "majority": dict(Counter(r["rating_majority"] for r in obf_rows)),
            "majority_cp1256": dict(Counter(majority([r[f"rating_{x}_cp1256"] for x in RATERS]) for r in obf_rows))}
        report["meaning"]["majority"] = dict(Counter(r["rating_majority"] for r in sample))
        report["meaning"]["majority_by_condition"] = {
            c: dict(Counter(r["rating_majority"] for r in sample if r["condition"] == c))
            for c in sorted({r["condition"] for r in sample})}
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
        print(f"readability majority: {report['readability']['majority']}  "
              f"meaning re-rated on obfuscated rows: {report['readability']['meaning_rerated']}")
        pc = report["readability"]["para_changed_rerated"]
        print(f"changed paraphrases re-rated: {pc['rows']} (moved to _prov {len(pc['ratings_moved_to_prov'])}, "
              f"rows added {pc['rows_added']})  majority {pc['majority']}  prov {pc['majority_prov']}")
    else:
        print("readability: pending")
    if args.make_readability_sheet:
        s = report["readability"]["sheet_written"]
        print(f"readability sheet: {s['file']}  sheets {s['sheets']}  ({s['obfuscation_rows_per_sheet']} obfuscated rows, "
              f"{s['para_changed_rows_per_sheet']} changed paraphrases)")
    c = report["csv"]
    print(f"CSV: {c['file']}  utf-8 strict OK, BOM {c['has_bom']}, mojibake markers {c['mojibake_markers']}, "
          f"{'CLEAN' if c['clean'] else 'NOT CLEAN'}")
    print("written to reports/ratings_merge_dev.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
