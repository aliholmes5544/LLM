"""
tfidf.py — the two TF-IDF baselines of configs/baselines.yaml (TASK_06 section 3: tfidf_lr, tfidf_svm;
Nahmias protocol: fit on `train`, C chosen on `valid`, evaluated on the detector item set). Deterministic:
the vectoriser's vocabulary is sorted, lbfgs and liblinear-style coordinate descent are seeded, so a refit on
the same machine gives the same coefficients and the same model_hash (the runner checks this against the
hash recorded by the previous run).
"""
import json
import time

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC

from baselines.core import label_from_score, prf, select_C, sha256_bytes


def build_vectorizer(f: dict) -> TfidfVectorizer:
    return TfidfVectorizer(analyzer=f["analyzer"], ngram_range=tuple(f["ngram_range"]), min_df=f["min_df"],
                           lowercase=f["lowercase"], sublinear_tf=f["sublinear_tf"], max_features=f["max_features"])


def build_classifier(c: dict, C: float, seed: int):
    if c["type"] == "LogisticRegression":
        return LogisticRegression(C=C, solver=c["solver"], max_iter=c["max_iter"], class_weight=c["class_weight"],
                                  random_state=seed)
    if c["type"] == "LinearSVC":
        return LinearSVC(C=C, loss=c["loss"], max_iter=c["max_iter"], class_weight=c["class_weight"],
                         random_state=seed)
    raise ValueError(f"unknown classifier type {c['type']}")


def fit(entry: dict, train_texts: list, train_y: list, valid_texts: list, valid_y: list, seed: int,
        positive: str) -> dict:
    """Fit the vectoriser on train, then one classifier per C of the grid; choose C by the selection metric on
    valid (ties: smallest C). Returns the chosen model and the full selection table."""
    t0 = time.perf_counter()
    vec = build_vectorizer(entry["features"])
    X_train = vec.fit_transform(train_texts)
    X_valid = vec.transform(valid_texts)
    rule = entry["threshold"]["rule"]
    table, models = {}, {}
    for C in entry["C_grid"]:
        clf = build_classifier(entry["classifier"], C, seed).fit(X_train, train_y)
        pred = [label_from_score(s, rule, positive) for s in scores(clf, X_valid, positive)]
        table[C] = prf(valid_y, pred, positive)
        models[C] = clf
    metric = entry["selection"]["metric"]
    assert metric == "f1_phish", metric
    chosen = select_C({C: t["f1"] for C, t in table.items()}, entry["selection"]["tie"])
    return {"vectorizer": vec, "clf": models[chosen], "C": chosen, "selection_table": table,
            "fit_s": round(time.perf_counter() - t0, 2), "vocab_size": len(vec.vocabulary_),
            "n_train": len(train_texts), "n_valid": len(valid_texts)}


def scores(clf, X, positive: str) -> np.ndarray:
    """p(positive) for a probabilistic classifier, the signed decision value otherwise."""
    pos = list(clf.classes_).index(positive)
    if hasattr(clf, "predict_proba"):
        return clf.predict_proba(X)[:, pos]
    d = clf.decision_function(X)
    return d if pos == 1 else -d          # decision_function is positive for classes_[1]


def score_one(model: dict, text: str, positive: str) -> tuple:
    """(score, number of non-zero features) for one item; the per-item timing is done by the caller."""
    x = model["vectorizer"].transform([text])
    return float(scores(model["clf"], x, positive)[0]), int(x.nnz)


def model_hash(model: dict) -> str:
    """sha256 of the sorted vocabulary, the coefficients and the intercept (rounded to 1e-8): the identity of
    the fitted model, reproducible on a refit with the same data, config and seed."""
    vocab = json.dumps(sorted(model["vectorizer"].vocabulary_.items()), ensure_ascii=False).encode("utf-8")
    coef = np.round(model["clf"].coef_, 8).astype(np.float64).tobytes()
    icpt = np.round(model["clf"].intercept_, 8).astype(np.float64).tobytes()
    return sha256_bytes(vocab, coef, icpt, json.dumps(list(model["clf"].classes_)).encode("utf-8"))


def save(model: dict, path) -> str:
    """Persist vectoriser + classifier (joblib, gitignored models/ dir); returns the file's sha256."""
    import joblib
    joblib.dump({"vectorizer": model["vectorizer"], "clf": model["clf"], "C": model["C"]}, path)
    return sha256_bytes(path.read_bytes())
