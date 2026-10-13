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

## Status

- [x] 01–04 data construction and audit (Section 3.2.1–3.2.4)
- [x] 05 variant derivation + meaning checks on the development set (Section 3.2.3) — thresholds await the manual rating (05b)
- [ ] 06 prompting / inference (Sections 3.4, 3.6)
- [ ] 07 baselines (Section 3.5)
- [ ] 08 evaluation and statistics (Section 3.7)
