# TASK 06 — Detection: models, prompting, inference, label extraction

Status: specification approved 2026-10-27 (decisions 1–4 confirmed by the author). Implements the detection stage of the evaluation framework (Chapter 3: §3.4 architecture, §3.5 components, §3.6 algorithm, §3.7 implementation). Results feed Chapter 4.

All rules in `CLAUDE.md` apply. In particular: evaluation partitions are read-only for development — **every prompt, parser rule, decoding setting and model choice is developed and smoke-tested on `dev` only**, frozen in `configs/detection.yaml`, and then run once on the evaluation items.

---

## 0. Inputs

| Input | Source | Notes |
|---|---|---|
| Originals | `data/processed/records.jsonl` + `data/processed/partitions.json` | `core_pos`, `core_neg`, `ctrl_modern_legit`, `gen_phish`, `gen_legit`, `dev`, `fewshot_pool` |
| Variants | `data/processed/variants_eval.jsonl` (fixed artifact; sha256 in `reports/variants_eval_fixed_artifacts.json`) | accepted rows only; `core_pos` × {para_low, para_high, obf_low, obf_high}, `ctrl_para_legit` × {para_high} |
| Dev variants | `data/processed/variants_dev.jsonl` | for smoke tests and parser development |
| Detector input | **`subject` + `body` only** | never sender, headers, URLs, attachments |

The evaluation item set per (model, strategy) is: all `core_pos` originals, all `core_neg`, all `ctrl_modern_legit`, all accepted `core_pos` variants, all accepted `ctrl_para_legit` variants, and the `gen_*` partitions (generalization test, reported separately). The exact count is whatever `04_partition` + `05` produced (recorded in `docs/CHANGES_FOR_THESIS.md`); do not hard-code it.

## 1. Models (decision 1)

Six open-weight instruction-tuned models, GGUF **Q4_K_M**, run through **llama.cpp** (`llama-cpp-python`, pinned version in `requirements.txt`) on both the laptop and Colab so the backend is identical.

| key | model | params | licence (record verbatim from the model card) | tier |
|---|---|---|---|---|
| `llama31-8b` | Meta-Llama-3.1-8B-Instruct | 8B | Llama 3.1 Community License (open-weight) | laptop |
| `mistral-7b` | Mistral-7B-Instruct-v0.3 | 7B | Apache-2.0 | laptop |
| `gemma2-9b` | gemma-2-9b-it | 9B | Gemma Terms of Use (open-weight) | laptop |
| `qwen25-7b` | Qwen2.5-7B-Instruct | 7B | Apache-2.0 | laptop |
| `qwen25-14b` | Qwen2.5-14B-Instruct | 14B | Apache-2.0 | Colab T4 |
| `gemma2-27b` | gemma-2-27b-it | 27B | Gemma Terms of Use (open-weight) | Colab L4 |

Rules:
- **Exclude the paraphrase model.** Read `configs/variants.yaml`; if the paraphrase model (or another size of the same family and generation) is in the table, drop it and tell the author before substituting. The detector set must not include the model that produced the variants.
- Record for each model: exact repository and file name of the GGUF, sha256 of the file, quantization, context length used, chat template applied, licence string. Write to `configs/models.yaml`; no weights in git.
- Context: 4,096 tokens is sufficient (bodies ≤ 600 words). If an item plus prompt exceeds the context, log it as `truncated_input` and truncate the body at a sentence boundary; report the count.
- Thread/GPU settings are per-tier in `configs/local.yaml` and `configs/cloud.yaml`; they affect speed only. Decoding is identical everywhere.

## 2. Prompting strategies (decision 2)

Four strategies; `zero_shot` is the reference condition for RQ3. Prompts live in `prompts/` as plain text with `{subject}` and `{body}` placeholders; the full text goes in the thesis appendix.

| key | content |
|---|---|
| `zero_shot` | system: brief task definition. user: instruction + subject + body + output rule. |
| `few_shot` | `zero_shot` + **4 fixed labelled examples** (2 phishing, 2 legitimate) drawn once from `fewshot_pool` with the project seed, identical for every model and every item; the examples must not share a persona/organisation with any Nahmias evaluation item (checked by the same rule as in step 04). |
| `cot` | `zero_shot` instruction + "First analyse the message in a few sentences, then give the final answer on its own line in the form `FINAL: PHISHING` or `FINAL: LEGITIMATE`." |
| `role` | `zero_shot` with the system message replaced by an email-security-analyst persona. User message identical to `zero_shot`. |

Output rule used in all four (CoT appends it after the analysis): **"Answer with exactly one word: PHISHING or LEGITIMATE."**

Decoding (identical for every model/strategy): greedy (`temperature = 0`), fixed seed, `max_tokens = 16` for `zero_shot`/`few_shot`/`role`, `max_tokens = 256` for `cot`, no stop-sequence tricks beyond the chat template's end token. One run per cell; greedy decoding makes repeated runs redundant, which is stated in §3.7.

Prompt development is done **only on `dev`** and only to fix format compliance (e.g. a model that ignores the one-word rule), never to improve accuracy. Every prompt revision is logged in `docs/CHANGES_FOR_THESIS.md` with the dev invalid-rate before and after. Prompts are then frozen (hash recorded).

