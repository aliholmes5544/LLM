"""
budget.py — compute-unit projection of the two-stage extraction (TASK_08 section 9 step 2; QUESTIONS.md item 18
(j), (k) and the step-2 record). Two plans, defined by the author on 2026-11-09:

  A  dev + the full eval partition (796 + 5,207 = 6,003 items per model), the plan of TASK_08 section 2;
  B  dev + the core eval only, gen_phish and gen_legit excluded (796 + 3,207 = 4,003 items per model).

Basis per model, the best available first:

  measured_dev  the full dev extraction cell twostage_<model>/extract/dev (796 items on the tier; the checkpoint of item 18
            option 1: its mean latency and the dev session's span rate revise the projection before the eval run);
  measured  the GPU smoke cell smoke/<model>/<eval_tier> of reports/twostage_report.json: seconds per item = the
            cell's mean latency on its tier (the sum is governed by the mean; one point estimate from 20 items),
            plus one model load per session; units per hour = the rate measured from the author's "Available
            compute units" reading (report `compute_units`, written by `06_run_twostage.py units`: units consumed
            over the span of the session) when one exists for the tier, else the published rate.
  prior     before the GPU smoke: the main study's CoT cell of the same model and tier
            (reports/detection_run_report.json): low = the CoT mean latency, high = scaled by (smoke output
            tokens / CoT output tokens); a model without a CPU smoke takes the other models' mean ratio.

Nothing here reads a model or an evaluation partition's text; `06_run_twostage.py budget` writes the report's
`budget_projection` and prints the table. The `eval_only` totals are the remainder once dev is extracted.
"""
from collections import defaultdict

PLANS = {"A": {"name": "dev + full eval", "exclude_partitions": ()},
         "B": {"name": "dev + core eval (gen_phish, gen_legit excluded)", "exclude_partitions": ("gen_phish", "gen_legit")}}


def plan_counts(dev_items: list, eval_items: list) -> dict:
    """Items per model under each plan, with the eval items by partition."""
    out = {}
    for key, plan in PLANS.items():
        ev = [i for i in eval_items if i["partition"] not in plan["exclude_partitions"]]
        by_part = defaultdict(int)
        for i in ev:
            by_part[i["partition"]] += 1
        out[key] = {"name": plan["name"], "exclude_partitions": list(plan["exclude_partitions"]), "dev": len(dev_items),
                    "eval": len(ev), "items_per_model": len(dev_items) + len(ev), "eval_by_partition": dict(sorted(by_part.items()))}
    return out


def units_entry(report: dict, tier: str, cells: list, before: float, after: float, span_s, rates: dict) -> dict:
    """One compute-unit record (item 18j/k): the reading before and after a Colab session, the sessions it covers
    (those of the given cells that carry the same before reading, else each cell's last session), the wall-clock
    estimate of those sessions and the gap, and the rate measured over the session's span."""
    sessions = []
    for key in cells:
        ss = report.get("cells", {}).get(key, {}).get("sessions", [])
        match = [s for s in ss if s.get("units", {}).get("units_before") == before]
        for s in (match or ss[-1:]):
            sessions.append({"cell": key, "started_at": s.get("started_at"), "finished_at": s.get("finished_at"),
                             "items_run": s.get("items_run"), "wall_s": s.get("wall_s"),
                             "estimate_wall_x_rate": s.get("units", {}).get("estimate_wall_x_rate")})
    wall = round(sum(s["wall_s"] or 0 for s in sessions), 1)
    est = round(sum(s["estimate_wall_x_rate"] or 0 for s in sessions), 3)
    measured = round(before - after, 3)
    return {"tier": tier, "cells": list(cells), "units_before": before, "units_after": after, "measured_units": measured,
            "sessions": sessions, "extraction_wall_s": wall, "estimate_wall_x_rate": est,
            "gap_measured_minus_estimate": round(measured - est, 3), "span_s": span_s,
            "rate_published_units_per_hour": rates.get(tier),
            "rate_measured_per_span_hour": round(measured / (span_s / 3600), 3) if span_s else None,
            "rate_measured_per_extraction_hour": round(measured / (wall / 3600), 3) if wall else None,
            "note": "span = the session from the start of the extraction cell to the moment the after reading was entered "
                    "(model loads and idle time included): the span rate is the billing rate to compare with the published one; "
                    "the per-extraction-hour rate is inflated by the loads of a short smoke and is not used for the projection."}


def measured_rate(report: dict, tier: str):
    """The latest span-measured rate of a tier, or None."""
    recs = [r for r in report.get("compute_units", {}).values() if r.get("tier") == tier and r.get("rate_measured_per_span_hour")]
    return recs[-1]["rate_measured_per_span_hour"] if recs else None


def _smoke_summary(cell):
    if not cell or not cell.get("n_done"):
        return None
    return {k: cell.get(k) for k in ("n_done", "n_expected", "parse_failure_rate", "volunteered_verdict_rate", "latency_median_s",
                                     "latency_mean_s", "output_tokens_mean", "gpu", "model_load_s", "git_commit")}


