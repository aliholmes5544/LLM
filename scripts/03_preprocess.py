#!/usr/bin/env python3
"""
03_preprocess.py — normalize, clean and deduplicate (Section 3.2.2).

Steps, in order, each counted in reports/preprocess_report.json:
  1. load every record from both sources into one schema
  2. strip HTML identically for all collections; decode entities; keep anchor
     text, drop link targets; collapse whitespace
  3. neutralize E-PhishLLM <<placeholder>> tokens (class-leaking artifact)
  4. drop empty / too-short bodies; truncate over-long bodies at a sentence boundary
  5. remove exact duplicates ACROSS all collections (normalized body)
  6. remove near-duplicates ACROSS all collections (word-trigram Jaccard >= threshold,
     MinHash LSH candidates verified exactly), keeping one record per cluster

Usage:  python scripts/03_preprocess.py
Output: data/processed/records.jsonl, reports/preprocess_report.json
"""
import html
import json
import re
import sys
from collections import Counter, defaultdict

from bs4 import BeautifulSoup
from datasketch import MinHash, MinHashLSH

from common import (ROOT, load_config, read_text, write_json, open_utf8,
                    norm_key, trigrams, GREETING_RE, GENERIC)

CFG = load_config()
P = CFG["preprocess"]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"

# ---- collection map: folder/file -> (subclass, class) ----------------------
NAHMIAS_MAP = {
    "spear_phishing": ("spear_llm", "phish"),
    "traditional_phishing": ("traditional", "phish"),
    "enron_ham": ("enron_ham", "legit"),
    "hard_ham": ("hard_ham", "legit"),
}
# deduplication keep-priority (lower = kept first): evaluation-critical first
PRIORITY = {"spear_llm": 0, "hard_ham": 1, "ephish_phish": 2, "ephish_legit": 3,
            "enron_ham": 4, "traditional": 5}

WS_RE = re.compile(r"[ \t\r\f\v]+")
NL_RE = re.compile(r"\n\s*\n+")
PLACEHOLDER_RE = re.compile(r"<<\s*([^>]*?)\s*>>")
SENT_END_RE = re.compile(r"[.!?]\s")


# ---- text normalization ----------------------------------------------------
def strip_html(text: str) -> str:
    """Same procedure for every collection (Section 3.2.2)."""
    if not text:
        return ""
    if "<" in text and ">" in text:
        soup = BeautifulSoup(text, "lxml")
        for t in soup(["script", "style", "head", "title", "meta"]):
            t.decompose()
        for br in soup.find_all(["br"]):
            br.replace_with("\n")
        for blk in soup.find_all(["p", "div", "li", "tr", "h1", "h2", "h3", "h4", "table"]):
            blk.insert_before("\n")
            blk.insert_after("\n")
        text = soup.get_text()          # anchor text kept, hrefs dropped
    text = html.unescape(text)
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = WS_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = NL_RE.sub("\n\n", text).strip()
    return text


def neutralize_placeholders(text: str) -> tuple[str, int]:
    """Replace <<...>> with neutral phrases carrying no class information."""
    pm = P["placeholder_map"]

    def repl(m):
        inner = m.group(1).lower()
        if "attach" in inner:
            return pm["attachment"]
        if "email" in inner or "address" in inner or "contact" in inner:
            return pm["email"]
        if "link" in inner or "url" in inner or "http" in inner:
            return pm["link"]
        return pm["default"]

    new, n = PLACEHOLDER_RE.subn(repl, text)
    return new, n


def truncate_words(text: str, limit: int) -> tuple[str, bool]:
    words = text.split()
    if len(words) <= limit:
        return text, False
    cut = " ".join(words[:limit])
    ends = [m.end() for m in SENT_END_RE.finditer(cut)]
    cut = cut[: ends[-1]].strip() if ends else cut
    return cut, True


def salutation_class(body: str) -> str:
    m = GREETING_RE.match(body)
    if not m:
        return "none"
    name = m.group(1).strip().lower()
    return "generic" if any(name == g or name.startswith(g + " ") for g in GENERIC) else "named"


# ---- loading ---------------------------------------------------------------
def load_nahmias(report: dict) -> list:
    base = RAW / "nahmias" / CFG["sources"]["nahmias"]["subdir"]
    recs = []
    for folder, (subclass, cls) in NAHMIAS_MAP.items():
        bad = 0
        for f in sorted((base / folder).glob("*.json")):
            try:
                o = json.loads(read_text(f, errors="replace"))
            except Exception:
                bad += 1
                continue
            recs.append({
                "id": f"nah:{folder}:{f.stem}",
                "source": "nahmias", "subclass": subclass, "class": cls,
                "subject": str(o.get("email_subject") or o.get("subject") or "").strip(),
                "body_raw": str(o.get("email_body") or o.get("body") or ""),
            })
        report["unparseable"][subclass] = bad
    return recs


