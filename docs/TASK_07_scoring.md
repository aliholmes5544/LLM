# TASK 07 — Scoring: metrics, robustness deltas, inference, secondary analyses

Status: specification approved 2026-11-01. Implements the scoring stage of the evaluation framework. Produces every number, table and figure of Chapter 4. Follows the pre-registered plan in `docs/QUESTIONS.md` item 12 verbatim; any deviation is logged there with date and reason **before** the affected number is computed.

All rules in `CLAUDE.md` apply. Step 07 **reads** results and **never** touches `results/raw/`, prompts, configs or data. It is computed once; a re-run must reproduce every number bit-for-bit (asserted by a test).

---

## 0. Inputs (read-only; assert hashes from `reports/integrity_check.json` before scoring)

| Input | Use |
|---|---|
| `results/raw/{model}/{strategy}/eval.jsonl` (24 files) | detector predictions |
| `results/raw/baseline_{tfidf_lr,tfidf_svm,distilbert}/supervised/eval.jsonl` (3 files) | baseline predictions (+ `score`) |
| `data/processed/partitions.json`, `data/processed/variants_eval.jsonl` | item → partition, condition, **source e-mail id** (cluster) |
| `reports/detection_run_report.json`, `reports/baselines_report.json` | per-cell latency (item 12d) |
| `results/smoke_dev/`, `results/smoke_gpu/` (dev only) | building the CoT cue lexicon (item 12b) before it touches eval |
| `docs/QUESTIONS.md` item 12 | the plan |

Research questions (thesis numbering, PROJECT_STATE section 2 and Table 3.1; relabelled 2026-11-01, QUESTIONS.md item 15a): **RQ1** effectiveness (capability on core originals and the generalisation set; descriptive with CIs, no test family); **RQ2** comparison across open models and baselines (test family = the two size pairs only); **RQ3** zero-shot vs prompt-engineered (reference condition: `zero_shot`); **RQ4** robustness of open-weight detectors to AI-generated paraphrase/obfuscation variants (the headline family).

## 1. Item classes and pairing

- **Phishing originals:** `core_pos`. **Phishing variants:** accepted `core_pos` × {`para_low`, `para_high`, `obf_low`, `obf_high`}.
- **Legitimate originals:** `core_neg`, `ctrl_modern_legit`. **Legitimate variants:** accepted `ctrl_para_legit` × `para_high`.
- **Generalisation:** `gen_phish`, `gen_legit` — scored separately, **never pooled** with the core set.
- **Pairing:** a variant is paired with its own original. Every robustness delta is computed on the **paired subset** (originals that have an accepted variant in that condition), so original and variant rates refer to the same e-mails.
- **Cluster:** the source e-mail id. All variants of one original belong to its cluster.

## 2. Primary metrics (per detector × strategy; baselines have one "strategy" = `supervised`)

| Metric | Definition |
|---|---|
| `sens(c)` | sensitivity (recall on phishing) under condition c ∈ {original, para_low, para_high, obf_low, obf_high} |
| `spec(c)` | specificity (recall on legitimate) under c ∈ {original_core_neg, original_ctrl_modern, para_high_ctrl} |
| `acc`, `bal_acc`, `f1_phish` | on **core originals only** (core_pos + core_neg + ctrl_modern_legit) — the "baseline capability" row |
| `invalid_rate` | share of invalid outputs per cell (and per condition) |
| **`Δsens(c)`** | `sens(original, paired) − sens(c)` — **the primary outcome** (RQ4) |
| **`Δspec(para_high_ctrl)`** | `spec(original, paired) − spec(para_high_ctrl)` — the control delta: a detector that "fails" on paraphrased legitimate mail is not detecting phishing but paraphrase |
| `gen_sens`, `gen_spec` | on `gen_phish`, `gen_legit` |

Invalid predictions are scored as **incorrect** in the primary analysis. A **sensitivity analysis** repeats every table with invalid items excluded (reported in an appendix table; headline numbers come from the primary analysis).

## 3. Inference (item 12e, no deviation)

- **Cluster bootstrap** CIs (95 %, percentile): resample clusters (source e-mails) with replacement, `B = 2000`, `seed = 2026`, for every metric and every delta. One RNG stream per table, seeded deterministically from the table name, so tables are independent of execution order.
- **McNemar** (exact binomial on discordant pairs) for every paired original-vs-variant comparison (per cell × condition).
- **Holm** correction within each family, uncorrected p also shown. Primary families (QUESTIONS.md item 15a, 2026-11-01): **F-RQ4** = all paired original-vs-variant McNemar tests under `zero_shot` (6 models × 4 phishing conditions + 6 control tests = 30), the headline family; **F-RQ2** = size contrasts (qwen 7B vs 14B, gemma 9B vs 27B) on Δsens per phishing condition under `zero_shot` (8), tested by cluster-bootstrap difference of deltas; **F-RQ3** = strategy-vs-`zero_shot` contrasts per model on Δsens(para_high) and Δsens(obf_high) (3 strategies × 6 models × 2 conditions = 36), same bootstrap contrast. RQ1 has no test family. Secondary families (item 15b), Holm within each: the McNemar tests of each other strategy (one family per strategy), of the three baselines (one family) and of the ensemble (one family). **p of a bootstrap contrast** (item 15c): two-sided percentile p = 2 × min(P(contrast ≤ 0), P(contrast ≥ 0)), floored at 1/B; the CI is the primary report.
- Effect sizes: differences of proportions with CIs; no p-value is reported without its effect size.
- Power note (descriptive, for §4.8; item 15f): a priori, assume 10 % discordant pairs and report the McNemar power for a 5-point paired drop with 334 paired phishing originals at α = 0.05 (state the computed figure); also report the observed discordance of the `zero_shot` cells post hoc as a descriptive check, labelled as such.

