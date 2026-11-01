"""
stats.py — metrics and inference for step 07 (TASK_07 sections 2 and 3; QUESTIONS.md item 12e with
refinements 1, 2, 5 and 6; Chapter 4 Section 4.3).

Every rate is a ratio of sums of per-cluster counts, so the cluster bootstrap resamples clusters (source
e-mails) with replacement and recomputes the statistic from the resampled sums. One numpy generator per table,
seeded through the project's derive_rng(seed, "bootstrap", table), so a table's CI does not depend on which
other tables were computed before it. McNemar is the exact binomial test on the discordant pairs; Holm is
applied within a family; a bootstrap contrast gets the two-sided percentile p floored at 1/B.
"""
import math

import numpy as np

from variants.rng import derive_rng

B_DEFAULT = 2000
ALPHA = 0.05


def table_rng(seed: int, table: str) -> np.random.Generator:
    """numpy generator for one table; the integer seed comes from the project's derive_rng stream."""
    return np.random.default_rng(derive_rng(seed, "bootstrap", table).getrandbits(63))


def resampled_sums(counts: np.ndarray, B: int, rng: np.random.Generator, chunk: int = 250) -> np.ndarray:
    """B x m matrix: column sums of `counts` (k x m, one row per cluster) over B cluster resamples."""
    counts = np.asarray(counts, dtype=np.int64)
    k, m = counts.shape
    out = np.empty((B, m), dtype=np.int64)
    for s in range(0, B, chunk):
        e = min(B, s + chunk)
        idx = rng.integers(0, k, size=(e - s, k))
        out[s:e] = counts[idx].sum(axis=1)
    return out


def _ratio(num, den):
    num, den = np.asarray(num, dtype=float), np.asarray(den, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = num / den
    return np.where(den > 0, r, np.nan)


# --- statistics on summed counts (vectorised: `s` is 1-D for the point estimate or B x m for the bootstrap) ---

def stat_rate(s):
    """columns [correct, n]"""
    return _ratio(s[..., 0], s[..., 1])


def stat_delta(s):
    """columns [orig_correct, var_correct, n_pairs] -> rate(original) - rate(variant)"""
    return _ratio(s[..., 0] - s[..., 1], s[..., 2])


def stat_bal_acc(s):
    """columns [correct_pos, n_pos, correct_neg, n_neg]"""
    return 0.5 * (_ratio(s[..., 0], s[..., 1]) + _ratio(s[..., 2], s[..., 3]))


def stat_f1(s):
    """columns [tp, fp, fn]"""
    return _ratio(2 * s[..., 0], 2 * s[..., 0] + s[..., 1] + s[..., 2])


def stat_contrast(s):
    """columns [oc_a, vc_a, oc_b, vc_b, n_pairs] -> delta_b - delta_a (negative: arm b loses less than arm a)"""
    return _ratio((s[..., 2] - s[..., 3]) - (s[..., 0] - s[..., 1]), s[..., 4])


def point_and_ci(counts: np.ndarray, stat, seed: int, table: str, B: int = B_DEFAULT) -> dict:
    """Point estimate from the full sums and a 95% percentile cluster-bootstrap CI."""
    counts = np.asarray(counts, dtype=np.int64)
    if counts.ndim != 2 or counts.shape[0] == 0:
        return {"value": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan"), "boot": None}
    value = float(stat(counts.sum(axis=0)))
    boot = stat(resampled_sums(counts, B, table_rng(seed, table)))
    boot = boot[~np.isnan(boot)]
    if boot.size == 0:
        return {"value": value, "ci_lo": float("nan"), "ci_hi": float("nan"), "boot": boot}
    lo, hi = np.percentile(boot, [100 * ALPHA / 2, 100 * (1 - ALPHA / 2)])
    return {"value": value, "ci_lo": float(lo), "ci_hi": float(hi), "boot": boot}


def bootstrap_p(boot: np.ndarray, B: int = B_DEFAULT) -> float:
    """Two-sided percentile p of a contrast: 2 x min(P(<= 0), P(>= 0)), floored at 1/B (item 12 refinement 2)."""
    if boot is None or boot.size == 0:
        return float("nan")
    p = 2.0 * min(np.mean(boot <= 0), np.mean(boot >= 0))
    return float(min(1.0, max(1.0 / B, p)))


# --- paired tests and multiplicity ---

def mcnemar_exact(b: int, c: int) -> float:
    """Exact two-sided McNemar p: binomial(b + c, 1/2) tail at min(b, c), doubled, capped at 1; 1 if no discordance."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2.0 * tail)


def holm(pvalues: list) -> list:
    """Holm step-down adjusted p-values (monotone, capped at 1); NaN inputs stay NaN and do not count."""
    idx = [i for i, p in enumerate(pvalues) if not (p is None or (isinstance(p, float) and math.isnan(p)))]
    m = len(idx)
    order = sorted(idx, key=lambda i: pvalues[i])
    adj = [float("nan")] * len(pvalues)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adj[i] = running
    return adj


def mcnemar_power(n_pairs: int, discordant: float, drop: float, alpha: float = ALPHA) -> float:
    """A priori power of the exact two-sided McNemar test (item 12 refinement 5).

    n_pairs originals; a share `discordant` of pairs disagree; the variant loses `drop` in sensitivity, so
    pi_b - pi_c = drop with pi_b + pi_c = discordant. Unconditional power: sum over the number of discordant
    pairs d ~ Binomial(n_pairs, discordant) of P(reject | d) with X_b ~ Binomial(d, pi_b / discordant).
    """
    pb = (discordant + drop) / 2
    q = pb / discordant
    power = 0.0
    for d in range(n_pairs + 1):
        pd = math.comb(n_pairs, d) * discordant ** d * (1 - discordant) ** (n_pairs - d)
        if pd < 1e-15:
            continue
        rej = 0.0
        for x in range(d + 1):
            if mcnemar_exact(x, d - x) <= alpha:
                rej += math.comb(d, x) * q ** x * (1 - q) ** (d - x)
        power += pd * rej
    return power
