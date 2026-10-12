#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python scripts/01_download_data.py
python scripts/02_audit_raw.py
python scripts/03_preprocess.py
python scripts/04_partition.py