def load_ephishllm() -> list:
    rows = json.loads(read_text(RAW / "ephishllm" / CFG["sources"]["ephishllm"]["file"]))
    recs = []
    for i, r in enumerate(rows):
        if r.get("Language") != P["language"]:
            continue
        cls = "phish" if r.get("type") == 1 else "legit"
        recs.append({
            "id": f"eph:{i}", "source": "ephishllm",
            "subclass": "ephish_phish" if cls == "phish" else "ephish_legit", "class": cls,
            "subject": str(r.get("Subject") or "").strip(),
            "body_raw": str(r.get("Body") or ""),
        })
    return recs


# ---- main ------------------------------------------------------------------
def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    report = {"unparseable": {}, "steps": [], "placeholders_replaced": 0,
              "truncated": Counter(), "too_short": Counter(),
              "exact_dup_removed": Counter(), "near_dup_removed": Counter(),
              "near_dup_pairs_verified": 0, "cross_collection_near_dups": Counter()}

    recs = load_nahmias(report) + load_ephishllm()
    report["steps"].append({"loaded": dict(Counter(r["subclass"] for r in recs))})

    # normalize
    min_words = P.get("min_body_words", 5)
    kept = []
    for r in recs:
        body = r.pop("body_raw")
        if r["source"] == "ephishllm":           # BEFORE html stripping: <<link>> parses as a tag
            body, n = neutralize_placeholders(body)
            report["placeholders_replaced"] += n
        body = strip_html(body)
        body, trunc = truncate_words(body, P["max_body_words"])
        if trunc:
            report["truncated"][r["subclass"]] += 1
        if len(body.split()) < min_words:
            report["too_short"][r["subclass"]] += 1
            continue
        r["subject"] = strip_html(r["subject"])
        r["body"] = body
        r["n_words"] = len(body.split())
        r["salutation"] = salutation_class(body)
        r["truncated"] = trunc
        kept.append(r)
    recs = kept
    report["steps"].append({"after_normalize": dict(Counter(r["subclass"] for r in recs))})

    # exact duplicates across all collections
    recs.sort(key=lambda r: (PRIORITY[r["subclass"]], r["id"]))
    seen = {}
    uniq = []
    for r in recs:
        k = norm_key(r["body"])
        if k in seen:
            report["exact_dup_removed"][r["subclass"]] += 1
            continue
        seen[k] = r["id"]
        uniq.append(r)
    recs = uniq
    report["steps"].append({"after_exact_dedup": dict(Counter(r["subclass"] for r in recs))})

    # near duplicates (MinHash LSH candidates, exact Jaccard verification)
    thr, perm = P["near_dup_jaccard"], P["minhash_perm"]
    lsh = MinHashLSH(threshold=thr, num_perm=perm)
    grams, mh = {}, {}
    for r in recs:
        g = trigrams(r["body"])
        grams[r["id"]] = g
        m = MinHash(num_perm=perm)
        for t in g:
            m.update(t.encode())
        mh[r["id"]] = m
        lsh.insert(r["id"], m)
    parent = {r["id"]: r["id"] for r in recs}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for r in recs:
        if not grams[r["id"]]:
            continue
        for cand in lsh.query(mh[r["id"]]):
            if cand <= r["id"]:
                continue
            a, b = grams[r["id"]], grams[cand]
            if not a or not b:
                continue
            j = len(a & b) / len(a | b)
            if j >= thr:
                report["near_dup_pairs_verified"] += 1
                parent[find(cand)] = find(r["id"])
    clusters = defaultdict(list)
    by_id = {r["id"]: r for r in recs}
    for r in recs:
        clusters[find(r["id"])].append(r)
    final = []
    for members in clusters.values():
        members.sort(key=lambda r: (PRIORITY[r["subclass"]], r["id"]))
        final.append(members[0])
        for m in members[1:]:
            report["near_dup_removed"][m["subclass"]] += 1
            if m["subclass"] != members[0]["subclass"]:
                report["cross_collection_near_dups"][f"{m['subclass']}->{members[0]['subclass']}"] += 1
    final.sort(key=lambda r: r["id"])
    report["steps"].append({"after_near_dedup": dict(Counter(r["subclass"] for r in final))})

    with open_utf8(OUT / "records.jsonl", "w") as fh:
        for r in final:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    for k in ("truncated", "too_short", "exact_dup_removed", "near_dup_removed", "cross_collection_near_dups"):
        report[k] = dict(report[k])
    report["config"] = P
    write_json(REPORTS / "preprocess_report.json", report)

    print("step".ljust(20) + "".join(s.rjust(14) for s in PRIORITY))
    for step in report["steps"]:
        name, counts = next(iter(step.items()))
        print(name.ljust(20) + "".join(str(counts.get(s, 0)).rjust(14) for s in PRIORITY))
    print(f"\nplaceholders replaced: {report['placeholders_replaced']}")
    print(f"too short (<{min_words} words): {report['too_short']}")
    print(f"truncated (>{P['max_body_words']} words): {report['truncated']}")
    print(f"exact dups removed: {report['exact_dup_removed']}")
    print(f"near dups removed (J>={thr}): {report['near_dup_removed']}")
    print(f"cross-collection near-dups: {report['cross_collection_near_dups']}")
    print(f"\nrecords -> {(OUT / 'records.jsonl').relative_to(ROOT)}  ({len(final)} records)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
