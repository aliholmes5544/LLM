# Archived: Mistral-7B-Instruct-v0.3 v1 cells, run without the system text (2026-10-28 to 2026-10-29)

Evidence for Section 4.8 (threats to validity), kept unchanged. QUESTIONS.md item 13, CHANGES_FOR_THESIS.md
entry of 2026-10-31.

What is here:

| path | content |
|---|---|
| `raw/{zero_shot,few_shot,cot,role}/eval.jsonl` | the four evaluation cells of mistral-7b (5,207 rows each) run on the Colab T4 at tags v0.6.1-detection-ready, 2026-10-29 |
| `smoke_dev/{strategy}.jsonl` | the laptop CPU smoke test of mistral-7b (20 dev items per cell), 2026-10-27 |
| `smoke_gpu/{strategy}.jsonl` | the Colab T4 smoke test of mistral-7b (same 20 dev items), 2026-10-28 |
| `detection_run_report_v1.json` | reports/detection_run_report.json as it stood with the four v1 Mistral cells |
| `integrity_check_v1.json` | reports/integrity_check.json of 2026-10-31 showing the four cells failing `system_text_delivered` |
| `smoke_dev_report_v1.json`, `smoke_backend_agreement_v1.json` | the smoke reports that include the v1 Mistral cells |

Why they were replaced: the GGUF's embedded chat template supports only user and assistant turns, and
llama-cpp-python 0.3.36 maps it to its built-in "mistral-instruct" formatter, which silently discards system
messages. With `system_role: true` in configs/models.yaml the runner sent the system text as a system message,
and the formatter dropped it, so in all four cells Mistral saw the user turn only (task instruction, email,
output rule; examples for few_shot; reasoning instruction for cot) and the role cell is byte-identical to the
zero_shot cell (same prompt token count on every item, same raw output on all 5,207 items). Found by
scripts/06_check_integrity.py (check `system_text_delivered`) on 2026-10-31, before any evaluation metric was
computed. The replacement cells (v0.6.2-detection-ready and later) use `system_role: false`, which prepends the
system text to the user turn exactly as for Gemma 2 (QUESTIONS.md item 9).

These files are valid, complete runs of a different prompt than intended and are not used for any result in
Chapter 4. Their sha256 values are recorded in `integrity_check_v1.json`.
