"""
stage2.py — the stage-2 logistic regression of the two-stage detector (TASK_08 section 5; configs/twostage.yaml
`stage2`; QUESTIONS.md item 18 decisions (a), (b)). Two fits per language model (configs/twostage.yaml `fits`,
amended 2026-11-10): `clean`, the primary, on the dev originals only, and `all`, the attack-aware secondary, on
every dev item; features are the one-hot indicators, rows whose extraction did not parse are excluded from the
fit (and counted), C is chosen on dev by stratified GROUP cross-validation with the source e-mail as the group
(an original and its variants never straddle a fold), the threshold is fixed at 0.5. Nothing here reads an
evaluation partition.
"""
import hashlib
import json

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, f1_score, log_loss
from sklearn.model_selection import StratifiedGroupKFold

from twostage.parse import feature_names, featurize, schema_of

POSITIVE = "phish"
HASHED = ("indicators", "definitions", "decoding", "parse", "stage2")


def config_hash(tcfg: dict, seed: int) -> str:
    """sha256 of the parts of configs/twostage.yaml that define the detector, plus the seed."""
    payload = {k: tcfg.get(k) for k in HASHED}
    payload["seed"] = seed
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def cluster_of(item_id: str) -> str:
    """The source e-mail of an item: the variant id is `<source id>#<condition>` (scripts/05_derive_variants.py)."""
    return item_id.split("#", 1)[0]


def design(rows: list, tcfg: dict) -> tuple:
    """(X, y, groups, names) from the PARSED extraction rows: X one-hot, y = 1 for phish, groups = source e-mail."""
    schema = schema_of(tcfg)
    X = np.array([featurize(r["indicators"], schema) for r in rows], dtype=np.float64)
    y = np.array([1 if r["label_true"] == POSITIVE else 0 for r in rows], dtype=np.int64)
    groups = np.array([cluster_of(r["item_id"]) for r in rows])
    return X, y, groups, feature_names(schema)


def _metric(name: str, y, p):
    pred = (p >= 0.5).astype(int)
    if name == "balanced_accuracy":
        return balanced_accuracy_score(y, pred)
    if name == "f1_phish":
        return f1_score(y, pred, zero_division=0)
    if name == "neg_log_loss":
        return -log_loss(y, p, labels=[0, 1])
    raise ValueError(f"unknown cv metric {name}")


def _lr(C: float, s2: dict, seed: int) -> LogisticRegression:
    c = s2["classifier"]
    return LogisticRegression(C=C, solver=c["solver"], max_iter=c["max_iter"], class_weight=c["class_weight"], random_state=seed)


def select_C(X, y, groups, tcfg: dict, seed: int) -> tuple:
    """(chosen C, table of mean cv metric per C); grouped stratified folds; ties go to the smallest C."""
    s2 = tcfg["stage2"]
    if s2["cv"]["scheme"] != "StratifiedGroupKFold":
        raise SystemExit(f"cv scheme {s2['cv']['scheme']} not implemented (item 18b fixes StratifiedGroupKFold)")
    cv = StratifiedGroupKFold(n_splits=s2["cv"]["folds"], shuffle=s2["cv"]["shuffle"], random_state=seed)
    table = []
    for C in s2["C_grid"]:
        scores = []
        for tr, te in cv.split(X, y, groups):
            m = _lr(C, s2, seed).fit(X[tr], y[tr])
            scores.append(_metric(s2["cv"]["metric"], y[te], m.predict_proba(X[te])[:, 1]))
        table.append({"C": C, "cv_mean": float(np.mean(scores)), "cv_sd": float(np.std(scores))})
    best = max(table, key=lambda t: (round(t["cv_mean"], 12), -t["C"]))   # highest metric, smallest C on a tie
    return best["C"], table


FIT_ROWS = {"originals": lambda r: r.get("condition") == "original",     # the dev originals: no rewritten text (clean fit)
            "all": lambda r: True}                                       # originals and accepted dev variants (attack-aware fit)


def fit_stage2(rows: list, tcfg: dict, seed: int, fit_rows: str = "all") -> dict:
    """Fit on the dev extraction rows selected by `fit_rows` (configs/twostage.yaml fits.<key>.rows: "originals" or
    "all"; parse failures excluded and counted); model, selection table, coefficients."""
    pool = [r for r in rows if FIT_ROWS[fit_rows](r)]
    kept = [r for r in pool if r.get("indicators") is not None]
    n_excluded = len(pool) - len(kept)
    X, y, groups, names = design(kept, tcfg)
    if len(set(y.tolist())) < 2:
        raise SystemExit("stage 2 needs both classes in the fitting rows")
    C, table = select_C(X, y, groups, tcfg, seed)
    model = _lr(C, tcfg["stage2"], seed).fit(X, y)
    coefs = sorted(zip(names, model.coef_[0].tolist()), key=lambda t: -abs(t[1]))
    cv_at_C = next(t for t in table if t["C"] == C)
    resub = float(balanced_accuracy_score(y, (model.predict_proba(X)[:, 1] >= 0.5).astype(int)))
    return {"model": model, "C": C, "cv_table": table, "feature_names": names,
            "balanced_accuracy_cv": round(cv_at_C["cv_mean"], 6), "balanced_accuracy_cv_sd": round(cv_at_C["cv_sd"], 6),
            "balanced_accuracy_resubstitution": round(resub, 6),
            "coefficients": [{"feature": n, "coef": round(c, 6)} for n, c in coefs],
            "intercept": float(model.intercept_[0]), "fit_rows": fit_rows, "n_rows_available": int(len(rows)),
            "n_rows": int(len(pool)), "n_fitted": int(len(kept)),
            "n_excluded_parse_failures": int(n_excluded), "n_positive": int(y.sum()), "n_negative": int(len(y) - y.sum()),
            "n_groups": int(len(set(groups.tolist())))}


def predict_row(model, row: dict, tcfg: dict) -> tuple:
    """(label, p_phish) for one extraction row; a parse failure short-circuits to ("invalid", None) (item 18a)."""
    if row.get("indicators") is None:
        return "invalid", None
    x = np.array([featurize(row["indicators"], schema_of(tcfg))], dtype=np.float64)
    p = float(model.predict_proba(x)[0, 1])
    return (POSITIVE if p >= 0.5 else "legit"), p


def save_model(path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, path)
    return sha256_file(path)


def load_model(path) -> dict:
    return joblib.load(path)


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
