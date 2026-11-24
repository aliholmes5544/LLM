#!/usr/bin/env python3
"""
09_thesis_figures.py — presentation-only thesis versions of the Chapter 4 figures F1 to F8 (QUESTIONS.md item 20,
2026-11-24). The committed figures under figures/ stay as they are; this script writes figures/thesis/ only.

How the data stay identical: the figure functions of scripts/07_tables_figures.py (F1 to F7) and
scripts/07_twostage_tables_figures.py (F8) are CALLED, with their save step intercepted, so every plotted artist is
built by the original selection code on the same CSV rows. This script then edits layout and wording only (axis-label
wording of the thesis, American spelling, legends moved off the data, more room where text overlapped) and saves each
figure as a 300 dpi PNG and a vector PDF under the same file name. Before saving, it (a) asserts that the values
carried by the plotted artists equal the rows selected from the CSVs (same count, same numbers) and (b) checks the
rendered layout programmatically: no two texts overlap (rotated texts tested as rotated rectangles), no legend covers a
data artist, every text lies inside the saved canvas. reports/thesis_figures_report.json records the input hashes, the
row counts, the check results and the output hashes. No existing file is modified.

Usage: python scripts/09_thesis_figures.py
"""
import importlib
import math
import re
import subprocess
import sys

import numpy as np
import pandas as pd

from common import ROOT, load_config, write_json
from scoring.cues import CATEGORIES
from scoring.output import sha256_file
from scoring.score import BASELINES, CONTROL, MODELS, PHISH_CONDITIONS, STRATEGIES

tf = importlib.import_module("07_tables_figures")
tsf = importlib.import_module("07_twostage_tables_figures")
plt, matplotlib = tf.plt, tf.matplotlib
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.image import AxesImage  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.text import Text  # noqa: E402
from matplotlib.transforms import Bbox  # noqa: E402

SCORES, ADDITIONAL = tf.SCORES, tf.SCORES / "additional"
OUT = ROOT / "figures" / "thesis"
REPORT = ROOT / "reports" / "thesis_figures_report.json"
SPELLING = [("e-mails", "emails"), ("E-mails", "Emails"), ("e-mail", "email"), ("E-mail", "Email"),
            ("generalisation", "generalization"), ("Generalisation", "Generalization")]
TOL = 1e-12

_captured = {}


def _capture(fig, name: str) -> str:
    """Replaces save_fig in the two source modules: keep the figure open and return the file name they would write."""
    _captured["fig"] = fig
    return f"ch04_{name}_eng.png"


tf.save_fig = _capture
tsf.save_fig = _capture


def git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def american(s: str) -> str:
    for a, b in SPELLING:
        s = s.replace(a, b)
    return s


# ---------------------------------------------------------------- artists -> plotted values

def errorbar_y(ax) -> list:
    return [float(v) for c in ax.containers if type(c).__name__ == "ErrorbarContainer" for v in c.lines[0].get_ydata()]


def bar_heights(ax) -> list:
    return [float(v) for c in ax.containers if type(c).__name__ == "BarContainer" for v in c.datavalues]


def point_lines(ax) -> list:
    """Line2D artists with exactly one data point (the scatter-like points of F5 baselines and F7)."""
    return [ln for ln in ax.lines if len(ln.get_xdata()) == 1]


def same_values(plotted: list, expected: list) -> dict:
    p, e = np.sort(np.asarray(plotted, dtype=float)), np.sort(np.asarray(expected, dtype=float))
    ok = len(p) == len(e) and bool(np.allclose(p, e, atol=TOL, rtol=0, equal_nan=True))
    return {"n_plotted": int(len(p)), "n_expected": int(len(e)), "equal": ok,
            "max_abs_diff": float(np.max(np.abs(p - e))) if ok and len(p) else None}


# ---------------------------------------------------------------- layout checks

