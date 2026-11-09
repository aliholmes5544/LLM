"""
parse.py — stage-1 output parsing for the two-stage detector (TASK_08 section 4; configs/twostage.yaml `parse`;
QUESTIONS.md item 18 decisions (a), (e), (f)).

Pure functions, unit-tested in tests/test_twostage.py. The raw model output is reduced to an indicator dict by
strict json.loads on the FIRST balanced {...} object. Values are normalised first (case-insensitive, trimmed;
the frozen synonym table for the booleans), and only then checked against the vocabulary. A missing key or a
value still out of vocabulary makes the row invalid (a parse failure = the architecture failed; scored as an
incorrect prediction exactly as in step 06). An extra key never invalidates the row; it is counted. A
volunteered verdict (any verdict word anywhere in the raw output) is a diagnostic counter only.
"""
import json
import re

INVALID = "invalid"


def schema_of(tcfg: dict) -> dict:
    """{key: vocabulary list | "bool"} in the key order of the config (threat indicators, then attributes)."""
    ind = tcfg["indicators"]
    return {**ind["threat"], **ind["attributes"]}


def first_balanced_object(text: str):
    """The first balanced {...} span of text (braces inside JSON strings ignored), or None."""
    s = text or ""
    start = s.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(s)):
            c = s[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return s[start:i + 1]
        start = s.find("{", start + 1)
    return None


def _canon(v) -> str:
    """Scalar to a lower-case trimmed string ('true' / 'false' for JSON booleans, '1' / '0' for 1 / 0)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)) and v in (0, 1):
        return str(int(v))
    return str(v).strip().lower() if isinstance(v, str) else ""


def normalise(key_vocab, value, ncfg: dict):
    """The vocabulary value for a raw value after the frozen normalisation, or None when still out of vocabulary."""
    c = _canon(value) if ncfg.get("case_insensitive", True) else (value if isinstance(value, str) else _canon(value))
    if key_vocab == "bool":
        for level, syns in ncfg["boolean"].items():
            if c in [s.lower() for s in syns]:
                return level
        return None
    table = ncfg["ternary"] if list(key_vocab) == ["yes", "no", "unclear"] else {v: [v] for v in key_vocab}
    for level, syns in table.items():
        if c in [s.lower() for s in syns]:
            return level
    return None


def parse_indicators(text: str, schema: dict, ncfg: dict = None) -> tuple:
    """(indicators, error, extra_keys): indicators is a dict when the output is valid (error None), else None with
    the reason (one of parse.invalid_when); extra_keys lists unknown keys (ignored, counted)."""
    ncfg = ncfg or {"case_insensitive": True, "ternary": {"yes": ["yes"], "no": ["no"], "unclear": ["unclear"]},
                    "boolean": {"true": ["true", "yes", "1"], "false": ["false", "no", "0"]}}
    span = first_balanced_object(text)
    if span is None:
        return None, "no_object", []
    try:
        obj = json.loads(span)
    except json.JSONDecodeError:
        return None, "no_object", []
    if not isinstance(obj, dict):
        return None, "not_a_dict", []
    extra = sorted(set(obj) - set(schema))
    if set(schema) - set(obj):
        return None, "missing_key", extra
    out = {}
    for k, vocab in schema.items():
        v = normalise(vocab, obj[k], ncfg)
        if v is None:
            return None, "value_out_of_vocabulary", extra
        out[k] = v
    return out, None, extra


def volunteered_verdict(text: str, words: list) -> bool:
    """True when the raw output contains any verdict word as a whole word (case-insensitive); diagnostic only."""
    t = (text or "").lower()
    return any(re.search(r"\b" + re.escape(w.lower()) + r"\b", t) for w in words)


def levels(vocab) -> list:
    return ["true", "false"] if vocab == "bool" else list(vocab)


def feature_names(schema: dict) -> list:
    """One-hot column names: every vocabulary value of every indicator ("unclear" included; no failure level)."""
    return [f"{k}={v}" for k, vocab in schema.items() for v in levels(vocab)]


def featurize(indicators: dict, schema: dict) -> list:
    """0/1 vector in feature_names order; a parse failure is never featurised (item 18a)."""
    if indicators is None:
        raise ValueError("a parse failure has no feature vector (item 18a)")
    return [1 if indicators[k] == lv else 0 for k, vocab in schema.items() for lv in levels(vocab)]