## 4. Secondary analyses (item 12 a–d; pre-registered, computed after §2–3, nothing re-tuned)

- **(a) Ensemble:** per strategy, majority vote of the six detectors; invalid = abstention; 3–3 or < 4 valid votes = invalid. Scored exactly as a seventh detector in every table.
- **(b) CoT cue analysis:** lexicon (regex per category: urgency, link/URL, sender/domain mismatch, credential/payment request, grammar/spelling, impersonation/authority, attachment, generic greeting) **built and frozen on dev CoT outputs** (`results/smoke_*`), hash recorded, then applied to eval `cot` raw outputs. Report: cue frequency per model × condition; for each original–variant pair, cue presence change, split by prediction outcome (stayed correct / flipped to incorrect / stayed incorrect / flipped to correct). One figure, one table.
- **(c) Hard core:** under `zero_shot`, items misclassified by all six language models (baselines excluded; invalid counts as misclassified) vs by none; describe by condition, body length, source, partition. Seeded (2026) stratified sample of **30** all-six failures, strata = the four phishing conditions, allocation proportional to the failures per condition with a minimum of 5 per condition when available (item 15e), → `reports/hardcore_sample.csv` with columns for the author's manual coding (`failure_type`, `note`), plus a one-page coding guide. Descriptive only.
- **(d) Cost–robustness frontier:** x = median latency per inference (GPU, from the run reports), y = Δsens(para_high) (and obf_high as a second panel), one point per model × strategy; baselines as reference marks.

## 5. Outputs

| Path | Content |
|---|---|
| `results/scores/metrics_long.csv` | one row per (detector, strategy, partition_set, condition, metric, n, value, ci_lo, ci_hi, analysis ∈ {primary, no_invalid}) |
| `results/scores/deltas_long.csv` | one row per (detector, strategy, condition, n_pairs, delta, ci_lo, ci_hi, mcnemar_p, holm_p, family) |
| `results/scores/contrasts.csv` | RQ2 and RQ3 contrasts with CIs, bootstrap p and Holm p |
| `results/scores/ensemble_*.csv`, `cues_*.csv`, `hardcore_*.csv`, `frontier.csv` | secondary analyses |
| `results/tables/tab_*.tex` | booktabs tables ready for `\input` (labels `tab:...` chosen by the author later; no `\section` or `\caption` inside the file, caption text proposed in the report) |
| `figures/ch04_*_eng.png` | 300 dpi, consistent style, colour-blind-safe palette, no title inside the image; one PNG per figure listed in §6 |
| `reports/scoring_report.json` | everything above in machine form + input hashes + lexicon hash + runtime |
| `docs/CHANGES_FOR_THESIS.md` | entry with the headline numbers and the wording for §4.3 (metrics/statistics) and §4.5 (results) |

## 6. Tables and figures to produce (Chapter 4 skeleton)

Tables: (T1) capability on core originals, all detectors + baselines; (T2) sens by condition, `zero_shot`, with CIs — **the main table**; (T3) Δsens and Δspec with CIs, McNemar, Holm, `zero_shot`; (T4) same as T3 per strategy (one block per strategy); (T5) size contrasts (RQ2); (T6) strategy contrasts (RQ3); (T7) invalid rates per cell; (T8) generalisation set; (T9) ensemble; (T10) cue analysis; (T11) hard-core description; (A1) sensitivity analysis without invalid.

Figures: (F1) sens by condition, grouped bars per model, `zero_shot`; (F2) Δsens heat-map model × strategy × condition; (F3) size effect (two paired lines); (F4) strategy effect; (F5) cost–robustness frontier; (F6) cue-change by outcome; (F7) generalisation vs core.

## 7. Scripts

| script | does |
|---|---|
| `scripts/07_build_items.py` | joins raw rows with partitions/variants → `results/scores/items.parquet` (one row per prediction with cluster id, condition, truth); asserts 27 files × 5,207 rows and input hashes |
| `scripts/07_score.py` | §2–3 → metrics_long, deltas_long, contrasts, report |
| `scripts/07_secondary.py` | §4 (a)–(d); builds and freezes the lexicon from dev first |
| `scripts/07_tables_figures.py` | §5–6 |
| `tests/test_scoring.py` | metric functions on toy data with hand-computed answers; bootstrap determinism; re-run reproduces `metrics_long.csv` exactly |

## 8. Order of work

1. `07_build_items.py` + tests. Commit. **Still no metric computed.**
2. Build and freeze the cue lexicon on dev (hash). Commit.
3. `07_score.py` → primary tables; `07_secondary.py`; `07_tables_figures.py`. Commit **once** with "Step 07: scores computed (first and only computation)".
4. Report to the author: T1–T3 and F1 first, with a plain-language summary; then the rest.

## 9. Definition of done

- Every number in Chapter 4 traceable to a row in `results/scores/*.csv` and to a script + commit.
- Re-running step 07 reproduces all CSVs byte-identically (test passes).
- No change to raw results, prompts, configs or the pre-registered plan; any deviation logged in item 12 with date and reason.
- `figures/ch04_*_eng.png` and `results/tables/tab_*.tex` ready for the thesis repository.