def _rot_polygon(t: Text, renderer) -> np.ndarray:
    """Corners (display px) of the text box as a rotated rectangle: the rotated size at the AABB centre."""
    bb = t.get_window_extent(renderer)
    ang = math.radians(t.get_rotation())
    if abs(math.sin(ang)) < 1e-9:
        return np.array([[bb.x0, bb.y0], [bb.x1, bb.y0], [bb.x1, bb.y1], [bb.x0, bb.y1]])
    rot = t.get_rotation()
    t.set_rotation(0)
    bb0 = t.get_window_extent(renderer)
    t.set_rotation(rot)
    w, h = bb0.width, bb0.height
    cx, cy = (bb.x0 + bb.x1) / 2, (bb.y0 + bb.y1) / 2
    c, s = math.cos(ang), math.sin(ang)
    corners = np.array([[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]])
    R = np.array([[c, -s], [s, c]])
    return corners @ R.T + np.array([cx, cy])


def _polys_intersect(a: np.ndarray, b: np.ndarray, shrink: float = 0.75) -> bool:
    """Separating-axis test for two convex quadrilaterals, each shrunk by `shrink` px towards its centre."""
    def shr(p):
        c = p.mean(axis=0)
        d = p - c
        n = np.linalg.norm(d, axis=1, keepdims=True)
        return c + d * np.maximum(n - shrink, 0) / np.where(n == 0, 1, n)
    a, b = shr(a), shr(b)
    for poly in (a, b):
        for i in range(4):
            edge = poly[(i + 1) % 4] - poly[i]
            axis = np.array([-edge[1], edge[0]])
            pa, pb = a @ axis, b @ axis
            if pa.max() <= pb.min() or pb.max() <= pa.min():
                return False
    return True


def _undrawn_tick_labels(fig) -> set:
    """ids of tick labels whose tick lies outside the axis view interval (they exist but are never drawn)."""
    out = set()
    for ax in fig.axes:
        for axis in (ax.xaxis, ax.yaxis):
            lo, hi = sorted(axis.get_view_interval())
            for ticks in (axis.get_major_ticks(), axis.get_minor_ticks()):
                for tick in ticks:
                    loc = tick.get_loc()
                    if not (lo - 1e-9 <= loc <= hi + 1e-9):
                        out.add(id(tick.label1)); out.add(id(tick.label2))
    return out


def _texts(fig, renderer=None) -> list:
    """Visible, non-empty, drawn texts with a finite, non-degenerate extent."""
    out = []
    skip = _undrawn_tick_labels(fig)
    for t in fig.findobj(Text):
        if not t.get_visible() or not t.get_text().strip() or id(t) in skip:
            continue
        if renderer is not None:
            bb = t.get_window_extent(renderer)
            if not (np.isfinite([bb.x0, bb.y0, bb.x1, bb.y1]).all() and bb.width > 0 and bb.height > 0):
                continue
        out.append(t)
    return out


def _legends(fig) -> list:
    legs = list(fig.legends)
    for ax in fig.axes:
        if ax.get_legend() is not None:
            legs.append(ax.get_legend())
    return legs


def _hits(bb: Bbox, other: Bbox) -> bool:
    inter = Bbox.intersection(bb, other)
    return inter is not None and inter.width > 0.5 and inter.height > 0.5


def _segments_hit(bb: Bbox, pts: np.ndarray, margin: float) -> bool:
    """True when a marker (expanded by `margin` px) or a straight segment between consecutive points enters bb."""
    big = Bbox.from_extents(bb.x0 - margin, bb.y0 - margin, bb.x1 + margin, bb.y1 + margin)
    pts = pts[np.isfinite(pts).all(axis=1)]
    if len(pts) == 0:
        return False
    if np.any((pts[:, 0] >= big.x0) & (pts[:, 0] <= big.x1) & (pts[:, 1] >= big.y0) & (pts[:, 1] <= big.y1)):
        return True
    for a, b in zip(pts[:-1], pts[1:]):
        s = a[None, :] + (b - a)[None, :] * np.linspace(0, 1, 40)[:, None]
        if np.any((s[:, 0] >= bb.x0) & (s[:, 0] <= bb.x1) & (s[:, 1] >= bb.y0) & (s[:, 1] <= bb.y1)):
            return True
    return False


