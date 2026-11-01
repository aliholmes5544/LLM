"""
ensemble.py — the majority-vote ensemble of the six detectors (TASK_07 section 4a, QUESTIONS.md item 12a).

Per strategy and item: an invalid prediction is an abstention; fewer than 4 valid votes, or a tie among the
valid votes (3-3, or 2-2 with four valid votes), gives an invalid ensemble prediction; otherwise the majority
label. No weighting, no tuning. The ensemble is scored as a seventh detector (kind "ensemble") in every table.
"""
import numpy as np
import pandas as pd

MIN_VALID = 4
ENSEMBLE = "ensemble"
META = ["item_id", "cluster", "partition", "condition", "item_class", "partition_set", "label_true", "source",
        "subclass", "body_words"]


def ensemble_rows(items: pd.DataFrame, models: list) -> pd.DataFrame:
    """One ensemble row per (strategy, item), built from the rows of the six language models."""
    llm = items[(items["kind"] == "llm") & items["detector"].isin(models)]
    out = []
    for strategy, g in llm.groupby("strategy", sort=True):
        votes = g.pivot(index="item_id", columns="detector", values="label_pred")
        if votes.shape[1] != len(models) or votes.isna().any().any():
            raise SystemExit(f"ensemble/{strategy}: not every model has a prediction for every item")
        valid = votes.isin(["phish", "legit"])
        n_valid = valid.sum(axis=1)
        n_phish = (votes == "phish").sum(axis=1)
        n_legit = (votes == "legit").sum(axis=1)
        label = np.where(n_phish > n_legit, "phish", np.where(n_legit > n_phish, "legit", "invalid"))
        label = np.where(n_valid < MIN_VALID, "invalid", label)
        meta = g.drop_duplicates("item_id").set_index("item_id").loc[votes.index, META[1:]]
        df = meta.reset_index()
        df["detector"], df["kind"], df["strategy"] = ENSEMBLE, ENSEMBLE, strategy
        df["label_pred"] = label
        df["invalid"] = df["label_pred"] == "invalid"
        df["n_valid_votes"] = n_valid.values
        df["n_phish_votes"] = n_phish.values
        df["n_legit_votes"] = n_legit.values
        for col in ("score", "latency_s"):
            df[col] = np.nan
        df["n_prompt_tokens"], df["truncated_input"], df["backend"] = 0, False, "vote"
        out.append(df)
    return pd.concat(out, ignore_index=True)


def vote_summary(ens: pd.DataFrame) -> pd.DataFrame:
    """Per strategy: items by number of valid votes and by majority size; ensemble invalid count (structural)."""
    rows = []
    for strategy, g in ens.groupby("strategy", sort=True):
        maj = np.maximum(g["n_phish_votes"], g["n_legit_votes"])
        row = {"strategy": strategy, "n_items": len(g), "ensemble_invalid": int(g["invalid"].sum())}
        for v in range(0, 7):
            row[f"valid_votes_{v}"] = int((g["n_valid_votes"] == v).sum())
        for mj in range(0, 7):
            row[f"majority_{mj}"] = int((maj == mj).sum())
        row["unanimous"] = int(((maj == 6)).sum())
        rows.append(row)
    return pd.DataFrame(rows)
