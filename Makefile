# SpearShift: evaluation framework for open-weight LLM detectors under AI-rewritten spear-phishing.
#
#   make evaluate MODEL=<key> [TIER=laptop|colab_t4|colab_l4]
#
# runs the full chain for one detector model listed in configs/models.yaml (README, "Adding a new model"):
# download and verify the GGUF, smoke gate on dev, the four strategies on the evaluation items, the integrity
# check, and the scoring of the model as an additional detector (scripts/07_score_model.py). make only
# sequences the numbered scripts and stops at the first failure. The scripts enforce the project rules: eval
# inference runs only on the model's eval_tier GPU, prompts and configs must be committed unchanged, a finished
# eval cell is never overwritten, and the pre-registered scores stay byte-identical (07_score.py --check).
# TIER defaults to the model's eval_tier; the laptop tier can run the smoke test only.

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python)
MODEL ?=
STRATEGIES ?= zero_shot few_shot cot role
ifeq ($(origin TIER), undefined)
TIER := $(shell $(PYTHON) -c "import yaml; m = yaml.safe_load(open('configs/models.yaml'))['models']; print(m['$(MODEL)']['eval_tier'] if '$(MODEL)' in m else '')")
endif
SMOKE_REPORT = reports/smoke_dev_$(MODEL).json
INTEGRITY_REPORT = reports/integrity_check_$(MODEL).json

.PHONY: help evaluate require-model download smoke eval integrity score test check tables

help:
	@echo "make evaluate MODEL=<key> [TIER=laptop|colab_t4|colab_l4]   full chain for one model of configs/models.yaml"
	@echo "make download|smoke|eval|integrity|score MODEL=<key>        one stage of that chain"
	@echo "make test                                                 unit tests (python -m unittest discover tests)"
	@echo "make check                                                re-run checks: item table, scores, secondary analyses byte-identical"
	@echo "make tables                                               regenerate results/tables and figures from the CSVs"

require-model:
	@test -n "$(MODEL)" || { echo "usage: make evaluate MODEL=<key in configs/models.yaml> [TIER=laptop|colab_t4|colab_l4]"; exit 2; }
	@$(PYTHON) -c "import sys, yaml; m = yaml.safe_load(open('configs/models.yaml'))['models']; sys.exit(0 if '$(MODEL)' in m else '$(MODEL) is not a key of configs/models.yaml; keys: %s' % list(m))"
	@test -n "$(TIER)" || { echo "TIER is empty: pass TIER=... or set eval_tier in the model's YAML block"; exit 2; }

download: require-model
	$(PYTHON) scripts/06_download_models.py --tier $(TIER) --models $(MODEL)

smoke: require-model
	$(PYTHON) scripts/06_smoke_dev.py --tier $(TIER) --models $(MODEL) --report $(SMOKE_REPORT)
	@$(PYTHON) -c "import json, sys; r = json.load(open('$(SMOKE_REPORT)')); sys.exit(0 if r.get('gate_all_pass') else 'smoke gate FAILED: a cell exceeds the invalid-rate limit, see $(SMOKE_REPORT)')"

eval: require-model
	@for s in $(STRATEGIES); do $(PYTHON) scripts/06_run_detection.py --model $(MODEL) --strategy $$s --partition eval --tier $(TIER) || exit 1; done

integrity: require-model
	$(PYTHON) scripts/06_check_integrity.py --models $(MODEL) --baselines none --report $(INTEGRITY_REPORT)

score: require-model
	$(PYTHON) scripts/07_score_model.py --model $(MODEL) --integrity $(INTEGRITY_REPORT)
	$(PYTHON) scripts/07_score.py --check

evaluate: download smoke eval integrity score
	@echo "done: results/scores/additional/$(MODEL)/ and reports/scoring_additional_$(MODEL).json; the pre-registered scores are unchanged"

test:
	$(PYTHON) -m unittest discover tests

check:
	$(PYTHON) scripts/07_build_items.py --check
	$(PYTHON) scripts/07_score.py --check
	$(PYTHON) scripts/07_secondary.py --check

tables:
	$(PYTHON) scripts/07_tables_figures.py
