"""
parse.py — stage-1 output parsing for the two-stage detector (TASK_08 section 4; configs/twostage.yaml `parse`).

Pure functions, unit-tested in tests/test_twostage.py. The raw model output is reduced to an indicator dict by
strict json.loads on the FIRST balanced {...} object; a missing key, an unknown key, a value outside the
indicator's vocabulary, or a non-boolean for a boolean indicator makes the row invalid (scored as an incorrect
prediction, exactly as in step 06). A volunteered verdict (any verdict word in the raw output; the prompt never
uses them) is flagged and ignored.
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


def parse_indicators(text: str, schema: dict) -> tuple:
    """(indicators dict, None) when the output is valid, else (None, reason); reasons are the config's invalid_when."""
    span = first_balanced_object(text)
    if span is None:
        return None, "no_object"
    try:
        obj = json.loads(span)
    except json.JSONDecodeError:
        return None, "no_object"
    if not isinstance(obj, dict):
        return None, "not_a_dict"
    keys = set(obj)
    if keys - set(schema):
        return None, "unknown_key"
    if set(schema) - keys:
        return None, "missing_key"
    out = {}
    for k, vocab in schema.items():
        v = obj[k]
        if vocab == "bool":
            if not isinstance(v, bool):
                return None, "non_boolean"
            out[k] = "true" if v else "false"
        else:
            if not isinstance(v, str) or v not in vocab:
                return None, "value_out_of_vocabulary"
            out[k] = v
    return out, None


def volunteered_verdict(text: str, words: list) -> bool:
    """True when the raw output contains any verdict word as a whole word (case-insensitive)."""
    t = (text or "").lower()
    return any(re.search(r"\b" + re.escape(w.lower()) + r"\b", t) for w in words)


def feature_names(schema: dict, invalid_value: str = INVALID) -> list:
    """One-hot column names: every vocabulary value of every indicator plus the explicit invalid level."""
    names = []
    for k, vocab in schema.items():
        levels = ["true", "false"] if vocab == "bool" else list(vocab)
        names += [f"{k}={v}" for v in levels + [invalid_value]]
    return names


def featurize(indicators, schema: dict, invalid_value: str = INVALID) -> list:
    """0/1 vector in feature_names order; a parse failure (indicators None) lights the invalid level of every key."""
    vec = []
    for k, vocab in schema.items():
        levels = (["true", "false"] if vocab == "bool" else list(vocab)) + [invalid_value]
        v = invalid_value if indicators is None else indicators[k]
        vec += [1 if v == lv else 0 for lv in levels]
    return vec