## 3. Baselines (decision 3)

Trained on `train` (traditional phishing + legitimate) and validated on `valid`, following the Nahmias protocol; evaluated on the same evaluation items as the LLMs (originals and variants, text = subject + body).

| key | method | notes |
|---|---|---|
| `tfidf_lr` | TF-IDF (word 1–2-grams, min_df 2) + logistic regression | C chosen on `valid` |
| `tfidf_svm` | TF-IDF (same features) + linear SVM | C chosen on `valid` |
| `distilbert` | DistilBERT-base-uncased fine-tuned, 3 epochs, lr 2e-5, batch 16, max 512 tokens, seed fixed | runs on Colab T4; checkpoint hash recorded; not in git |
| `proprietary_ref` | one proprietary model, **zero-shot only**, same prompt as `zero_shot`, temperature 0 | reference point, not a study detector (Chapter 1 scope). Model name, API version, date and cost recorded. Requires `OPENAI_API_KEY` (or equivalent) in `.env`. Skipped cleanly if the key is absent. |

## 4. Label extraction (decision 4) — `scripts/common.py: extract_label(text, strategy)`

Deterministic, no retries:

1. Normalise: lowercase; strip punctuation and whitespace runs.
2. If `strategy == "cot"`: take the text after the **last** occurrence of `final:`; if there is none, use the whole output.
3. Search the resulting span for the tokens `phishing` and `legitimate` (whole-word).
4. Exactly one token present → that label. Both, neither, or empty output → **`invalid`**.
5. `invalid` is scored as an **incorrect** prediction in the primary analysis; the invalid rate is reported per model × strategy, and a sensitivity analysis excluding invalid items is reported alongside.

Unit tests in `tests/test_extract_label.py` cover: clean answers, lowercase, trailing punctuation, both tokens, neither, empty, CoT with and without `FINAL:`, CoT where the analysis mentions both words but the final line is one.

## 5. Scripts

| script | does |
|---|---|
| `scripts/06_download_models.py` | downloads the GGUF files listed in `configs/models.yaml` to `models/` (ignored), verifies sha256, records licence strings. |
| `scripts/06_run_detection.py` | `--model KEY --strategy KEY --partition {dev,eval}`. Builds the item list, renders prompts, runs llama.cpp, writes **one row per item** to `results/raw/{model}/{strategy}/{partition}.jsonl` with: `item_id`, `partition`, `condition` (original / para_low / …), `label_true`, `raw_output`, `label_pred`, `invalid` flag, `prompt_hash`, `model_hash`, `n_prompt_tokens`, `n_output_tokens`, `latency_s`, `truncated_input`. Resumable: skips items already present. Never overwrites a finished eval file (refuses; requires `--force` with a logged reason). |
| `scripts/06_run_baselines.py` | trains and evaluates the three baselines; same output schema under `results/raw/baseline_*/`. |
| `scripts/06_run_proprietary.py` | the reference run; same schema; skipped without a key. |
| `scripts/06_smoke_dev.py` | runs every model × strategy on 20 dev items (10 + 10), reports invalid rate and latency per cell. **Gate:** no eval run starts until every cell has invalid rate ≤ 10 % on dev; otherwise the prompt is revised (logged) or the model's inability is documented and it is still run as is. |
| `run_detection_local.sh` / `notebooks/cloud_run.ipynb` | laptop tier / Colab tier orchestration; the notebook clones the repo at a tag, downloads models, runs the cloud-tier cells, and copies `results/raw/` back to Drive and to the repo. |

Scoring (metrics, deltas, bootstrap, McNemar) is **step 07**, not here. Step 06 produces only raw predictions.

## 6. Order of work

1. `configs/models.yaml`, `configs/detection.yaml`, prompts, `extract_label` + tests. Commit.
2. Smoke test on dev for the laptop-tier models (4 × 4 cells × 20 items). Fix format problems only. Freeze prompts; record hashes. Commit.
3. Full dev run for one model (all strategies) to measure throughput; estimate eval time per tier; write the estimate to `docs/CHANGES_FOR_THESIS.md`.
4. Baselines on `valid` (sanity: F1 on valid should be high) — then on eval.
5. Eval runs, laptop tier. Each (model, strategy) is a separate resumable job; push results after each.
6. Colab tier: tag the repo, run the notebook, pull results back.
7. Proprietary reference (if key present).
8. Integrity: a script that verifies every eval results file has exactly the expected item set, no duplicates, prompt and model hashes equal to the frozen ones. Only then step 07.

## 7. Definition of done

- `configs/models.yaml`, `configs/detection.yaml`, `prompts/*.txt` frozen with hashes recorded.
- `results/raw/` complete for 6 models × 4 strategies + 3 baselines (+ reference), every file passing the integrity check.
- Per-cell invalid rates and latencies in `reports/detection_run_report.json`.
- Every prompt revision, every model substitution and every throughput estimate logged in `docs/CHANGES_FOR_THESIS.md`.
- No evaluation item was used to choose or change anything.
