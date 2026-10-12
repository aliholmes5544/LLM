#!/usr/bin/env python3
"""
02_audit_raw.py — verify counts, fields and labels in the raw sources.

Produces every raw figure quoted in Section 3.2 so that the section can be
checked against the data rather than against prose. Nothing is modified.

Usage:  python scripts/02_audit_raw.py
Output: reports/audit_raw.json  and a console summary
"""
import json
import re
import sys
from collections import Counter

from common import ROOT, load_config, read_text, write_json, GREETING_RE, GENERIC

CFG = load_config()
RAW = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"

HTML_RE = re.compile(r"<\s*(html|body|p|br|div|a|span|table|td|tr|ul|li)\b", re.I)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
PLACEHOLDER_RE = re.compile(r"<<[^>]*>>")


def flatten(body: str) -> str:
    return WS_RE.sub(" ", TAG_RE.sub(" ", body or "")).strip().lower()


def salutation_class(body: str) -> str:
    m = GREETING_RE.match(flatten(body))
    if not m:
        return "none"
    name = m.group(1).strip().lower()
    return "generic" if any(name == g or name.startswith(g + " ") for g in GENERIC) else "named"


def audit_nahmias() -> dict:
    base = RAW / "nahmias" / CFG["sources"]["nahmias"]["subdir"]
    out = {}
    for folder in sorted(p for p in base.iterdir() if p.is_dir()):
        files = sorted(folder.glob("*.json"))
        keys, html, bad, no_subject = Counter(), 0, [], 0
        bodies, words = [], []
        for f in files:
            try:
                o = json.loads(read_text(f, errors="replace"))
            except Exception:
                bad.append(f.name)
                continue
            keys.update(o.keys())
            body = str(o.get("email_body") or o.get("body") or "")
            if HTML_RE.search(body):
                html += 1
            flat = flatten(body)
            bodies.append(flat)
            words.append(len(flat.split()))
            if not str(o.get("email_subject") or o.get("subject") or "").strip():
                no_subject += 1
        words_sorted = sorted(words)
        out[folder.name] = {
            "files": len(files),
            "parsed": len(bodies),
            "unparseable": bad,
            "fields": dict(keys),
            "html_bodies": html,
            "exact_duplicate_bodies": len(bodies) - len(set(bodies)),
            "distinct_bodies": len(set(bodies)),
            "missing_subject": no_subject,
            "body_words": {
                "min": words_sorted[0] if words else 0,
                "median": words_sorted[len(words_sorted) // 2] if words else 0,
                "max": words_sorted[-1] if words else 0,
            },
        }
    return out


def audit_ephishllm() -> dict:
    path = RAW / "ephishllm" / CFG["sources"]["ephishllm"]["file"]
    rows = json.loads(read_text(path))
    langs = Counter(r.get("Language") for r in rows)
    en = [r for r in rows if r.get("Language") == CFG["preprocess"]["language"]]
    out = {"total": len(rows), "by_language": dict(langs), "en_total": len(en), "en": {}}
    for cls, label in ((1, "phishing"), (0, "legitimate")):
        sub = [r for r in en if r.get("type") == cls]
        bodies = [flatten(str(r.get("Body", ""))) for r in sub]
        ph = sum(1 for r in sub if PLACEHOLDER_RE.search(str(r.get("Body", ""))))
        sal = Counter(salutation_class(str(r.get("Body", ""))) for r in sub)
        words = sorted(len(b.split()) for b in bodies)
        out["en"][label] = {
            "n": len(sub),
            "with_placeholder": ph,
            "placeholder_pct": round(100 * ph / len(sub), 1) if sub else 0,
            "salutation": dict(sal),
            "exact_duplicate_bodies": len(bodies) - len(set(bodies)),
            "body_words": {"min": words[0], "median": words[len(words) // 2], "max": words[-1]} if words else {},
        }
    toks = Counter(m for r in en for m in PLACEHOLDER_RE.findall(str(r.get("Body", ""))))
    out["placeholder_tokens_top"] = toks.most_common(10)
    out["placeholder_distinct"] = len(toks)
    return out


def main() -> int:
    if not (RAW / "provenance.json").exists():
        print("run scripts/01_download_data.py first", file=sys.stderr)
        return 1
    REPORTS.mkdir(exist_ok=True)
    report = {
        "provenance": json.loads(read_text(RAW / "provenance.json")),
        "nahmias": audit_nahmias(),
        "ephishllm": audit_ephishllm(),
    }
    write_json(REPORTS / "audit_raw.json", report)

    print("=" * 66)
    print("NAHMIAS et al. (2024)")
    print("=" * 66)
    for name, s in report["nahmias"].items():
        print(f"{name:22s} n={s['files']:5d}  distinct={s['distinct_bodies']:5d}  "
              f"dup={s['exact_duplicate_bodies']:5d}  html={s['html_bodies']:5d}  "
              f"no_subject={s['missing_subject']:3d}  unparseable={len(s['unparseable'])}")
        print(f"{'':22s} fields={s['fields']}  words(min/med/max)="
              f"{s['body_words']['min']}/{s['body_words']['median']}/{s['body_words']['max']}")
    e = report["ephishllm"]
    print("=" * 66)
    print(f"E-PhishLLM  total={e['total']}  english={e['en_total']}")
    print("=" * 66)
    for label, s in e["en"].items():
        print(f"{label:12s} n={s['n']:5d}  placeholders={s['with_placeholder']:5d} "
              f"({s['placeholder_pct']}%)  salutation={s['salutation']}  dup={s['exact_duplicate_bodies']}")
    print(f"distinct placeholder tokens: {e['placeholder_distinct']}  top: {e['placeholder_tokens_top'][:5]}")
    print(f"\nwritten to {(REPORTS / 'audit_raw.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
