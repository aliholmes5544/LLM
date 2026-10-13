"""
spans.py — protected spans: detection, masking and restoration (Section 3.2.3).

A protected span must survive every transformation verbatim: personal and organisational
names, dates, times, amounts, email-like strings and the neutral placeholder phrases
introduced in step 03 ("the link", "the attachment", "the address"). Spans are located
once per record on the whole body (character offsets). For paraphrasing they are masked
as [[S1]], [[S2]], ... and restored afterwards; for obfuscation they simply make the
tokens inside them ineligible.
"""
import re
from collections import Counter

Span = dict  # {"start": int, "end": int, "text": str, "label": str, "source": str}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
MONEY_RE = re.compile(r"(?:[$€£]\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:USD|EUR|GBP|dollars?|euros?|pounds?)\b)")
NUMBER_RE = re.compile(r"\d[\d,./:-]*\d|\d")
MASK_RE = re.compile(r"\[\[S(\d+)\]\]")

_PRIORITY = {"placeholder": 0, "regex": 1, "ner": 2}


def _regex_spans(body: str, placeholder_phrases: list) -> list:
    out = []
    phrase_re = re.compile(r"\b(" + "|".join(re.escape(p) for p in placeholder_phrases) + r")\b", re.I)
    for m in phrase_re.finditer(body):
        out.append({"start": m.start(), "end": m.end(), "text": m.group(0), "label": "PLACEHOLDER", "source": "placeholder"})
    for label, rx in (("EMAIL", EMAIL_RE), ("MONEY", MONEY_RE), ("NUMBER", NUMBER_RE)):
        for m in rx.finditer(body):
            out.append({"start": m.start(), "end": m.end(), "text": m.group(0), "label": label, "source": "regex"})
    return out


def detect_spans(body: str, nlp, placeholder_phrases: list, ner_labels: list) -> list:
    """All protected spans of `body`, merged and sorted by start offset."""
    spans = _regex_spans(body, placeholder_phrases)
    if nlp is not None:
        for ent in nlp(body).ents:
            if ent.label_ in ner_labels:
                spans.append({"start": ent.start_char, "end": ent.end_char, "text": ent.text,
                              "label": ent.label_, "source": "ner"})
    return merge_spans(spans)


def merge_spans(spans: list) -> list:
    """Drop overlaps: placeholders win, then longer spans; result is non-overlapping."""
    ranked = sorted(spans, key=lambda s: (_PRIORITY[s["source"]], -(s["end"] - s["start"]), s["start"]))
    kept = []
    for s in ranked:
        if s["end"] <= s["start"]:
            continue
        if all(s["end"] <= k["start"] or s["start"] >= k["end"] for k in kept):
            kept.append(s)
    return sorted(kept, key=lambda s: s["start"])


def mask(body: str, spans: list) -> tuple:
    """Replace spans (in body order) by [[S1]].. tokens; return (masked, {token: text})."""
    out, mapping, pos = [], {}, 0
    for i, s in enumerate(spans, 1):
        token = f"[[S{i}]]"
        out.append(body[pos:s["start"]])
        out.append(token)
        mapping[token] = body[s["start"]:s["end"]]
        pos = s["end"]
    out.append(body[pos:])
    return "".join(out), mapping


def restore(text: str, mapping: dict) -> str:
    """Put span texts back; an unknown token is left as-is (and fails spans_present)."""
    return MASK_RE.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)


def spans_present(variant_body: str, spans: list) -> tuple:
    """True iff every span text occurs in the variant at least as often as in the original."""
    need = Counter(s["text"] for s in spans)
    missing = sorted(t for t, n in need.items() if variant_body.count(t) < n)
    return (not missing), missing
