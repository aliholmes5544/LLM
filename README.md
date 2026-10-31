# LLM vs. LLM — Evaluation Framework

Reproducible pipeline for *Evaluating the Effectiveness of Open-Source Language Models
in Detecting AI-Generated Spear-Phishing Emails* (Master's thesis).

This repository contains code only. Datasets are downloaded by script at pinned commits
and are **not redistributed** (see `data/raw/provenance.json` after step 1 for licenses).

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
| `scripts/06_check_integrity.py` | verifies every `results/raw/*/*/eval.jsonl`: exact item set, no duplicates, frozen prompt and model hashes, backend cuda, GPU of the eval tier, labels reproducible from raw outputs, system text delivered (role prompt longer than zero_shot) | `reports/integrity_check.json` |
| `notebooks/cloud_run.ipynb` | Colab: clone at a tag, CUDA wheel, verified downloads, data from Drive, GPU smoke test, eval cells synced to Drive | `results/raw/`, `reports/` on Drive |

All evaluation inference runs on Colab GPUs (`eval_tier` in `configs/models.yaml`: T4 for the 7B to 14B
models, L4 for gemma-2-27b); the laptop runs development and the dev smoke test (`docs/QUESTIONS.md` item 11).
Gemma 2 and Mistral-7B receive the system text prepended to the user turn (`system_role: false`; `docs/QUESTIONS.md` items 9 and 13). The first Mistral run, made without the system text, is archived under `results/archive/mistral-7b_v1_no_system_text/`.

```bash
python scripts/06_download_models.py --tier laptop          # 4 GGUFs, 19.7 GB
python scripts/06_smoke_dev.py --tier laptop                 # CPU smoke test, dev only
python scripts/06_run_detection.py --model qwen25-7b --strategy zero_shot --partition dev --tier laptop --limit 20
python -m unittest tests.test_system_text                    # system text reaches every model (QUESTIONS.md item 13)
# evaluation: notebooks/cloud_run.ipynb on Colab (TAG = v0.6.2-detection-ready; MODELS = "mistral-7b" for the rerun),
# then copy results/raw and reports back
python scripts/06_check_integrity.py                        # every cell: item set, hashes, backend, GPU, parser, system text
```

## Status

- [x] 01–04 data construction and audit (Section 3.2.1–3.2.4)
- [x] 05 variant derivation + meaning checks on the development set (Section 3.2.3) — thresholds await the manual rating (05b)
- [ ] 06 prompting / inference (Sections 3.4, 3.6)
- [ ] 07 baselines (Section 3.5)
- [ ] 08 evaluation and statistics (Section 3.7)
