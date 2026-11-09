"""
stage2.py — the stage-2 logistic regression of the two-stage detector (TASK_08 section 5; configs/twostage.yaml
`stage2`). One model per language model, fitted on the dev extractions only: features are the one-hot
indicators (parse failures encoded explicitly), C is chosen on dev by stratified cross-validation, the threshold
is fixed at 0.5. Nothing here reads an evaluation partition.
"""
import hashlib
import json

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, f1_score, log_loss
from sklearn.model_selection import StratifiedKFold

from twostage.parse import feature_names, featurize, schema_of

POSITIVE = "phish"


def config_hash(tcfg: dict, seed: int) -> str:
    """sha256 of the parts of configs/twostage.yaml that define the detector, plus the seed."""
    payload = {k: tcfg[k] for k in ("indicators", "decoding", "parse", "stage2")}
    payload["seed"] = seed
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def design(rows: list, tcfg: dict) -> tuple:
    """(X, y, names) from extraction rows: X one-hot in feature order, y = 1 for phish."""
    schema, inv = schema_of(tcfg), tcfg["parse"]["invalid_value"]
    X = np.array([featurize(r.get("indicators"), schema, inv) for r in rows], dtype=np.float64)
    y = np.array([1 if r["label_true"] == POSITIVE else 0 for r in rows], dtype=np.int64)
    return X, y, feature_names(schema, inv)


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


def select_C(X, y, tcfg: dict, seed: int) -> tuple:
    """(chosen C, table of mean cv metric per C); ties go to the smallest C."""
    s2 = tcfg["stage2"]
    cv = StratifiedKFold(n_splits=s2["cv"]["folds"], shuffle=s2["cv"]["shuffle"], random_state=seed)
    table = []
    for C in s2["C_grid"]:
        scores = []
        for tr, te in cv.split(X, y):
            m = _lr(C, s2, seed).fit(X[tr], y[tr])
            scores.append(_metric(s2["cv"]["metric"], y[te], m.predict_proba(X[te])[:, 1]))
        table.append({"C": C, "cv_mean": float(np.mean(scores)), "cv_sd": float(np.std(scores))})
    best = max(table, key=lambda t: (round(t["cv_mean"], 12), -t["C"]))   # highest metric, smallest C on a tie
    return best["C"], table


def fit_stage2(rows: list, tcfg: dict, seed: int) -> dict:
    """Fit on the dev extraction rows; returns the model, the selection table and the coefficients."""
    X, y, names = design(rows, tcfg)
    if len(set(y.tolist())) < 2:
        raise SystemExit("stage 2 needs both classes in the fitting rows")
    C, table = select_C(X, y, tcfg, seed)
    model = _lr(C, tcfg["stage2"], seed).fit(X, y)
    coefs = sorted(zip(names, model.coef_[0].tolist()), key=lambda t: -abs(t[1]))
    return {"model": model, "C": C, "cv_table": table, "feature_names": names,
            "coefficients": [{"feature": n, "coef": round(c, 6)} for n, c in coefs],
            "intercept": float(model.intercept_[0]), "n_rows": int(len(rows)), "n_positive": int(y.sum()),
            "n_parse_failures": int(sum(1 for r in rows if r.get("indicators") is None))}


def predict_row(model, row: dict, tcfg: dict) -> tuple:
    """(label, p_phish) for one extraction row; a parse failure gives ("invalid", None) (TASK_08 section 4)."""
    if row.get("indicators") is None:
        return "invalid", None
    x = np.array([featurize(row["indicators"], schema_of(tcfg), tcfg["parse"]["invalid_value"])], dtype=np.float64)
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
