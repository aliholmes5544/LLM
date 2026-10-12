# TASK 05 — Variant derivation and meaning checks (Section 3.2.3)

**Goal of this task:** implement `scripts/05_derive_variants.py` and validate it on the
**development set only** (`dev` partition, and specifically its 100 `ephish_phish` items,
which are LLM-generated and personalized). Do **not** run it on `core_pos` yet. The
purpose is to calibrate thresholds and confirm the procedure before it touches test data.

## Inputs
- `data/processed/records.jsonl`, `data/processed/partitions.json`
- `configs/variants.yaml` (create; see schema below)
- Seed: `configs/data.yaml: seed`

## Outputs
- `data/processed/variants_dev.jsonl` — one row per variant:
  `variant_id, source_id, condition, body, subject, checks{...}, status (pass|regenerated|excluded)`
- `data/processed/obfuscation_log_dev.jsonl` — one row per edit:
  `variant_id, position, original_char, replacement, operation`
- `reports/variants_dev_report.json` — counts per condition: produced, failed each check,
  regenerated, excluded; similarity distributions (min/p5/median) per condition
- `reports/manual_review_sample_dev.csv` — stratified 10% sample per condition for two
  annotators: `variant_id, condition, original_body, variant_body, rating_A, rating_B, notes`

## Conditions (exactly four)
| key | family | intensity definition |
|---|---|---|
| `para_low`  | paraphrase  | 50% of sentences rewritten (seeded selection) |
| `para_high` | paraphrase  | 100% of sentences rewritten |
| `obf_low`   | obfuscation | 10% of eligible tokens perturbed |
| `obf_high`  | obfuscation | 30% of eligible tokens perturbed |

## Protected spans (both families)
Masked before transformation, restored verbatim after. Detect with regex + a small NER
(spaCy `en_core_web_sm` is acceptable): PERSON, ORG, DATE, TIME, MONEY, CARDINAL amounts,
email-like strings, and the neutral placeholder phrases "the link", "the attachment",
"the address". Record the span list per record. A variant missing any protected span fails.

## Paraphrasing
- Backend: llama.cpp via `llama-cpp-python`, GGUF model path from `configs/variants.yaml`.
  The model family must be **excluded from the detector set** (documented in the config).
  For the dev run on the author's CPU machine use a ≤4B instruction model, Q4_K_M.
- Sentence split with a deterministic splitter (regex on `.!?` + newline is acceptable).
- Per selected sentence, one prompt (see `prompts/paraphrase_v1.txt`, create it):
  "Rewrite the following sentence using different words. Keep exactly the same meaning,
  tone and level of formality. Do not add or remove information. Output only the rewritten
  sentence." Temperature 0.7, top_p 0.9, max_tokens = 3 × input tokens, fixed seed per
  (record, sentence index, attempt).
- Reassemble in original order; untouched sentences copied verbatim.

## Obfuscation (deterministic script, no model)
- Eligible token: alphabetic, ≥4 chars, not inside a protected span.
- Select `rate × n_eligible` tokens with the seeded RNG; each gets **one** operation drawn
  uniformly from: (1) homoglyph (fixed table, e.g. a→а, e→е, o→о, c→с, p→р, x→х, i→і),
  (2) digit lookalike (fixed map o→0, l→1, e→3, a→4, s→5), (3) zero-width space (U+200B)
  inserted after a random interior letter, (4) visible separator ("-" or ".") inserted after
  a random interior letter.
- Log every edit. The **integrity check** replays the log in reverse and must reproduce the
  original body exactly.

## Automatic checks (paraphrase)
- `sim_cos`: cosine of sentence embeddings (`all-mpnet-base-v2`) ≥ `thr_cos` (start 0.80)
- `len_ratio`: variant words / original words in [0.70, 1.40]
- `spans_ok`: all protected spans present
- `nli_ok`: for each rewritten sentence, cross-encoder NLI (`cross-encoder/nli-deberta-v3-base`
  or similar) gives entailment prob ≥ `thr_nli` (start 0.70) in both directions
- Fail → regenerate once (seed+1) → fail again → `excluded`.

## Calibration (this is why we run on dev first)
1. Produce all four conditions for the 100 dev `ephish_phish` items (400 variants).
2. Export the 10% manual sample; the author rates it (3-point: preserved / partly / not).
3. Choose `thr_cos` and `thr_nli` as the lowest values at which ≥95% of variants rated
   "preserved" pass the automatic checks. Write the chosen values to `configs/variants.yaml`
   and the calibration table to `reports/variants_calibration.json`.
4. Report in `docs/CHANGES_FOR_THESIS.md` the final thresholds, the exclusion rate per
   condition, and the dev manual-sample failure rate, so Section 3.2.3 can be updated.

## Definition of done
- Script runs end-to-end on dev with the seed and reproduces identical outputs on rerun.
- Integrity check passes for 100% of obfuscated variants.
- Reports written; no evaluation partition touched (assert at the top of the script).
