"""
obfuscate.py — deterministic surface obfuscation with an exact edit log (Section 3.2.3).

Eligible token: alphabetic, at least `min_token_len` characters, wholly outside every
protected span. `rate * n_eligible` tokens (rounded half up) are chosen with the seeded
RNG; each receives exactly ONE operation drawn uniformly from
  homoglyph   - one letter replaced by a visually confusable character (fixed table)
  digit       - one letter replaced by its conventional digit lookalike (fixed map)
  zero_width  - U+200B inserted after a random interior letter
  separator   - "-" or "." inserted after a random interior letter
If the drawn operation cannot apply to the token (no mappable letter) it is redrawn
among the applicable ones; redraws are counted. Edit positions are indices into the
ORIGINAL body; edits are applied right-to-left, and `replay_reverse` undoes them
left-to-right, which must reproduce the original exactly (integrity check).
"""
import math
import random
import re

TOKEN_RE = re.compile(r"[^\W\d_]+")
OPS = ("homoglyph", "digit", "zero_width", "separator")


def eligible_tokens(body: str, spans: list, min_len: int) -> list:
    """[{start, end, text}] for alphabetic tokens >= min_len chars outside all spans."""
    out = []
    for m in TOKEN_RE.finditer(body):
        if m.end() - m.start() < min_len or not m.group(0).isalpha():
            continue
        if any(m.start() < s["end"] and m.end() > s["start"] for s in spans):
            continue
        out.append({"start": m.start(), "end": m.end(), "text": m.group(0)})
    return out


def _applicable(token: str, cfg: dict) -> list:
    ops = []
    if any(ch in cfg["homoglyph"] for ch in token):
        ops.append("homoglyph")
    if any(ch in cfg["digit"] for ch in token):
        ops.append("digit")
    if len(token) >= 3:
        ops.extend(["zero_width", "separator"])
    return ops


def _edit_for(token: dict, op: str, rng: random.Random, cfg: dict) -> dict:
    text = token["text"]
    if op in ("homoglyph", "digit"):
        table = cfg[op]
        idx = rng.choice([i for i, ch in enumerate(text) if ch in table])
        return {"position": token["start"] + idx, "original_char": text[idx],
                "replacement": table[text[idx]], "operation": op}
    j = rng.randrange(1, len(text) - 1)              # interior letter index
    repl = cfg["zero_width"] if op == "zero_width" else rng.choice(cfg["separators"])
    return {"position": token["start"] + j + 1, "original_char": "", "replacement": repl, "operation": op}


def obfuscate(body: str, spans: list, rate: float, rng: random.Random, cfg: dict) -> tuple:
    """Return (variant_body, edits, stats). Pure: same inputs and RNG state -> same output."""
    tokens = eligible_tokens(body, spans, cfg["min_token_len"])
    k = int(math.floor(rate * len(tokens) + 0.5))
    chosen = sorted(rng.sample(range(len(tokens)), k)) if k else []
    edits, redraws = [], 0
    for i in chosen:
        tok = tokens[i]
        op = rng.choice(OPS)
        applicable = _applicable(tok["text"], cfg)
        if op not in applicable:
            redraws += 1
            op = rng.choice(applicable)
        edits.append(_edit_for(tok, op, rng, cfg))
    variant = apply_edits(body, edits)
    stats = {"n_eligible": len(tokens), "n_selected": k, "op_redraws": redraws,
             "ops": {op: sum(1 for e in edits if e["operation"] == op) for op in OPS}}
    return variant, edits, stats


def apply_edits(body: str, edits: list) -> str:
    """Apply edits right-to-left so original-coordinate positions stay valid."""
    s = body
    for e in sorted(edits, key=lambda e: e["position"], reverse=True):
        p = e["position"]
        if e["original_char"] == "":
            s = s[:p] + e["replacement"] + s[p:]
        else:
            if s[p] != e["original_char"]:
                raise ValueError(f"edit at {p}: expected {e['original_char']!r}, found {s[p]!r}")
            s = s[:p] + e["replacement"] + s[p + 1:]
    return s


def replay_reverse(variant: str, edits: list) -> str:
    """Undo edits left-to-right; the prefix before each edit already equals the original."""
    s = variant
    for e in sorted(edits, key=lambda e: e["position"]):
        p, repl = e["position"], e["replacement"]
        if s[p:p + len(repl)] != repl:
            raise ValueError(f"replay at {p}: expected {repl!r}, found {s[p:p + len(repl)]!r}")
        s = s[:p] + e["original_char"] + s[p + len(repl):]
    return s
