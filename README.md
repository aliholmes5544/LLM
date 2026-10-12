# LLM vs. LLM — Evaluation Framework

Reproducible pipeline for *Evaluating the Effectiveness of Open-Source Language Models
in Detecting AI-Generated Spear-Phishing Emails* (Master's thesis).

This repository contains code only. Datasets are downloaded by script at pinned commits
and are **not redistributed** (see `data/raw/provenance.json` after step 1 for licenses).

## Setup

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # fill in later; never commit .env
```

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

## Status

- [x] 01–04 data construction and audit (Section 3.2.1–3.2.4)
- [ ] 05 variant derivation + meaning checks on the development set (Section 3.2.3)
- [ ] 06 prompting / inference (Sections 3.4, 3.6)
- [ ] 07 baselines (Section 3.5)
- [ ] 08 evaluation and statistics (Section 3.7)
