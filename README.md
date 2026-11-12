# SpearShift: evaluation framework for open-weight LLM detectors under AI-rewritten spear-phishing

SpearShift (package name `spearshift`) is the reproducible evaluation framework of the Master's thesis
*LLM vs. LLM: Evaluating the Effectiveness of Open-Source Language Models in Detecting AI-Generated
Spear-Phishing Emails* (Bakhit Ali Mashan, 2026). It builds a benchmark from published corpora, derives
paraphrased and obfuscated variants under meaning checks, runs open-weight detectors under four prompting
strategies against supervised baselines, and scores them with pre-registered statistics. Cite it with
`CITATION.cff`; the code is MIT (`LICENSE`), the derived data CC BY-NC-SA 4.0 (`docs/DATASHEET.md`).
`docs/REPRODUCE.md` maps every table and figure of Chapter 4 to its script, CSV and commit, lists the
pinned environment and the fixed-artefact hashes, and discloses the AI assistance.

This repository contains code, configuration, reports and result tables. Datasets are downloaded by script
at pinned commits and are **not redistributed** (see `data/raw/provenance.json` after step 1 for licenses).
`make evaluate MODEL=<key>` adds a detector model with one YAML block (section "Adding a new model").

## Setup

```bash
python -m venv .venv && source .venv/bin/activate     # Linux / WSL2 (the reference environment)
pip install -r requirements.txt                        # llama-cpp-python builds from source: needs gcc/g++
cp .env.example .env                                   # fill in later; never commit .env
```

Versions in `requirements.txt` are pinned to the environment that produced the files in
`reports/`. Run the scripts under Linux or WSL2: on native Windows the default text encoding
and the 260-character path limit change the results.

## Data pipeline (Section 3.2) — run in order

| step | script | what it does | output |
|---|---|---|---|
| 1 | `scripts/01_download_data.py` | fetch both sources at the commits in `configs/data.yaml`, record sha256 + license | `data/raw/`, `data/raw/provenance.json` |
| 2 | `scripts/02_audit_raw.py` | counts, fields, labels, HTML, duplicates, placeholders, salutation proxy | `reports/audit_raw.json` |
| 3 | `scripts/03_preprocess.py` | one schema; strip HTML identically; neutralize `<<placeholders>>`; drop empty, truncate long; exact + near-duplicate removal **across all collections** | `data/processed/records.jsonl`, `reports/preprocess_report.json` |
| 4 | `scripts/04_partition.py` | core test / controls / generalization / development / train+valid with one seed; **leakage check** (no evaluation item has a near-duplicate in train, valid, dev or few-shot pool) | `data/processed/partitions.json`, `reports/partition_report.json` |

```bash
python scripts/01_download_data.py
python scripts/02_audit_raw.py
python scripts/03_preprocess.py
python scripts/04_partition.py
```

Every threshold and size lives in `configs/data.yaml`; every figure in the thesis
traces to a file in `reports/`.

## Variant derivation (Section 3.2.3) — development set first

| step | script | what it does | output |
|---|---|---|---|
| 5 | `scripts/05_derive_variants.py` | for the 100 dev `ephish_phish` emails: protected spans (regex + spaCy NER), two obfuscation conditions with an exact edit log and integrity replay, two paraphrase conditions (Phi-3.5-mini-instruct GGUF via llama.cpp, cached) with embedding, length, span and NLI checks; regenerate once, else exclude; stratified 10 % manual-review sample. Asserts that no evaluation partition is touched. | `data/processed/variants_dev.jsonl`, `data/processed/obfuscation_log_dev.jsonl`, `reports/variants_dev_report.json`, `reports/manual_review_sample_dev.csv` |
| 5b | `scripts/05b_calibrate_variants.py` | after both annotators rate the sample: choose `thr_cos` / `thr_nli`, Cohen's kappa, Wilson 95 % CI of the sample failure rate per condition | `reports/variants_calibration.json` |

```bash
bash run_variants_dev.sh          # --selftest, --limit 3 smoke run, then the full dev run (~1 h on 16 CPU threads)
python scripts/05b_calibrate_variants.py   # once reports/manual_review_sample_dev.csv is rated
```

