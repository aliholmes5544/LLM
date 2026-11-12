# SpearShift (LLM vs. LLM): project instructions for Claude Code

Master's thesis code: *LLM vs. LLM: Evaluating the Effectiveness of Open-Source Language Models in
Detecting AI-Generated Spear-Phishing Emails*. This repository is **SpearShift** (package name
`spearshift`, `pyproject.toml`, `CITATION.cff`), the "reproducible evaluation framework" promised in the
thesis (Contribution 4). Script paths are unchanged by the name. Methodology text lives in
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
- **Eval inference on GPU only.** Every evaluation cell runs on its `eval_tier` (Colab T4 / L4,
  `notebooks/cloud_run.ipynb`); the laptop runs dev smoke tests only. `06_run_detection.py` enforces this.

## Conventions
- Python 3.10+, standard library first; third-party only via `requirements.txt` (pinned on release).
- Scripts are numbered, idempotent, config-driven, runnable from repo root:
  `python scripts/NN_name.py`. Each prints a summary and writes `reports/<name>.json`.
- Shared helpers go in `scripts/common.py` (create it when a function is needed twice).
- **Frozen scores.** The six pre-registered models, the ensemble, the families and every CSV of
  `scripts/07_score.py` are frozen (QUESTIONS.md item 12). A new detector is added with one YAML block in
  `configs/models.yaml` and `make evaluate MODEL=<key>` (Makefile), which scores it through
  `scripts/07_score_model.py` into `results/scores/additional/<key>/`; never append rows to the frozen CSVs.
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
| 05 | variants (paraphrase, obfuscation) + meaning checks, dev set first, then eval | done: dev calibrated (thresholds frozen), eval derived 2026-10-26 and determinism-checked; questions 7 and 8 answered 2026-10-27 (control 210 after the unchanged rule; variants file + cache are the fixed artifact, hashes in the report) |
| 06 | prompting / inference (llama.cpp GGUF backend) | DONE (v0.6.5-step06-complete, 2026-11-01; TASK_06 definition of done met): configs, prompts, extract_label + tests, few-shot examples frozen (2026-10-27); laptop GGUFs sha256-pinned; dev smoke test PASSED on CPU (reports/smoke_dev_report.json); decision Q11: ALL eval inference on Colab GPUs (T4: 7B to 14B, L4: 27B), laptop = dev/smoke only; 06_run_detection.py, 06_compare_smoke.py, 06_check_integrity.py, notebooks/cloud_run.ipynb; tags v0.6, v0.6.1, v0.6.2, v0.6.3; all 24 eval cells complete on Colab (T4 20 cells, L4 4 cells, 2026-10-28 to 2026-11-01), results/raw committed (124,968 rows), 24/24 cells pass 06_check_integrity.py including system text delivered; the first Mistral run (no system message, QUESTIONS.md item 13) is archived in results/archive/ and was rerun with system_role false; GPU/CPU smoke label agreement 99.7% (319/320); 188 invalid rows (0.15%), max cell mistral-7b/cot 1.31%; about 63 compute units of inference. Baselines (06_run_baselines.py): tfidf_lr (C 1.0) and tfidf_svm (C 0.3) on the laptop, distilbert on Colab T4 (checkpoint sha256 274764c7..., 330/5,207 eval inputs truncated at 512 tokens, all legitimate); 3/3 baselines pass 06_check_integrity.py; proprietary reference DROPPED (QUESTIONS.md item 14). No metric computed yet (pre-registration item 12) |
| 07 | baselines (scripts/06_run_baselines.py, configs/baselines.yaml; TASK_06 section 3) | done (2026-11-01): tfidf_lr, tfidf_svm (laptop) and distilbert (Colab T4, notebooks/cloud_baselines.ipynb) trained on `train`, C chosen on `valid`, eval cells in results/raw/baseline_*/supervised/eval.jsonl, all passing 06_check_integrity.py; reports/baselines_report.json |
| 09 | two-stage indicator detector (docs/TASK_08_twostage.md; supervisor-requested, exploratory, post hoc; QUESTIONS.md item 18) | step 1 done 2026-11-09: configs/twostage.yaml, prompts/extract_indicators.txt, scripts/06_run_twostage.py (extract / fit / predict; --smoke), scripts/twostage/{parse,stage2,integrity}.py, tests/test_twostage.py; item 18 (a) to (k) answered 2026-11-09 and implemented (parse failure never a feature; grouped cv; normalisation table; sender_claim_inconsistency; 07_score_model.py --kind twostage; 06_check_integrity.py --twostage; no rows in T1 to T11; units measured two ways); step 2: CPU smoke on dev for qwen25-7b and gemma2-9b done on the laptop (20/20 each, 0 parse failures, format gate passed); `06_run_twostage.py units` (Colab reading before/after, span rate, gap) and `budget` (plans A = dev + full eval 6,003 items per model, B = dev + core eval 4,003; scripts/twostage/budget.py; prior basis until the GPU smoke exists) added 2026-11-09; GPU smoke of all three done 2026-11-10 (0 parse failures in every cell; T4 3.7 and 5.6 s/item, L4 10.1 s/item; measured rates 1.375 T4, 2.461 L4 units/h); item 18 option 1 (2026-11-10): plan A for all three, stop rule 80; step 3 done 2026-11-10: dev extraction 3 x 796/796 on Colab (0 parse failures, 0 volunteered verdicts; mean 4.79 / 6.01 / 9.95 s per item; 8.98 units incl. set-up; measured billing rates 1.632 T4, 1.721 L4 units/h over the dev spans), checkpoint plan A 58.0 units total, 50.3 remaining for eval, below the stop rule of 80, 103.58 available; amendment 2026-11-10 (author): two stage-2 fits per model, `clean` on the 400 dev originals only (PRIMARY, strategy lr_clean, family A-twostage-<key>-clean) and `all` on the 796 dev items (attack-aware secondary, lr_all, A-twostage-<key>-all), configs/twostage.yaml `fits` (outside config_hash), both predicted, integrity-checked and scored, T12/F8 headline = clean; fitted (clean C 3.0 / 0.3 / 1.0, grouped-cv balanced accuracy 0.890 / 0.908 / 0.890; all C 3.0, 0.889 / 0.890 / 0.866; models/twostage/*.joblib gitignored, sha256 in the report); steps 4 and 5 done 2026-11-12 (v1.1.0-twostage, the first and only computation): eval extraction 3 x 5,207/5,207 on Colab (0 parse failures; T4 21.55 units, L4 29.94; TASK_08 total 113.12 -> 52.09 = 61.03 units), both fits predicted and 6/6 cells pass `06_check_integrity.py --twostage`; scored by `07_score_model.py --kind twostage`, primary comparison by `07_twostage_compare.py` (difference of deltas two-stage minus direct, bootstrap CI and p, Holm per family), T12 `results/tables/tab_t12_twostage.tex` and F8 `figures/ch04_f8_twostage_eng.png` by `07_twostage_tables_figures.py`; headline: the clean-fit two-stage detector is less sensitive on originals than the Gemma direct verdicts (0.47 to 0.58 vs 0.93 to 0.98) and its phishing deltas are larger in magnitude (obfuscation lifts it to 0.93 to 0.99), so it is not more robust; it is more specific on the core legit set and on the paraphrased control; it helps the weak Qwen2.5-7B direct verdict; 83 frozen files byte-identical; step 6 done 2026-11-12 (thesis wording for 3.5, 3.6, 4.5, 4.7, 4.8, 5.5 in CHANGES_FOR_THESIS.md; the hard-core coding clause is marked to confirm because reports/hardcore_coding.xlsx is still unfilled); TASK_08 complete |
| 08 | evaluation + statistics (docs/TASK_07_scoring.md; scripts/07_*.py) | in progress: TASK_07 step 1 done 2026-11-01 (results/scores/items.parquet, 140,589 rows, hash-verified inputs, rebuild byte-identical, NO metric computed); item 15 answered 2026-11-01 (families F-RQ4/F-RQ2/F-RQ3, refinements in item 12); dev CoT run 6 x 796 on Colab (v0.7.0-devcot) committed; step 2 done 2026-11-01: cue lexicon frozen on dev only (configs/cue_lexicon.yaml sha256 e209c7a565add8bf..., scripts/07_freeze_lexicon.py, reports/cue_lexicon_dev_report.json, 61 tests OK); item 16 answered and closed; step 3 DONE 2026-11-01 (v0.7.1-scored, the first and only computation): 07_score.py (metrics_long, deltas_long, contrasts, ensemble; 48 s, re-run byte-identical, test), 07_secondary.py (ensemble votes, cue analysis, hard core, frontier), 07_tables_figures.py (results/tables/tab_t1..t11,a1.tex, figures/ch04_f1..f7_eng.png); headline: every zero-shot phishing delta <= 0 (variants easier to detect), 26/30 F-RQ4 tests Holm-significant, control deltas positive; hard-core sample: 8 pre-registered (all six wrong, phishing variants) + 30 post hoc (at least 4 of 6 wrong, five strata; QUESTIONS.md item 17 closed, deviation logged in item 12); author's manual coding of the 38 rows in reports/hardcore_sample.csv pending (docs/HARDCORE_CODING_GUIDE.md); framework named SpearShift 2026-11-01 (Makefile `make evaluate`, 07_score_model.py, CITATION.cff, LICENSE MIT for code); docs/DATASHEET.md and docs/REPRODUCE.md written; tag v1.0.0-thesis; coding workbook reports/hardcore_coding.xlsx (07_coding_sheet.py, read back by 07_import_coding.py) and demo_detect.py (README "Try it") added |

## Known data facts (from reports/, do not re-derive by guessing)
- Nahmias spear-phishing: 334 records, all distinct, bodies 59–324 words, all HTML in source.
- E-PhishLLM English: 5,996 phish / 5,506 legit; `<<placeholder>>` tokens appeared in 60% of
  phish and 0% of legit (class leak) and are neutralized in step 03 (3,673 replacements).
- After cross-collection dedup: hard_ham 308, enron_ham 1,610, traditional 2,654.
- Partitions: core_pos 334, core_neg 1,002 (308 hard + 694 enron), controls 334+334,
  gen 1,000+1,000 (salutation named 599 / generic 330 / none 71), dev 400, train 3,033, valid 337.
- Eval variants (reports/variants_eval_report.json): core_pos para_low 334/334 accepted, para_high
  325/334 (9 excluded, fraction), obf_low and obf_high 334/334 (integrity 100%); ctrl_para_legit
  para_high 210/334 (124 excluded, 37.1%, flagged; 18 excluded as "unchanged", a logical rule applied
  in every condition; QUESTIONS.md item 7). Items per detector per strategy: 334 + 1,002 + 1,327 + 544
  = 3,207. Two cache-sharing runs byte-identical (2026-10-26); cache spot check 171/179 generations
  identical (QUESTIONS.md item 8). Fixed artifact hashes in reports/variants_eval_fixed_artifacts.json.

## Working with the thesis author
- The author reviews methodology with a separate advisor chat; this repo implements what
  `docs/` specifies. If a spec is ambiguous or infeasible, stop and write the question into
  `docs/QUESTIONS.md` rather than guessing.
- When a script changes a number that appears in `docs/METHODOLOGY_3.2.md`, append the
  new value to `docs/CHANGES_FOR_THESIS.md` so the text can be updated.

@docs/PROJECT_STATE.md
