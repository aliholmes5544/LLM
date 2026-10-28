"""
stats.py — per-cell statistics shared by the smoke test and the detection runner (TASK_06 section 7:
per-cell invalid rates and latencies in reports/detection_run_report.json). Scoring (metrics, deltas,
bootstrap, McNemar) is step 07 and is deliberately absent here.
"""
import statistics
from collections import Counter


def cell_stats(rows: list, gate: float = None) -> dict:
    lat = [r["latency_s"] for r in rows]
    n_inv = sum(r["invalid"] for r in rows)
    st = {"n": len(rows), "invalid": n_inv, "invalid_rate": round(n_inv / len(rows), 4),
          "pred_counts": dict(Counter(r["label_pred"] for r in rows)),
          "latency_median_s": round(statistics.median(lat), 2), "latency_mean_s": round(statistics.fmean(lat), 2),
          "latency_max_s": round(max(lat), 2), "latency_total_s": round(sum(lat), 1),
          "prompt_tokens_median": int(statistics.median(r["n_prompt_tokens"] for r in rows)),
          "prompt_tokens_max": max(r["n_prompt_tokens"] for r in rows),
          "output_tokens_median": int(statistics.median(r["n_output_tokens"] for r in rows)),
          "finish_reasons": dict(Counter(r["finish_reason"] for r in rows)),
          "truncated_input": sum(r["truncated_input"] for r in rows),
          "backends": dict(Counter(r.get("backend", "unrecorded") for r in rows))}
    if gate is not None:
        st["gate_pass"] = n_inv / len(rows) <= gate
    return st
