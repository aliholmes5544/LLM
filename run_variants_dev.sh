#!/usr/bin/env bash
# Step 05 on the development set (Section 3.2.3). Needs the venv and the models (downloaded on first run).
set -euo pipefail
cd "$(dirname "$0")"
python scripts/05_derive_variants.py --selftest
python scripts/05_derive_variants.py --limit 3
python scripts/05_derive_variants.py
# After the author has rated reports/manual_review_sample_dev.csv:
#   python scripts/05b_calibrate_variants.py
