# LLM vs. LLM — project instructions for Claude Code

Master's thesis code: *Evaluating the Effectiveness of Open-Source Language Models in
Detecting AI-Generated Spear-Phishing Emails*. This repository is the "reproducible
evaluation framework" promised in the thesis (Contribution 4). Methodology text lives in
`docs/`; every script implements a numbered section of Chapter 3. Read
`docs/METHODOLOGY_3.2.md` before touching data code.

## Hard rules (never violate)
- **No data in git.** `data/` is ignored. Sources are downloaded by `scripts/01_download_data.py`
  at the pinned commits in `configs/data.yaml`. Never copy datasets into the repo; never
  change the pinned commits without updating `docs/` and `reports/`.
- **No secrets in git.** Tokens go in `.env` (ignored). `.env.example` documents keys only.
- **No generation of phishing content.** Variants are *derived* from existing records by
  the defined transformations only. Do not write prompts that ask a model to create phishing.
- **Evaluation items are read-only.** Never develop prompts, thresholds, examples or code
  behaviour against `core_pos`, `core_neg`, controls or `gen_*` partitions. Use `dev` only.
- **Determinism.** Every random choice uses `seed` from `configs/data.yaml`. Same input,
  same config, same seed must give byte-identical outputs.
- **Report everything.** Any record dropped, truncated, replaced, excluded or regenerated is
  counted in a JSON report under `reports/`. The thesis cites these files.
- **Text only.** Detectors see `subject` and `body` only. Never feed sender, headers, URLs.

## Conventions
- Python 3.10+, standard library first; third-party only via `requirements.txt` (pinned on release).
- Scripts are numbered, idempotent, config-driven, runnable from repo root:
  `python scripts/NN_name.py`. Each prints a summary and writes `reports/<name>.json`.
- Shared helpers go in `scripts/common.py` (create it when a function is needed twice).
- Logging to stdout; no print-debugging left behind.
- Keep functions small and typed; docstring states which thesis section it implements.
- Record schema (`data/processed/records.jsonl`): `id, source, subclass, class, subject,
  body, n_words, salutation, truncated`. `class` is `phish|legit`. `subclass` is one of
  `spear_llm, traditional, enron_ham, hard_ham, ephish_phish, ephish_legit`.
- Partition names (`data/processed/partitions.json`): `core_pos, core_neg, ctrl_para_legit,
  ctrl_modern_legit, gen_phish, gen_legit, dev, train, valid, fewshot_pool`.

## Pipeline status
| step | script | status |
|---|---|---|
| 01 | download at pinned commits | done, tested |
| 02 | audit raw sources | done, tested |
| 03 | normalize, neutralize placeholders, dedup across collections | done, tested |
| 04 | partitions + leakage check | done, tested (no leakage) |
| 05 | variants (paraphrase, obfuscation) + meaning checks, dev set first, then eval | done: dev calibrated (thresholds frozen), eval derived 2026-10-26 and determinism-checked; questions 7 and 8 answered 2026-10-27 (control kept at 213; variants file + cache are the fixed artifact, hashes in the report) |
| 06 | prompting / inference (llama.cpp GGUF backend) | not started |
| 07 | baselines | not started |
| 08 | evaluation + statistics | not started |

## Known data facts (from reports/, do not re-derive by guessing)
- Nahmias spear-phishing: 334 records, all distinct, bodies 59–324 words, all HTML in source.
- E-PhishLLM English: 5,996 phish / 5,506 legit; `<<placeholder>>` tokens appeared in 60% of
  phish and 0% of legit (class leak) and are neutralized in step 03 (3,673 replacements).
- After cross-collection dedup: hard_ham 308, enron_ham 1,610, traditional 2,654.
- Partitions: core_pos 334, core_neg 1,002 (308 hard + 694 enron), controls 334+334,
  gen 1,000+1,000 (salutation named 599 / generic 330 / none 71), dev 400, train 3,033, valid 337.
- Eval variants (reports/variants_eval_report.json): core_pos para_low 334/334 accepted, para_high
  325/334 (9 excluded, fraction), obf_low and obf_high 334/334 (integrity 100%); ctrl_para_legit
  para_high 213/334 (121 excluded, 36.2%, flagged; QUESTIONS.md item 7). Two cache-sharing runs
  byte-identical; cache spot check 171/179 generations identical (QUESTIONS.md item 8).

## Working with the thesis author
- The author reviews methodology with a separate advisor chat; this repo implements what
  `docs/` specifies. If a spec is ambiguous or infeasible, stop and write the question into
  `docs/QUESTIONS.md` rather than guessing.
- When a script changes a number that appears in `docs/METHODOLOGY_3.2.md`, append the
  new value to `docs/CHANGES_FOR_THESIS.md` so the text can be updated.

@docs/PROJECT_STATE.md
