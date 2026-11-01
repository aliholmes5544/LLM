"""
core.py — shared pieces of the baseline runner (TASK_06 section 3; Chapter 3 Section 3.5, Chapter 4
Section 4.4): item lists and text, the per-baseline config hash, the fixed decision rule, the model-selection
metrics on `valid`, and hashing helpers. Pure functions where possible so that tests/test_baselines.py covers
them without data or models. Nothing here reads an evaluation label for any purpose other than copying it
into the results row; scoring against the truth is step 07.
"""
import hashlib
import json
import math

from common import ROOT
from detect.items import eval_items, original_item

STRATEGY = "supervised"


def item_text(item: dict, text_cfg: dict) -> str:
    """subject + join + body: the same two fields the detectors see (CLAUDE.md: text only)."""
    return text_cfg["join"].join(item[f] for f in text_cfg["fields"])


def partition_items(name: str, recs: dict, part: dict, bcfg: dict, dcfg: dict) -> list:
    """train / valid: original records of that partition; eval: the detector item set (detect.items.eval_items)."""
    pname = bcfg["partitions"][name]
    if name == "eval":
        return eval_items(recs, part, dcfg)
    return [original_item(recs[i], pname) for i in part[pname]]


def config_hash(key: str, bcfg: dict, seed: int) -> str:
    """sha256 of the baseline's own config block, the text settings, the decision rule inputs and the seed;
    recorded in every row as `config_hash` (the counterpart of the detectors' prompt_hash)."""
    payload = {"baseline": key, "config": bcfg["baselines"][key], "text": bcfg["text"],
               "positive_class": bcfg["positive_class"], "seed": seed}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def label_from_score(score: float, rule: str, positive: str = "phish", negative: str = "legit") -> str:
    """The fixed decision rule of configs/baselines.yaml (threshold.rule): ">= 0.5" for probabilities, "> 0"
    for an SVM decision value. Nothing is tuned: the rule is fixed before any evaluation item is seen."""
    op, val = rule.split()
    v = float(val)
    hit = {">=": score >= v, ">": score > v}[op]
    return positive if hit else negative


def prf(y_true: list, y_pred: list, positive: str = "phish") -> dict:
    """Precision, recall and F1 of the positive class plus accuracy; used on `valid` only (model selection and
    the sanity check of TASK_06 section 6 item 4). Never called on an evaluation partition by this stage."""
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == positive and p == positive)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t != positive and p == positive)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == positive and p != positive)
    tn = len(y_true) - tp - fp - fn
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"n": len(y_true), "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(prec, 4),
            "recall": round(rec, 4), "f1": round(f1, 4), "accuracy": round((tp + tn) / len(y_true), 4)}


def select_C(scores_by_C: dict, tie: str = "smallest_C") -> float:
    """Chosen C = the grid value with the highest selection metric; ties go to the smallest C (deterministic).
    scores_by_C: {C: metric_value}."""
    assert tie == "smallest_C", tie
    best = max(scores_by_C.values())
    return min(c for c, v in scores_by_C.items() if math.isclose(v, best, rel_tol=0, abs_tol=1e-12))


def sha256_bytes(*chunks: bytes) -> str:
    h = hashlib.sha256()
    for c in chunks:
        h.update(c)
    return h.hexdigest()


def rows_for_decide(rows: list) -> list:
    """Adapter for detect.resume.decide(), which reads prompt_hash: the baseline rows carry config_hash."""
    return [{"item_id": r["item_id"], "prompt_hash": r.get("config_hash"), "model_hash": r.get("model_hash")}
            for r in rows]


def model_dir(bcfg: dict):
    d = ROOT / bcfg["model_dir"]
    d.mkdir(parents=True, exist_ok=True)
    return d
