# SpearShift: reproducibility package

How every table and figure of Chapter 4 is produced, from which file, by which script, at which commit; the
pinned environment; the hashes of the fixed artefacts; the checks that confirm a re-run; and the disclosure of
AI assistance. Written 2026-11-01 at tag v1.0.0-thesis. Repository: https://github.com/aliholmes5544/LLM
(tags v0.6-detection-ready to v1.0.0-thesis).

## 1. Tables and figures of Chapter 4

All tables and figures are written by `scripts/07_tables_figures.py` from the CSVs under `results/scores/`;
the script computes nothing new except pooling over models for the cue table and figure. The CSVs were computed
once, at commit e18b66f (tag v0.7.1-scored, 2026-11-01), by `scripts/07_score.py` (primary tables) and
`scripts/07_secondary.py` (secondary analyses); `reports/hardcore_sample.csv` was extended at 75d9acb (item 17)
without changing any other file. The tables and figures were regenerated at 75d9acb and are byte-identical to
the e18b66f versions; their sha256 values are in `reports/tables_figures_report.json` (first 16 hex digits
below). Tables are booktabs bodies without caption or label; figures are 300 dpi PNG, palette in fixed model
order.

| item | content | input CSV (results/scores/) | producing script of the CSV | output file | sha256 (16) |
|---|---|---|---|---|---|
| T1 | capability on the 1,670 core originals: accuracy, balanced accuracy, F1, sensitivity, specificity (core, modern), invalid rate; LLMs zero-shot, ensemble, baselines | metrics_long.csv | 07_score.py | results/tables/tab_t1_capability.tex | 09d9e6b3d1d983bf |
| T2 | sensitivity by condition, zero-shot, 95% cluster-bootstrap CIs | metrics_long.csv | 07_score.py | results/tables/tab_t2_sens_by_condition.tex | f71e2a9d7bf26905 |
| T3 | paired deltas, zero-shot (family F-RQ4): delta, CI, discordant pairs, exact McNemar p, Holm p | deltas_long.csv | 07_score.py | results/tables/tab_t3_deltas_zero_shot.tex | df378092a51255bf |
| T4 | paired deltas by strategy (families S-few_shot, S-cot, S-role) | deltas_long.csv | 07_score.py | results/tables/tab_t4_deltas_by_strategy.tex | b2feda818620f471 |
| T5 | size contrasts (F-RQ2): Qwen 7B vs 14B, Gemma 9B vs 27B | contrasts.csv | 07_score.py | results/tables/tab_t5_size_contrasts.tex | 5457e6ab62d9937b |
| T6 | strategy contrasts (F-RQ3): each strategy vs zero-shot, para_high and obf_high | contrasts.csv | 07_score.py | results/tables/tab_t6_strategy_contrasts.tex | 7dc9730fb486a128 |
| T7 | invalid-output rates per cell and item group | metrics_long.csv | 07_score.py | results/tables/tab_t7_invalid_rates.tex | 7097a2c1513e8faf |
| T8 | generalisation set (E-PhishLLM): sensitivity and specificity against the core | metrics_long.csv | 07_score.py | results/tables/tab_t8_generalisation.tex | ca765cdaba5215b0 |
| T9 | majority ensemble: vote composition and metrics per strategy | ensemble_votes.csv, metrics_long.csv | 07_secondary.py, 07_score.py | results/tables/tab_t9_ensemble.tex | a1e407b5faa9f91d |
| T10 | CoT cue frequencies by category and item group, pooled over models | cues_frequency.csv | 07_secondary.py | results/tables/tab_t10_cues.tex | f0b54c0e1b74a03a |
| T11 | hard core: items missed by all six vs by none, per item group | hardcore_summary.csv | 07_secondary.py | results/tables/tab_t11_hardcore.tex | e7ecb4dfe9426635 |
| A1 | sensitivity by condition without invalid outputs (analysis no_invalid) | metrics_long.csv | 07_score.py | results/tables/tab_a1_sensitivity_no_invalid.tex | 0fda73f354788bd6 |
| F1 | sensitivity by condition, zero-shot, grouped bars with CI whiskers | metrics_long.csv | 07_score.py | figures/ch04_f1_sens_by_condition_eng.png | 2874d4917e756582 |
| F2 | heat map of paired deltas, model x strategy per condition | deltas_long.csv | 07_score.py | figures/ch04_f2_delta_heatmap_eng.png | d035f0f6ddd9ab56 |
| F3 | size effect: the two model families by condition | metrics_long.csv | 07_score.py | figures/ch04_f3_size_effect_eng.png | 47a019a9dc66fd57 |
| F4 | strategy effect: deltas per strategy by model | deltas_long.csv | 07_score.py | figures/ch04_f4_strategy_effect_eng.png | 3267ca20fd960316 |
| F5 | cost-robustness frontier: median GPU latency vs delta sensitivity | frontier.csv | 07_secondary.py | figures/ch04_f5_frontier_eng.png | 63f0e689679e7e83 |
| F6 | cue change by outcome in the paired rationales | cues_change.csv | 07_secondary.py | figures/ch04_f6_cue_change_eng.png | d19e384887822e0e |
| F7 | generalisation: core vs E-PhishLLM sensitivity and specificity | metrics_long.csv | 07_score.py | figures/ch04_f7_generalisation_eng.png | e78164fba4ad9b4b |

