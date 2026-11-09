# TASK 08 — Two-stage indicator detector (supervisor-requested, exploratory)

Status: specification 2026-11-09. Requested by the supervisor after the step-07 scores were computed. **Exploratory and post-hoc**; declared as such in `docs/QUESTIONS.md` with its date and reason.

**Framing, and it is binding:** the two-stage pipeline is an **additional evaluated condition inside the existing framework**, not a proposed system. The thesis does not claim it is a better detector and performs no architecture tuning, no ablation and no fair-baseline exercise. Research questions RQ1–RQ4 are unchanged.

All rules in `CLAUDE.md` apply. The frozen artefacts of steps 05–07 are read-only: `results/raw/*`, `results/scores/*.csv`, `configs/*` and `prompts/*` of the main study must stay byte-identical, verified before and after.

---

## 1. The question this answers

> When the decision is forced through an explicit set of extracted indicators instead of a single end-to-end verdict, does it become **more or less robust to AI rewriting**?

Primary outcome: the **difference of robustness deltas** between the two-stage pipeline and the same model's direct `zero_shot` verdict, per condition.

Accuracy on originals is reported **descriptively only**. The thesis does not claim which architecture is more accurate: neither side was tuned for that comparison, and saying so is part of the write-up.

**Why the comparison is fair in the one respect that matters:** extraction uses the **same underlying model** as the direct verdict it is compared with, so a difference is attributable to the architecture rather than to model capability.

## 2. Scope (do not widen)

| Item | Value |
|---|---|
| Models | `qwen25-7b` (weak), `gemma2-9b` (strong), `gemma2-27b` (strongest, at ceiling) — three, no more |
| Tiers | `colab_t4` for the two 7B/9B models, `colab_l4` for `gemma2-27b`, matching their `eval_tier` |
| Extraction strategy | zero-shot only |
| Stage 2 | one logistic regression per model; no second LLM call |
| Partitions | `dev` (fit stage 2) and `eval` (report), including `gen_*` |
| Budget | ≈ 24 compute units (≈ 9.6 on T4, ≈ 14.5 on L4); stop and report if it passes 28 |

Three models span the range the question needs: does the architecture **compensate** for a weak model, and does it **cost** a strong one? `gemma2-27b` is the decisive case, because a model already at 0.979 sensitivity has nothing to gain and only accuracy to lose — the supervisor's architecture is most at risk there.

## 3. Indicator schema (`configs/twostage.yaml`, frozen with hash)

Combines the project's threat indicators with the generic attributes the supervisor named, so his proposal is represented as given.

**Threat indicators** (the eight frozen cue categories, as ternary values `yes` / `no` / `unclear`): `urgency`, `link_or_url`, `sender_domain_mismatch`, `credential_or_payment_request`, `grammar_anomaly`, `impersonation_authority`, `attachment`, `generic_greeting`.