def _legend_covers_data(bb: Bbox, ax, renderer) -> bool:
    """Bars and images by their boxes; lines and error-bar segments by their actual points and segments."""
    for p in ax.patches:
        if isinstance(p, Rectangle) and p.get_visible() and p.get_width() and p.get_height() and _hits(bb, p.get_window_extent(renderer)):
            return True
    for im in ax.images:
        if isinstance(im, AxesImage) and _hits(bb, im.get_window_extent(renderer)):
            return True
    for ln in ax.lines:
        if not ln.get_visible() or not len(ln.get_xdata()):
            continue
        pts = ln.get_transform().transform(np.column_stack([np.asarray(ln.get_xdata(), float), np.asarray(ln.get_ydata(), float)]))
        margin = (ln.get_markersize() * ax.figure.dpi / 72) / 2 + 1 if ln.get_marker() not in (None, "None", "") else 1
        if _segments_hit(bb, pts, margin):
            return True
    for col in ax.collections:
        if isinstance(col, LineCollection) and col.get_visible():
            for seg in col.get_segments():
                if _segments_hit(bb, col.get_transform().transform(np.asarray(seg, float)), 1):
                    return True
    return False


def _legend_text_ids(legs) -> dict:
    ids = {}
    for k, leg in enumerate(legs):
        for t in leg.findobj(Text):
            ids[id(t)] = k
    return ids


def layout_check(fig) -> dict:
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    texts = _texts(fig, r)
    legs = _legends(fig)
    leg_of = _legend_text_ids(legs)
    polys = [_rot_polygon(t, r) for t in texts]
    overlaps = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if id(texts[i]) in leg_of and leg_of[id(texts[i])] == leg_of.get(id(texts[j])):
                continue                                           # entries inside the same legend
            if _polys_intersect(polys[i], polys[j]):
                overlaps.append([texts[i].get_text()[:40], texts[j].get_text()[:40]])
    legend_hits = []
    for leg in legs:
        lb = leg.get_window_extent(r)
        axes = fig.axes if leg in fig.legends else [leg.axes]
        for ax in axes:
            if _legend_covers_data(lb, ax, r):
                legend_hits.append({"legend": [t.get_text() for t in leg.get_texts()][:2], "axes": ax.get_title() or ax.get_ylabel()[:30]})
    # texts crossing a legend box (a legend over a label), excluding the legend's own texts
    text_legend_hits = []
    for leg_k, leg in enumerate(legs):
        lb = leg.get_window_extent(r)
        for t, poly in zip(texts, polys):
            if leg_of.get(id(t)) == leg_k:
                continue
            tb = Bbox.from_extents(poly[:, 0].min(), poly[:, 1].min(), poly[:, 0].max(), poly[:, 1].max())
            if _hits(lb, tb):
                text_legend_hits.append(t.get_text()[:40])
    tight = fig.get_tightbbox(r).transformed(fig.dpi_scale_trans)     # inches -> display px
    outside = [t.get_text()[:40] for t, poly in zip(texts, polys)
               if poly[:, 0].min() < tight.x0 - 0.5 or poly[:, 0].max() > tight.x1 + 0.5 or poly[:, 1].min() < tight.y0 - 0.5 or poly[:, 1].max() > tight.y1 + 0.5]
    return {"n_texts": len(texts), "n_legends": len(legs), "text_overlaps": overlaps, "legend_over_data": legend_hits,
            "legend_over_text": text_legend_hits, "text_outside_canvas": outside,
            "ok": not (overlaps or legend_hits or text_legend_hits or outside)}


def respell(fig) -> int:
    """American spelling in every non-tick text; tick labels are asserted free of the words (they come from fixed maps)."""
    n = 0
    tick_texts = set()
    for ax in fig.axes:
        for t in ax.get_xticklabels() + ax.get_yticklabels():
            tick_texts.add(id(t))
            for a, _ in SPELLING:
                if a in t.get_text():
                    raise SystemExit(f"tick label needs respelling: {t.get_text()!r}")
    for t in _texts(fig):
        if id(t) in tick_texts:
            continue
        new = american(t.get_text())
        if new != t.get_text():
            t.set_text(new)
            n += 1
    return n


