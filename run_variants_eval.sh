#!/usr/bin/env bash
# Step 05 on the evaluation partitions (Section 3.2.3, Table 3.2): a single derivation with the frozen
# settings, run twice to verify determinism. Refuses to start unless configs/variants.yaml is identical to
# the committed version. Log: data/interim/variants_eval_run.log (gitignored); the config hashes are also
# written into reports/variants_eval_report.json by the script.
set -euo pipefail
cd "$(dirname "$0")"
LOG=data/interim/variants_eval_run.log
mkdir -p data/interim
{
  echo "=== $(date -u +%FT%TZ) run_variants_eval.sh start (commit $(git rev-parse --short HEAD))"
  if ! git diff --quiet HEAD -- configs/variants.yaml; then
    echo "configs/variants.yaml differs from the committed version; refusing to derive evaluation variants"; exit 1
  fi
  echo "configs/variants.yaml identical to HEAD; sha256 $(sha256sum configs/variants.yaml | cut -d' ' -f1)"
  echo "configs/variants_eval.yaml sha256 $(sha256sum configs/variants_eval.yaml | cut -d' ' -f1)"
  echo "prompts/paraphrase_v1.txt sha256 $(sha256sum prompts/paraphrase_v1.txt | cut -d' ' -f1)"
  python scripts/05_derive_variants.py --target eval --dry-run
  echo "=== $(date -u +%FT%TZ) run 1"
  python scripts/05_derive_variants.py --target eval --skip-download
  sha256sum data/processed/variants_eval.jsonl data/processed/obfuscation_log_eval.jsonl reports/variants_eval_report.json > data/interim/variants_eval_run1.sha256
  cat data/interim/variants_eval_run1.sha256
  echo "=== $(date -u +%FT%TZ) run 2 (determinism check)"
  python scripts/05_derive_variants.py --target eval --skip-download
  sha256sum data/processed/variants_eval.jsonl data/processed/obfuscation_log_eval.jsonl reports/variants_eval_report.json > data/interim/variants_eval_run2.sha256
  cat data/interim/variants_eval_run2.sha256
  if cmp -s data/interim/variants_eval_run1.sha256 data/interim/variants_eval_run2.sha256; then
    echo "DETERMINISM OK: run 2 reproduced run 1 byte-identically"
  else
    echo "DETERMINISM FAILED: outputs differ between run 1 and run 2"; exit 2
  fi
  echo "=== $(date -u +%FT%TZ) done"
} 2>&1 | tee -a "$LOG"