def projection(report: dict, tcfg: dict, mcfg: dict, det_cells: dict, counts: dict) -> dict:
    """The budget projection for every model of the two-stage detector under plans A and B."""
    rates = tcfg["budget"]["rates_units_per_hour"]
    planned, stop = tcfg["budget"]["compute_units_planned"], tcfg["budget"]["compute_units_stop"]
    cells = report.get("cells", {})
    ratios = {}
    for m in tcfg["models"]:
        cpu, cot = cells.get(f"smoke/{m}/laptop"), det_cells.get(f"{m}/cot/eval")
        if cpu and cpu.get("output_tokens_mean") and cot and cot.get("output_tokens_median"):
            ratios[m] = cpu["output_tokens_mean"] / cot["output_tokens_median"]
    mean_ratio = sum(ratios.values()) / len(ratios) if ratios else None
    rows, totals = [], {p: {"low": 0.0, "high": 0.0} for p in counts}
    for m in tcfg["models"]:
        tier = mcfg["models"][m]["eval_tier"]
        gpu_cell, cpu_cell, cot = cells.get(f"smoke/{m}/{tier}"), cells.get(f"smoke/{m}/laptop"), det_cells.get(f"{m}/cot/eval", {})
        dev_cell = cells.get(f"{tcfg.get('model_prefix', 'twostage_')}{m}/extract/dev")
        rate_pub, rate_meas = rates.get(tier), measured_rate(report, tier)
        rate_used = rate_meas or rate_pub
        if dev_cell and dev_cell.get("n_done"):
            basis, s_lo, load_s, ratio_src = "measured_dev", dev_cell["latency_mean_s"], dev_cell.get("model_load_s") or 0.0, None
            s_hi = s_lo
        elif gpu_cell and gpu_cell.get("n_done"):
            basis, s_lo, load_s, ratio_src = "measured", gpu_cell["latency_mean_s"], gpu_cell.get("model_load_s") or 0.0, None
            s_hi = s_lo
        else:
            basis, s_lo, load_s = "prior", cot.get("latency_mean_s"), 0.0
            ratio = ratios.get(m, mean_ratio)
            ratio_src = "own CPU smoke" if m in ratios else ("other models' mean ratio" if ratio else None)
            s_hi = s_lo * ratio if (s_lo and ratio) else s_lo
        units = {}
        for p, c in counts.items():
            n = c["items_per_model"]
            u = {"low": (s_lo * n + load_s) / 3600 * rate_used if s_lo else None,
                 "high": (s_hi * n + load_s) / 3600 * rate_used if s_hi else None}
            units[p] = {k: (round(v, 1) if v is not None else None) for k, v in u.items()}
            for k in ("low", "high"):
                totals[p][k] += u[k] or 0.0
        eval_only = {p: (round((s_hi * c["eval"] + load_s) / 3600 * rate_used, 1) if s_hi else None) for p, c in counts.items()}
        for p in counts:
            totals.setdefault("eval_only_" + p, 0.0)
            totals["eval_only_" + p] += eval_only[p] or 0.0
        rows.append({"model": m, "tier": tier, "basis": basis, "dev_cell": _smoke_summary(dev_cell), "gpu_smoke": _smoke_summary(gpu_cell),
                     "cpu_smoke": _smoke_summary(cpu_cell), "eval_only_units": eval_only,
                     "cot_eval": {"latency_mean_s": cot.get("latency_mean_s"), "output_tokens_median": cot.get("output_tokens_median")},
                     "output_token_ratio": (round(ratios[m], 3) if m in ratios else
                                            (round(mean_ratio, 3) if (basis == "prior" and mean_ratio) else None)),
                     "ratio_source": ratio_src,
                     "seconds_per_item": {"low": round(s_lo, 3) if s_lo else None, "high": round(s_hi, 3) if s_hi else None},
                     "model_load_s": load_s, "rate_units_per_hour": {"published": rate_pub, "measured_span": rate_meas, "used": rate_used},
                     "units": units})
    eval_only = {p[len("eval_only_"):]: round(v, 1) for p, v in totals.items() if p.startswith("eval_only_")}
    totals = {p: {k: round(v, 1) for k, v in t.items()} for p, t in totals.items() if not p.startswith("eval_only_")}

    def verdict(high):
        if high <= planned:
            return "within the planned budget"
        return "between the planned budget and the stop rule" if high <= stop else "exceeds the stop rule"

    return {"basis": "measured = GPU smoke cell of the model on its eval tier (mean latency per item + one model load) x the "
                     "span-measured compute-unit rate of the tier when recorded, else the published rate; prior = the main study's "
                     "CoT mean latency (low) scaled by the output-token ratio (high), published rate. Items per plan from "
                     "configs/detection.yaml items.",
            "plans": counts, "rows": rows, "totals": totals, "eval_only_totals": eval_only, "planned": planned, "stop": stop,
            "verdict": {p: verdict(t["high"]) for p, t in totals.items()},
            "all_measured": all(r["basis"].startswith("measured") for r in rows),
            "basis_note": "measured_dev = the dev extraction cell (796 items) with the latest span rate of the tier; eval_only_totals = the "
                          "remaining cost of the eval partition under each plan once dev is extracted."}


def format_table(proj: dict) -> str:
    plans = list(proj["plans"])
    lines = [f"{'model':11s} {'tier':9s} {'basis':12s} {'s/item lo-hi':>14s} {'rate':>6s} "
             + " ".join(f"{'units ' + p + ' lo-hi':>18s}" for p in plans)]
    for r in proj["rows"]:
        s = r["seconds_per_item"]
        cells = " ".join(f"{str(r['units'][p]['low']):>8s}-{str(r['units'][p]['high']):<9s}" for p in plans)
        lines.append(f"{r['model']:11s} {r['tier']:9s} {r['basis']:12s} {str(s['low']):>7s}-{str(s['high']):<6s} "
                     f"{str(r['rate_units_per_hour']['used']):>6s} {cells}")
    for p in plans:
        c, t = proj["plans"][p], proj["totals"][p]
        lines.append(f"plan {p} ({c['name']}; {c['items_per_model']:,} items per model): total {t['low']} to {t['high']} units "
                     f"(eval only {proj['eval_only_totals'][p]}); planned {proj['planned']}, stop {proj['stop']}: {proj['verdict'][p]}")
    return "\n".join(lines)