Settings live in `configs/variants.yaml` (model, decoding, thresholds, protected-span rules; the
paraphrase model's family is listed under `excluded_from_detectors`). The GGUF (2.4 GB) and the
check models are downloaded into `models/` on first run. Paraphrase generations are cached in
`data/interim/`, so reruns are fast and byte-identical.

## Detection (step 06, Sections 3.5 to 3.7)

Six open-weight detectors (GGUF Q4_K_M, llama-cpp-python 0.3.36) x four prompting strategies, decoding
frozen in `configs/detection.yaml`, prompts in `prompts/`. Developed and smoke-tested on `dev` only.

| script | what it does | output |
|---|---|---|
| `scripts/06_select_fewshot.py` | draws the 4 fixed few-shot examples from `fewshot_pool` (persona, length, similarity rules) | `prompts/few_shot_examples.json`, `reports/fewshot_selection.json` |
| `scripts/06_download_models.py` | downloads the GGUF files of a tier into `models/`, verifies sha256, records licences | `reports/models_download_report.json` |
| `scripts/06_smoke_dev.py` | every model x strategy on 20 dev items; gate: invalid rate <= 10 % per cell | `results/smoke_dev/`, `reports/smoke_dev_report.json` |
| `scripts/06_compare_smoke.py` | agreement between two smoke runs (CPU laptop vs GPU Colab) | `reports/smoke_backend_agreement.json` |
| `scripts/06_run_detection.py` | one resumable (model, strategy, partition) cell, one row per item, backend recorded | `results/raw/{model}/{strategy}/{partition}.jsonl`, `reports/detection_run_report.json` |
| `scripts/06_run_baselines.py` | one (baseline, partition) cell: TF-IDF + LR / SVM (train on `train`, C on `valid`, laptop) or DistilBERT (Colab T4, `notebooks/cloud_baselines.ipynb`); runner schema, `config_hash` + `model_hash`, resumable, fixed thresholds | `results/raw/baseline_{key}/supervised/{valid,eval}.jsonl`, `reports/baselines_report.json` |
| `scripts/07_build_items.py` | step 07 item table: hash-verified join of the 27 eval files with partition, condition, item class, cluster (source e-mail) and body length; no metric | `results/scores/items.parquet`, `results/scores/pairs.csv`, `reports/items_build_report.json` |
| `scripts/07_score.py` | step 07 step 3: primary metrics with cluster-bootstrap CIs, paired deltas with exact McNemar and Holm per family, F-RQ2/F-RQ3 contrasts, majority ensemble; `--check` re-runs and compares byte for byte | `results/scores/{metrics_long,deltas_long,contrasts,ensemble_predictions}.csv`, `reports/scoring_report.json` |
| `scripts/07_secondary.py` | step 07 secondary analyses: ensemble votes, CoT cue frequency and cue change by outcome (frozen lexicon), hard core and its seeded coding sample (8 pre-registered + 30 post hoc, item 17), cost-robustness frontier; `--check` | `results/scores/{ensemble_votes,cues_*,hardcore_*,frontier}.csv`, `reports/hardcore_sample.csv`, `reports/secondary_report.json` |
| `scripts/06_run_twostage.py` | TASK_08 two-stage indicator detector (supervisor-requested, exploratory, post hoc; `docs/TASK_08_twostage.md`, QUESTIONS.md item 18): `extract` fills the indicator JSON with the same model (`prompts/extract_indicators.txt`, `configs/twostage.yaml`; `--smoke` = the 20-item dev sample), `fit` trains two logistic regressions per model on the dev extractions (grouped cv): `clean` on the 400 originals only, the primary, and `all` on all 796 items, attack-aware; `predict` writes detector rows for both (`lr_clean`, `lr_all`), `units` records a Colab compute-unit reading, `budget` projects the compute units for plans A (dev + full eval) and B (dev + core eval); Colab: `notebooks/cloud_twostage.ipynb`; integrity: `06_check_integrity.py --twostage`; scoring: `07_score_model.py --kind twostage`; frozen artefacts untouched | `results/raw/twostage_{model}/{extract,lr_clean,lr_all}/{partition}.jsonl`, `results/smoke_twostage/`, `models/twostage/`, `reports/twostage_report.json` Steps 4 and 5 done 2026-11-12 (v1.1.0-twostage): `scripts/07_twostage_compare.py` computes the primary comparison (difference of deltas, two-stage minus direct) into `results/scores/additional/twostage_compare/`, `scripts/07_twostage_tables_figures.py` writes `results/tables/tab_t12_twostage.tex` and `figures/ch04_f8_twostage_eng.png`. |
| `scripts/07_coding_sheet.py` | the author's coding workbook for the hard-core sample: one row per sampled item with subject, original body, variant body, the models that missed it, a drop-down `failure_type` (code list by row type) and a free-text `note` | `reports/hardcore_coding.xlsx` |
| `scripts/07_import_coding.py` | reads the filled workbook back: validates the codes, writes only the two coding columns into `reports/hardcore_sample.csv`, writes the code summary; `--dry-run` | `reports/hardcore_sample.csv` (two columns), `reports/hardcore_coding_summary.csv` |
| `scripts/demo_detect.py` | demo outside the pipeline: classifies one e-mail with one study model and strategy on the laptop (section "Try it") | stdout only |
| `scripts/07_score_model.py` | SpearShift extension path (`make evaluate`): scores one additional model with the functions of `07_score.py` into separate files, leaving the pre-registered scores byte-identical (`tests/test_score_model.py`); `--check` | `results/scores/additional/<key>/{items.parquet,metrics_long,deltas_long}.csv`, `reports/scoring_additional_<key>.json` |
| `scripts/07_tables_figures.py` | LaTeX tables T1 to T11 and A1 (booktabs, no caption) and figures F1 to F7 (300 dpi) from the CSVs | `results/tables/tab_*.tex`, `figures/ch04_*_eng.png`, `reports/tables_figures_report.json` |
| `scripts/07_freeze_lexicon.py` | step 07 step 2: applies the frozen CoT cue lexicon (`configs/cue_lexicon.yaml`, `scripts/scoring/cues.py`) to the dev rationales only (six `cot/dev.jsonl` cells + smoke sets), reports counts, polarity and seeded examples; `--check` reproduces the report | `reports/cue_lexicon_dev_report.json` |
| `scripts/06_check_integrity.py` | verifies every `results/raw/*/*/eval.jsonl`: exact item set, no duplicates, frozen prompt and model hashes, backend cuda, GPU of the eval tier, labels reproducible from raw outputs, system text delivered (role prompt longer than zero_shot) | `reports/integrity_check.json` |
| `notebooks/cloud_run.ipynb` | Colab: clone at a tag, CUDA wheel, verified downloads, data from Drive, GPU smoke test, eval cells synced to Drive | `results/raw/`, `reports/` on Drive |

All evaluation inference runs on Colab GPUs (`eval_tier` in `configs/models.yaml`: T4 for the 7B to 14B
models, L4 for gemma-2-27b); the laptop runs development and the dev smoke test (`docs/QUESTIONS.md` item 11).
Gemma 2 and Mistral-7B receive the system text prepended to the user turn (`system_role: false`; `docs/QUESTIONS.md` items 9 and 13). The first Mistral run, made without the system text, is archived under `results/archive/mistral-7b_v1_no_system_text/`;
the rerun passes the integrity check (24 of 24 cells, 2026-11-01). GPU/CPU smoke label agreement 99.7 % (319 of 320).

```bash
python scripts/06_download_models.py --tier laptop          # 4 GGUFs, 19.7 GB
python scripts/06_smoke_dev.py --tier laptop                 # CPU smoke test, dev only
python scripts/06_run_detection.py --model qwen25-7b --strategy zero_shot --partition dev --tier laptop --limit 20
python -m unittest tests.test_system_text                    # system text reaches every model (QUESTIONS.md item 13)
# evaluation: notebooks/cloud_run.ipynb on Colab (all 24 cells complete at v0.6.3-detection-complete; the four Mistral
# cells were rerun at TAG = v0.6.2-detection-ready with MODELS = "mistral-7b"), then copy results/raw and reports back
python scripts/06_check_integrity.py                        # every cell: item set, hashes, backend, GPU, parser, system text
python scripts/06_run_baselines.py --baseline tfidf_lr  --partition valid   # C selection + sanity F1 on valid (laptop)
python scripts/06_run_baselines.py --baseline tfidf_lr  --partition eval    # same 5,207 items as the detectors
python scripts/06_run_baselines.py --baseline tfidf_svm --partition valid
python scripts/06_run_baselines.py --baseline tfidf_svm --partition eval
python scripts/07_build_items.py            # step 07 item table (no metric)
python scripts/07_freeze_lexicon.py         # step 07 step 2: cue lexicon on dev rationales only
python scripts/07_score.py                  # step 07 step 3: scores (computed once; --check reproduces)
python scripts/07_secondary.py              # ensemble votes, cues, hard core, frontier
python scripts/07_tables_figures.py         # tables and figures for Chapter 4
# distilbert: notebooks/cloud_baselines.ipynb on a Colab T4 (trains once, checkpoint hash recorded), then copy back
```

## Try it

`scripts/demo_detect.py` classifies a single e-mail with one of the study's detectors, using the same prompt
files, decoding settings, context rule, system-text delivery and label extraction as the evaluation, but
outside the pipeline: nothing is written, and the answer is not an evaluation result. It needs the model's GGUF
in `models/` (`python scripts/06_download_models.py --models gemma2-9b`, 5.8 GB) and runs on the CPU
(gemma2-9b: about 20 s to load, 10 to 30 s per e-mail on 16 threads).

```bash
python scripts/demo_detect.py --subject "Agenda for Thursday" \
    --body "Hi all, attached is the agenda for Thursday's review. Please add your items by Wednesday noon. Thanks, Dana"
python scripts/demo_detect.py --file mail.txt --model qwen25-7b --strategy cot --show-prompt
```

`--file` takes a UTF-8 text file whose first line may be `Subject: ...`; `--strategy` is `zero_shot` (default),
`few_shot` (needs `data/processed/records.jsonl` for the four frozen examples), `cot` or `role`. The output shows
the verified model hash, the prompt hash, the raw model output and the extracted label (`PHISH`, `LEGIT` or
`INVALID`). Detectors see subject and body only; do not paste headers or addresses.

## Adding a new model (SpearShift extension path)

One YAML block in `configs/models.yaml` describes a detector; everything else is derived from it. Copy an
existing block and set, at least:

```yaml
  my-model-9b:                                   # key: used in paths, tables and make
    name: My-Model-9B-Instruct                   # model card name
    params_b: 9
    original_repo: org/My-Model-9B-Instruct      # gated repositories need HF_TOKEN in .env
    gguf_repo: someone/My-Model-9B-Instruct-GGUF
    gguf_file: My-Model-9B-Instruct-Q4_K_M.gguf  # Q4_K_M, like the six pre-registered models
    gguf_bytes: 0                                # size listed by the repository (sanity check only)
    sha256: null                                 # the downloader fills it on first download, then verifies it
    license: "apache-2.0"                        # verbatim from the model card
    license_class: open-source                   # or open-weight
    chat_template: embedded
    system_role: true                            # false if the template has no system turn (text is prepended)
    eval_tier: colab_t4                          # colab_t4 up to about 14B, colab_l4 for larger models
    smoke_tiers: [laptop, colab_t4]
```

The model's family must not be the paraphrase model's family (`excluded_from_detectors` in
`configs/variants.yaml`; the downloader refuses it). Then run, on the GPU tier named in the block:

```bash
make evaluate MODEL=my-model-9b                 # TIER defaults to eval_tier; TIER=laptop runs the smoke test only
```

The target sequences the numbered scripts and stops at the first failure: `06_download_models.py`
(download, sha256), `06_smoke_dev.py` on dev with the invalid-rate gate (`reports/smoke_dev_<key>.json`),
`06_run_detection.py` for the four strategies on the evaluation items (refused off the model's GPU tier, and
refused when prompts or configs are not committed), `06_check_integrity.py --models <key>` into
`reports/integrity_check_<key>.json`, and `07_score_model.py`, which writes the model's metrics and paired
deltas with the same bootstrap streams, McNemar test and Holm correction as the pre-registered scores into
`results/scores/additional/<key>/`. The six pre-registered models, the ensemble, the families F-RQ4, F-RQ2,
F-RQ3 and the committed CSVs are frozen: the target ends with `07_score.py --check`, and
`tests/test_score_model.py` verifies that scoring a model alone reproduces its frozen rows. An added model is
reported next to the frozen tables as a post-registration addition with its own families `A-<key>` and
`A-<key>-<strategy>`; it enters neither the ensemble nor the tables and figures of Chapter 4.

## Status

- [x] 01–04 data construction and audit (Section 3.2.1–3.2.4)
- [x] 05 variant derivation + meaning checks on the development set (Section 3.2.3) — thresholds await the manual rating (05b)
- [x] 06 prompting / inference (Sections 3.4, 3.6): 24 cells on Colab GPUs, all passing the integrity check
- [x] 07 baselines (Section 3.5): tfidf_lr, tfidf_svm (laptop) and distilbert (Colab T4); 3/3 pass the integrity check
- [x] 08 evaluation and statistics (Section 4.3, 4.5): scores computed once (v0.7.1-scored); tables and figures in results/tables and figures/