def lowest_edge(fig, exclude=()) -> float:
    """Lowest y (figure fraction) reached by any axes or text of the figure, for placing a legend below everything."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    ys = [ax.get_window_extent(r).y0 for ax in fig.axes]
    ys += [t.get_window_extent(r).y0 for t in _texts(fig) if t not in exclude]
    return min(ys) / fig.bbox.height


def legend_below(fig, handles, labels, ncol: int, gap: float = 0.03, **kw):
    y = lowest_edge(fig) - gap
    return fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, y), ncol=ncol, frameon=False, **kw)


def save(fig, name: str) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / name
    pdf = png.with_suffix(".pdf")
    fig.savefig(png, dpi=300, bbox_inches="tight", facecolor="white", metadata={"Software": None})
    fig.savefig(pdf, bbox_inches="tight", facecolor="white", metadata={"Creator": None, "Producer": None, "CreationDate": None})
    plt.close(fig)
    return {str(png.relative_to(ROOT)): sha256_file(png), str(pdf.relative_to(ROOT)): sha256_file(pdf)}


# ---------------------------------------------------------------- the eight figures

def f1(M):
    name = tf.fig_f1(M)
    fig = _captured["fig"]
    ax = fig.axes[0]
    P = M[(M["analysis"] == "primary") & (M["strategy"] == "zero_shot") & (M["metric"] == "sens")]
    exp = [P[(P["detector"] == m) & (P["condition"] == c)]["value"].item() for m in MODELS for c in ["original"] + PHISH_CONDITIONS]
    chk = same_values(bar_heights(ax), exp)
    ax.set_xlabel("Input condition (core phishing emails)")
    return name, fig, chk


def f2(D):
    name = tf.fig_f2(D)
    fig = _captured["fig"]
    DP = D[(D["analysis"] == "primary") & (D["kind"] == "llm")]
    exp, plotted = [], []
    for ax, cond in zip(fig.axes[:5], PHISH_CONDITIONS + [CONTROL]):
        mat = DP[DP["condition"] == cond].pivot(index="detector", columns="strategy", values="delta").loc[MODELS, STRATEGIES]
        exp += mat.values.ravel().tolist()
        plotted += np.asarray(ax.images[0].get_array()).ravel().tolist()
        for t in ax.texts:
            if re.fullmatch(r"[+-]0\.00", t.get_text()):
                t.set_text("0.00")
    return name, fig, same_values(plotted, exp)


def f3(M):
    name = tf.fig_f3(M)
    fig = _captured["fig"]
    P = M[(M["analysis"] == "primary") & (M["strategy"] == "zero_shot") & (M["metric"] == "sens")]
    conds = ["original"] + PHISH_CONDITIONS
    exp = [P[(P["detector"] == m) & (P["condition"] == c)]["value"].item() for m in ("qwen25-7b", "qwen25-14b", "gemma2-9b", "gemma2-27b") for c in conds]
    plotted = [v for ax in fig.axes for v in errorbar_y(ax)]
    return name, fig, same_values(plotted, exp)


def f4(D):
    name = tf.fig_f4(D)
    fig = _captured["fig"]
    DP = D[(D["analysis"] == "primary") & (D["kind"] == "llm")]
    exp = [DP[(DP["condition"] == c) & (DP["strategy"] == s) & (DP["detector"] == m)]["delta"].item()
           for c in ("para_high", "obf_high") for s in STRATEGIES for m in MODELS]
    plotted = [v for ax in fig.axes for v in errorbar_y(ax)]
    chk = same_values(plotted, exp)
    leg = fig.axes[1].get_legend()
    handles, labels = fig.axes[1].get_legend_handles_labels()
    leg.remove()
    legend_below(fig, handles, labels, ncol=4, fontsize=8, title="strategy", title_fontsize=8)
    return name, fig, chk


def f5(F):
    name = tf.fig_f5(F)
    fig = _captured["fig"]
    exp, plotted = [], []
    for ax, cond in zip(fig.axes[:2], ("para_high", "obf_high")):
        exp += F[f"delta_sens_{cond}"].astype(float).tolist()
        plotted += errorbar_y(ax) + [float(ln.get_ydata()[0]) for ln in point_lines(ax) if ln.get_marker() == "x"]
    chk = same_values(plotted, exp)
    fig.set_size_inches(9.0, 3.8)
    fig.subplots_adjust(wspace=0.32, bottom=0.17)
    fig.supxlabel("Median latency per email (s)", fontsize=9, y=0.0)
    leg = fig.legends[0]                                   # rebuilt below the x label with the same handles and labels
    handles, labels = leg.legend_handles, [t.get_text() for t in leg.get_texts()]
    leg.remove()
    legend_below(fig, handles, labels, ncol=5, fontsize=7)
    return name, fig, chk


def f6(cues_c):
    name = tf.fig_f6(cues_c)
    fig = _captured["fig"]
    chg = cues_c.groupby(["condition", "category", "outcome"], sort=False)[["n_pairs", "lost", "gained"]].sum().reset_index()
    chg["net"] = (chg["gained"] - chg["lost"]) / chg["n_pairs"]
    exp = [chg[(chg["condition"] == c) & (chg["outcome"] == oc) & (chg["category"] == cat)]["net"].item()
           for c in ("para_high", "obf_high") for oc in ("stayed_correct", "flipped_to_incorrect", "stayed_incorrect", "flipped_to_correct")
           for cat in CATEGORIES]
    plotted = [v for ax in fig.axes for v in bar_heights(ax)]
    chk = same_values(plotted, exp)
    fig.set_size_inches(10.5, 4.0)
    for ax in fig.axes:
        handles, labels = ax.get_legend_handles_labels()
        ax.get_legend().remove()
        title = ax.get_title()
        ax.set_title("")
        ax.legend(handles, labels, fontsize=7, ncol=2, loc="lower left", bbox_to_anchor=(0, 1.01), frameon=False,
                  title=title, title_fontsize=9, alignment="left")
    return name, fig, chk


def f7(M):
    name = tf.fig_f7(M)
    fig = _captured["fig"]
    P = M[M["analysis"] == "primary"].set_index(["detector", "strategy", "metric", "condition"])
    specs = [("sens", "original", "gen_sens", "gen_phish"), ("spec", "original_core_neg", "gen_spec", "gen_legit")]
    exp_x, exp_y, plotted_x, plotted_y = [], [], [], []
    for ax, (xm, xc, ym, yc) in zip(fig.axes, specs):
        pts = point_lines(ax)
        for (det, s), ln in zip(tf.ref_cells(), pts):
            exp_x.append(P.at[(det, s, xm, xc), "value"]); exp_y.append(P.at[(det, s, ym, yc), "value"])
            plotted_x.append(float(ln.get_xdata()[0])); plotted_y.append(float(ln.get_ydata()[0]))
            ln.set_label(tf.NAME[det])
        for t in list(ax.texts):                       # the per-point annotations are replaced by one shared legend
            t.remove()
    chk = {"x": same_values(plotted_x, exp_x), "y": same_values(plotted_y, exp_y)}
    chk["equal"] = chk["x"]["equal"] and chk["y"]["equal"]
    chk["n_plotted"], chk["n_expected"] = chk["y"]["n_plotted"], chk["y"]["n_expected"]
    fig.set_size_inches(8.6, 4.3)
    fig.subplots_adjust(wspace=0.38)
    ax0, ax1 = fig.axes
    ax0.set_xlabel("Sensitivity on the spear-phishing originals"); ax0.set_ylabel("Sensitivity on the generalization set")
    ax1.set_xlabel("Specificity on the core negatives"); ax1.set_ylabel("Specificity on the generalization set")
    # the six models and the ensemble are identified by colour and marker in one shared legend; the three baselines share
    # the grey square of the committed figure, so each keeps a short label with a leader line
    offsets = {0: {"baseline_tfidf_lr": (-12, -13), "baseline_tfidf_svm": (-12, -13), "baseline_distilbert": (12, -13)},
               1: {"baseline_tfidf_lr": (-12, -13), "baseline_tfidf_svm": (-12, 9), "baseline_distilbert": (-12, -13)}}
    for k, ax in enumerate((ax0, ax1)):
        for (det, s), ln in zip(tf.ref_cells(), point_lines(ax)):
            if det in BASELINES:
                dx, dy = offsets[k][det]
                ax.annotate(tf.NAME[det], (ln.get_xdata()[0], ln.get_ydata()[0]), xytext=(dx, dy), textcoords="offset points",
                            fontsize=7, color="#333333", ha="right" if dx < 0 else "left", va="center",
                            arrowprops={"arrowstyle": "-", "color": tf.GREY, "lw": 0.6, "shrinkA": 0, "shrinkB": 4})
    handles = [ln for (det, s), ln in zip(tf.ref_cells(), point_lines(ax0)) if det not in BASELINES]
    handles.append(Line2D([], [], marker="s", color=tf.GREY, ls="", ms=6, label="supervised baselines (labeled)"))
    legend_below(fig, handles, [h.get_label() for h in handles], ncol=4, fontsize=8, handletextpad=0.4, columnspacing=1.2)
    return name, fig, chk


def f8():
    tcfg = load_config("twostage.yaml")
    models = list(tcfg["models"])
    fits = [v["strategy_key"] for v in sorted(tcfg["fits"].values(), key=lambda v: not v.get("primary"))]
    M8, D8, _ = tsf.load(models, fits)
    name = tsf.fig_f8(D8, models, fits)
    fig = _captured["fig"]
    DP = D8[D8["analysis"] == "primary"].set_index(["model", "strategy", "condition"])
    exp = [DP.at[(m, s, c), "delta"] for m in models for s in [tsf.DIRECT] + fits for c in tsf.CONDITIONS]
    plotted = [v for ax in fig.axes for v in errorbar_y(ax)]
    inputs = [SCORES / "deltas_long.csv"] + [ADDITIONAL / f"{tsf.TWOSTAGE_PREFIX}{m}" / "deltas_long.csv" for m in models]
    return name, fig, same_values(plotted, exp), inputs


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", default=None, help="also write every figure (checks passed or not) as PNG into this directory, for inspection")
    a = ap.parse_args()
    M = pd.read_csv(SCORES / "metrics_long.csv"); D = pd.read_csv(SCORES / "deltas_long.csv")
    F = pd.read_csv(SCORES / "frontier.csv"); cues_c = pd.read_csv(SCORES / "cues_change.csv")
    inputs = {str(p.relative_to(ROOT)): sha256_file(p) for p in (SCORES / "metrics_long.csv", SCORES / "deltas_long.csv",
                                                                   SCORES / "frontier.csv", SCORES / "cues_change.csv")}
    figures, all_ok = {}, True
    jobs = [("F1", lambda: f1(M)), ("F2", lambda: f2(D)), ("F3", lambda: f3(M)), ("F4", lambda: f4(D)), ("F5", lambda: f5(F)),
            ("F6", lambda: f6(cues_c)), ("F7", lambda: f7(M)), ("F8", f8)]
    for label, job in jobs:
        res = job()
        name, fig, chk = res[0], res[1], res[2]
        if label == "F8":
            inputs.update({str(p.relative_to(ROOT)): sha256_file(p) for p in res[3]})
        n_respelled = respell(fig)
        lay = layout_check(fig)
        ok = bool(chk["equal"]) and lay["ok"]
        all_ok &= ok
        entry = {"source": name, "values_equal_selected_rows": chk, "respelled_texts": n_respelled, "layout": lay}
        if a.draft:
            from pathlib import Path
            Path(a.draft).mkdir(parents=True, exist_ok=True)
            fig.savefig(Path(a.draft) / name, dpi=150, bbox_inches="tight", facecolor="white")
        if ok:
            entry["outputs"] = save(fig, name)
        else:
            plt.close(fig)
        figures[label] = entry
        print(f"{label} {name}: values {'OK' if chk['equal'] else 'MISMATCH'} ({chk['n_plotted']} plotted / {chk['n_expected']} expected); "
              f"layout {'OK' if lay['ok'] else 'PROBLEM'} {'' if lay['ok'] else {k: v for k, v in lay.items() if v and k != 'ok'}}")
    report = {"purpose": "presentation-only thesis versions of F1 to F8 (QUESTIONS.md item 20); the committed figures are unchanged",
              "inputs": inputs, "figures": figures, "all_ok": all_ok, "matplotlib": matplotlib.__version__,
              "git_commit": git("rev-parse", "--short", "HEAD")}
    write_json(REPORT, report)
    print(f"{'all figures OK' if all_ok else 'PROBLEMS, see report'} -> {OUT.relative_to(ROOT)}/, {REPORT.relative_to(ROOT)}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