The hard-core coding sample (`reports/hardcore_sample.csv`, 8 pre-registered and 30 post hoc rows) and its
guide (`docs/HARDCORE_CODING_GUIDE.md`) feed the qualitative paragraph of Section 4.5; the author's codes are
entered by hand after the quantitative results were fixed.

## 2. The chain that produced the inputs

Every step is a numbered script run from the repository root; each writes a JSON report under `reports/`
and is idempotent. Commits name the state at which each output was produced.

| step | script(s) | output | commit (tag) | re-run check |
|---|---|---|---|---|
| 01 to 04 data | 01_download_data, 02_audit_raw, 03_preprocess, 04_partition | data/raw, data/processed/records.jsonl, partitions.json; reports/audit_raw, preprocess_report, partition_report | 3a6e489, pinned b7845df | byte-identical on re-run with requirements.txt |
| 05 variants, dev | 05_derive_variants (dev), 05a_merge_ratings, 05b_calibrate_variants | variants_dev.jsonl; reports/variants_dev_report, ratings_merge_dev, variants_calibration | 9d36803 to a8dbb6f (thresholds frozen fc4ec73, 2026-10-25) | from the dev cache |
| 05 variants, eval | 05_derive_variants (eval), 05c_spot_check_cache, 05d_control_exclusion_diagnosis | variants_eval.jsonl, paraphrase_cache_eval.jsonl (fixed artefacts); reports/variants_eval_report, variants_eval_fixed_artifacts, variants_eval_spot_check | b619959, 3d3a10b, 4d62378 (2026-10-26 and 2026-10-27) | two cache-sharing runs byte-identical; generation itself not bit-reproducible on CPU (section 4) |
| 06 detection | 06_select_fewshot, 06_download_models, 06_smoke_dev, 06_run_detection (notebooks/cloud_run.ipynb), 06_compare_smoke, 06_check_integrity | results/raw/<model>/<strategy>/eval.jsonl (24 cells, 124,968 rows); reports/detection_run_report, integrity_check | f2f7997 (v0.6-detection-ready) to 243e4d7 (v0.6.3-detection-complete); Mistral rerun at 071e3a0 (v0.6.2) | 24 of 24 cells pass the integrity check; GPU/CPU smoke agreement 99.7% |
| 06 baselines | 06_run_baselines (laptop: tfidf_lr, tfidf_svm; Colab T4: distilbert via notebooks/cloud_baselines.ipynb) | results/raw/baseline_*/supervised/eval.jsonl; reports/baselines_report | 3c6b4fb, 25b019e, e2dd65b (v0.6.5-step06-complete) | 3 of 3 pass the integrity check; refit reproduces the model hash |
| 07 item table | 07_build_items | results/scores/items.parquet (140,589 rows), pairs.csv; reports/items_build_report | 21910c2 | `--check` IDENTICAL |
| 07 cue lexicon | dev CoT run (Colab, 6 x 796) then 07_freeze_lexicon | configs/cue_lexicon.yaml; reports/cue_lexicon_dev_report | 6a18ecb (v0.7.0-devcot data), f450c3e | `--check` reproduces the report |
| 07 scores | 07_score, 07_secondary, 07_tables_figures | results/scores/*.csv, results/tables/*.tex, figures/*.png; reports/scoring_report, secondary_report, tables_figures_report | e18b66f (v0.7.1-scored); hard-core sample extension 75d9acb | `--check` IDENTICAL for all 12 CSVs; tests/test_scoring.py repeats it |
| SpearShift | Makefile, 07_score_model, CITATION.cff, docs/DATASHEET.md, this file | | 29bc0e2 and later (v1.0.0-thesis) | tests/test_score_model.py |

The pre-registered analysis plan is `docs/QUESTIONS.md` item 12 (declared 2026-10-31, before any metric),
with refinements 1 to 7 and the decisions of items 15 and 16 logged before the computation and the one
post-computation deviation (item 17, hard-core sample) logged with date and reason.

## 3. Pinned environment

**Laptop (data, variants, baselines TF-IDF, item table, scores, tables, figures).** WSL2, Ubuntu 24.04.3 LTS,
Python 3.12.3, CPU only. Pinned in `requirements.txt`: pyyaml 6.0.3, beautifulsoup4 4.15.0, lxml 6.1.3,
datasketch 2.0.0, numpy 2.5.4, torch 2.14.1+cpu, transformers 5.19.0, sentence-transformers 6.1.0,
sentencepiece 0.2.2, protobuf 7.36.2, spacy 3.8.16 with en_core_web_sm 3.8.0, huggingface_hub 1.33.0,
llama-cpp-python 0.3.36 (built from source), openpyxl 3.1.5, scikit-learn 1.9.1, pandas 3.1.0, pyarrow 26.0.0,
matplotlib 3.11.2. The versions that produced each report are also written into that report.

**Colab (all evaluation inference and the DistilBERT baseline).** Colab Pro subscription; Tesla T4 (15 GB) for
the 7B to 14B detectors (20 cells) and the DistilBERT baseline, NVIDIA L4 (24 GB) for gemma-2-27b (4 cells).
`requirements-detect.txt` with the CUDA build of llama-cpp-python 0.3.36 from the official wheel index (cu124
or cu130 chosen from the runtime's CUDA version by the notebook); `requirements-baselines.txt` with the
runtime's torch (2.11.0+cu130 recorded) and transformers 5.19.0. Total consumption 86.9 compute units (about
USD 8.70) for the 24 detector cells, the Mistral rerun, DistilBERT and the six dev CoT cells.

**Decoding and seeds.** Greedy decoding (temperature 0, top_p 1, repeat penalty off), seed 2026 everywhere
(`configs/data.yaml`), context 4,096 tokens, one run per cell. Every bootstrap stream is derived from the table
name, so a table's CI does not depend on what was computed before it (`scripts/scoring/stats.py`).

## 4. Fixed artefacts and their hashes (sha256)

Files that are inputs to a later step and are verified by hash before use. Items marked *archive* are not in
git and are deposited with the thesis (section 7 of `docs/DATASHEET.md`).

| artefact | sha256 | verified by |
|---|---|---|
| Nahmias et al. repository zip, commit 1c5ecbdd | 4804c49341808f941f847e8b079801193ab1403fdb50137663fd3d6c83c9e8f9 | 01_download_data (data/raw/provenance.json) |
| E-PhishLLM repository zip, commit 3ff53fb2 | edc5c5850a78463b6ebf07ab1f1334afded1a2fd88edd455f6b87e0550813094 | 01_download_data |
| data/processed/variants_eval.jsonl (*archive*, 1,670 rows) | d898cece5d0f5d399a036bdeab8d63c9246b4eb91fd8298c299285b354d46389 | reports/variants_eval_fixed_artifacts.json; 06_run_detection, 07_build_items, 07_score_model, cloud_run.ipynb |
| data/interim/paraphrase_cache_eval.jsonl (*archive*, 8,228 rows) | 694cd11b27045dfd6d7256b6f2bfae366e77d6c9d1be6fb02b9e6b0aac6297d7 | reports/variants_eval_fixed_artifacts.json |
| paraphraser Phi-3.5-mini-instruct-Q4_K_M.gguf | e4165e3a71af97f1b4820da61079826d8752a2088e313af0c7d346796c38eff5 | 05_derive_variants (configs/variants.yaml) |
| prompts/paraphrase_v1.txt | abe51e78ab6c6342ba5201cf1c355e9b9e163da38260072f0ae2a238b5da36e4 | reports/variants_eval_report.json |
| prompts/zero_shot.txt | 50cd0f47bb6686ca6d7540a9417554d984baa959157386d23beffe00264196aa | 06_check_integrity (every row carries the prompt hash) |
| prompts/few_shot.txt : prompts/few_shot_examples.json | bc6fb8a2153940b6b2800e0d6e841bfad6282452a0dbf37dfaaf33fe41ca6de5 : 6232e206d26430af4f05c1a7e59bee609d06b82d3e1ac65a4a132b4c8d67ac2d | 06_check_integrity |
| prompts/cot.txt | a06937f10aaa939c6906a176f7f8c66a176b0f987d4e4d2181ddc27e82f0a374 | 06_check_integrity |
| prompts/role.txt | ffa098cca99c756a77f4b85c9017ff0703d9342838b12f7be61e6b03ccdf3892 | 06_check_integrity |
| configs/detection.yaml | 017aa5a93b5db68716cc96f9b8fb365d50036e883090ecc66018825f368f57a5 | reports/detection_run_report.json, smoke reports |
| configs/models.yaml (at v0.7.1-scored) | d65261eeff6bafbf909248f54ef71cdeb5437e7cdef68711c5d9a7966a6beeff | reports/detection_run_report.json, smoke reports |
| Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf | 7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c | 06_download_models, 06_run_detection (model_hash per row) |
| Mistral-7B-Instruct-v0.3-Q4_K_M.gguf | 1270d22c0fbb3d092fb725d4d96c457b7b687a5f5a715abe1e818da303e562b6 | same |
| gemma-2-9b-it-Q4_K_M.gguf | 13b2a7b4115bbd0900162edcebe476da1ba1fc24e718e8b40d32f6e300f56dfe | same |
| Qwen2.5-7B-Instruct-Q4_K_M.gguf | 65b8fcd92af6b4fefa935c625d1ac27ea29dcb6ee14589c55a8f115ceaaa1423 | same |
| Qwen2.5-14B-Instruct-Q4_K_M.gguf | e47ad95dad6ff848b431053b375adb5d39321290ea2c638682577dafca87c008 | same |
| gemma-2-27b-it-Q4_K_M.gguf | 503a87ab47c9e7fb27545ec8592b4dc4493538bd47b397ceb3197e10a0370d23 | same |
| DistilBERT checkpoint models/baselines/distilbert.pt (*archive*) | 274764c766ff7a29dfd440822ba5a64f332a6a5ba3976be16422308472af6db1 | reports/baselines_report.json (model_hash), 06_check_integrity |
| TF-IDF + LR model hash / TF-IDF + SVM model hash | 20259f940b276711... / 80cf13cbd09419a3... (full values in reports/baselines_report.json) | 06_run_baselines refit check, 06_check_integrity |
| configs/cue_lexicon.yaml (frozen 2026-11-01, dev only) | e209c7a565add8bf7d88595b94d3f7174535ec93c6b35206225c58b8f43822fd | 07_secondary, tests/test_cue_lexicon.py |
| results/scores/items.parquet | 857b43eb24d3f57c0cd05444291556b816b35bd68292df3d475268ac43ec0dbc | 07_score (reports/items_build_report.json) |
| results/scores/pairs.csv | 4e953bb64eb5a6bcbcb9b3a426038d727e7872e43d2b0a5cb42c1dc146affa9e | 07_score, 07_score_model |
| results/scores/metrics_long.csv | 6c53871c3719d6927a0be006b246ba92042c0c38d423ca3b2570d9611c34fbe7 | reports/scoring_report.json; tests/test_score_model.py |
| results/scores/deltas_long.csv | 8053a31a421f0c900809c5761da9f871d95aa9015a68b534b5dfc8228dcfa9b3 | same |
| results/scores/contrasts.csv | b68073b9d6d4519aa6694a2639cbb915afc989e05dc6787b41e6e43d05028ccc | same |
| results/scores/ensemble_predictions.csv | 631475ca60b86569bb35fac950c0d9dc6b37254163d9acb2afe65cf92481f959 | same |

The 27 raw result files (24 detector cells, 3 baselines) have their sha256 and row counts in
`reports/integrity_check.json`; `07_build_items.py` refuses any file whose hash differs.

**What is not bit-reproducible.** Paraphrase generation on the CPU backend of llama.cpp: in the cache spot check
8 of 179 regenerated sentences differed by one to three words from the cached ones
(`reports/variants_eval_spot_check.json`). The released variants file and cache are therefore the fixed
artefacts, and every later step is byte-reproducible from them. GPU inference is greedy and was run once per
cell; the laptop CPU smoke test agreed with the GPU smoke test on 319 of 320 labels
(`reports/smoke_backend_agreement.json`).

## 5. Checks to run after cloning

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
make test                      # 78 unit tests, including the re-run of 07_score.py --check
make check                     # 07_build_items, 07_score, 07_secondary: IDENTICAL for every output
python scripts/07_freeze_lexicon.py --check
python scripts/06_check_integrity.py          # needs results/raw (in git) and data/processed (rebuilt by steps 01 to 05)
make tables                    # regenerates results/tables and figures; compare with reports/tables_figures_report.json
```

`make check` and `07_freeze_lexicon.py --check` need `data/processed/` (steps 01 to 04 rebuild the records and
partitions from the pinned commits; the variants file comes from the deposit or from step 05 with the cache).

## 6. AI assistance

The author used Claude Code (Anthropic) as an implementation assistant for this repository. The author set the
specifications (docs/METHODOLOGY_3.2.md, docs/TASK_05_variants.md, docs/TASK_06_detection.md,
docs/TASK_07_scoring.md), took every methodological decision, and reviewed the methodology with a separate
advisory process. Whenever a specification was ambiguous or infeasible, the assistant wrote the question into
docs/QUESTIONS.md instead of guessing, and the author's answer is logged there with its date; all 17 items,
their answers and the resulting deviations are in that file. The assistant wrote code, tests and documentation
under those specifications and the project rules of CLAUDE.md (no data or secrets in git, no generation of
phishing content, evaluation items read-only, determinism, every exclusion reported, text-only detectors,
evaluation inference on GPU only). Commits made with the assistant carry a Co-Authored-By line. The analysis
plan was declared before any metric was computed (QUESTIONS.md item 12), the scores were computed once, and the
author's manual coding of the hard-core sample is the only step performed by hand on results.

## 7. Zenodo deposit for v1.0.0-thesis

**Include.** The GitHub release archive of tag v1.0.0-thesis (code, configs, prompts, docs, tests, notebooks,
reports/, results/scores, results/tables, results/raw, figures); `data/processed/variants_eval.jsonl`,
`data/interim/paraphrase_cache_eval.jsonl` and `data/processed/obfuscation_log_eval.jsonl` under CC BY-NC-SA
4.0 with attribution to Nahmias et al. (2024); `models/baselines/distilbert.pt` with its hash and the licence
of distilbert-base-uncased (Apache-2.0); this file, `docs/DATASHEET.md`, `CITATION.cff` and `LICENSE`.

**Exclude.** Everything derived from E-PhishLLM, which carries no licence: `data/processed/records.jsonl`,
`partitions.json`, `variants_dev.jsonl`, `obfuscation_log_dev.jsonl`, the dev paraphrase cache,
`data/processed/hardcore_sample_text.jsonl`, the few-shot example texts (ids and hashes only are in git) and
the raw downloads; the GGUF model weights (distributed by their publishers under their own terms); `.env`
and any token. The raw result files in `results/raw/` carry no e-mail text field (item id, label, raw model output,
hashes, latency); the chain-of-thought outputs are model-written rationales that may quote short phrases of
an e-mail, including E-PhishLLM items. Reading: a few quoted words inside an analytic output are not a
redistribution of the dataset, so the raw files are deposited as they are in git; if the depositor prefers,
the `raw_output` field of the 12 CoT and dev CoT files can be blanked before upload without affecting any
score, since every label is reproducible from the committed `label_pred`.