**Generic text attributes** (supervisor's list): `sentiment` (`negative` / `neutral` / `positive`), `is_question` (bool), `is_complaint` (bool), `language_pattern` (`human_like` / `machine_like` / `unclear`), `register` (`informal` / `neutral` / `formal`).

No free-text field. No probability scores: a model's self-reported confidence is not calibrated and would add an uncontrolled variable.

## 4. Extraction prompt (`prompts/extract_indicators.txt`)

- Output **only** a JSON object with exactly the keys above; no prose, no code fence.
- Decoding identical to the study: greedy, `temperature = 0`, seed 2026, `max_tokens = 256`.
- **The prompt must not ask for, or hint at, a phishing verdict.** If the model volunteers one it is ignored; a check reports how often it happens.
- Developed on `dev` only, revised only for format compliance (never for accuracy), each revision logged with the dev parse-failure rate before and after. Frozen with a sha256.

**Parse failures:** strict `json.loads` on the first balanced object; a missing or out-of-vocabulary key makes the row `invalid`, scored as an incorrect prediction exactly as in step 06, with the rate reported per cell.

## 5. Stage 2

- Features: one-hot of every indicator (unclear and parse-failure encoded explicitly), no text features, no interactions.
- Fitted on the **`dev` extractions only** (796 items: originals and accepted dev variants). `train`/`valid` are not used, so no extraction run is needed on them.
- Hyper-parameter: C chosen on `dev` by cross-validation; **nothing is chosen on `eval`**.
- Threshold fixed at 0.5. The fitted model's sha256 is recorded; the model file stays out of git.

## 6. Runner `scripts/06_run_twostage.py`

Writes the **same row schema as every other detector**, so step 07 scores it with the existing code path:

`results/raw/twostage_{model}/lr/{partition}.jsonl` — `item_id`, `partition`, `condition`, `label_true`, `raw_output` (the JSON string), `label_pred`, `invalid`, `prompt_hash`, `config_hash`, `model_hash`, `n_prompt_tokens`, `n_output_tokens`, `latency_s`, `truncated_input`, `backend`, plus `parse_ok` and the parsed indicator columns.

Resumable, refuses to overwrite a finished eval file without `--force --reason`, refuses to run when configs or prompts differ from HEAD — the same guards as `06_run_detection.py`.

## 7. Scoring

- Scored by the existing `07_score.py` into **`results/scores/additional/twostage_{model}/`** with its own families `A-twostage-{model}`. The pre-registered families F-RQ1…F-RQ4 keep their exact test counts and Holm corrections.
- Reported per condition: sensitivity, specificity, Δsens, Δspec on the control, with 95 % cluster bootstrap CIs on the same clusters and the same seed.
- **Primary comparison:** difference of deltas, two-stage minus direct, per condition, with bootstrap CI and the two-sided bootstrap p defined in item 12(e).
- A descriptive note on where the two pipelines disagree, and the three indicators with the largest fitted coefficients.

## 8. Outputs

| Path | Content |
|---|---|
| `results/scores/additional/twostage_*/…csv` | metrics and deltas, same long format |
| `results/tables/tab_t12_twostage.tex` | one table: direct vs two-stage per model per condition, with the difference of deltas |
| `figures/ch04_f8_twostage_eng.png` | Δsens per condition, direct vs two-stage, three panels (one per model) |
| `reports/twostage_report.json` | parse-failure rates, volunteered-verdict rate, fitted coefficients, hashes, runtime, compute units |

Existing tables T1–T11 gain rows for the two-stage detector; **their existing values must be verified unchanged** and the verification recorded.

## 9. Order of work (one command each, stop and report between)

1. `configs/twostage.yaml`, extraction prompt, runner, tests. Verify the frozen artefacts are untouched. Commit.
2. Extraction smoke on `dev` (20 items × 3 models; the 27B on the L4 tier): parse-failure rate, volunteered verdicts, latency, and the measured compute-unit rate. Revise the prompt for format only; freeze; record hashes. Commit. **Gate: parse failures ≤ 10 % per cell.** Report the budget projection before any full run.
3. Full `dev` extraction (796 × 3); fit stage 2 per model; report dev performance and coefficients. Commit.
4. `eval` extraction (5,207 × 3): T4 run for `qwen25-7b` and `gemma2-9b`, then L4 run for `gemma2-27b`; integrity check. Commit.
5. Scoring, table T12, figure F8; verify every frozen CSV byte-identical. Commit; tag `v1.1.0-twostage`.
6. Write-up text for §3.5/§3.6, §4.5, §4.7, §4.8 and the shortened §5 future work, in `docs/CHANGES_FOR_THESIS.md`.

## 10. Definition of done

- Extraction prompt and config frozen with hashes; stage 2 fitted on `dev` only.
- `results/raw/twostage_*` complete, passing the integrity check.
- Every pre-registered CSV, family and Holm correction unchanged, verified.
- The deviation logged in `docs/QUESTIONS.md` item 12 with date, reason (supervisor request after scoring) and the exploratory label.
- Compute units consumed recorded.

## 11. Stop conditions

Stop and report rather than improvising if: parse failures exceed 10 % on dev after one prompt revision; the budget passes 28 compute units; or the eval extraction cannot complete before the compute credit runs out. A partial result reported honestly is better than a rushed one. If only two of the three models can be completed, keep `qwen25-7b` and `gemma2-27b`, the two ends of the range.
