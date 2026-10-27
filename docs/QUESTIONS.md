# Open questions for the advisor (Claude Code appends here instead of guessing)

## Step 05 — variant derivation (2026-10-12)

1. **Subject line.** TASK_05 lists `subject` in the variant rows but the conditions describe body
   transformations only. Implemented: the subject is carried verbatim for all four conditions and
   only the body is paraphrased/obfuscated. Confirm.
2. **"50% / 100% of sentences".** Implemented over *eligible* segments: the body is split at sentence
   punctuation and at line breaks; a segment is rewritable only if it has at least 3 alphabetic words
   outside protected spans, is not a greeting line, and either ends with sentence punctuation or has
   at least 8 words. Greeting lines, job titles, company names, signature lines and link labels
   ("Access Project Document: the link") are copied verbatim and not counted: on the dev set this
   keeps 508 of 606 candidate segments (the 98 dropped are all structural lines with no propositional
   content, which the NLI check cannot judge). Confirm the denominator; `n_segments`, `n_eligible`,
   `n_selected` are recorded per variant.
3. **Calibration rule ("lowest values at which >= 95% of preserved variants pass").** Pass rate is
   monotone in the threshold, so this is read as the 5th percentile of the preserved variants' scores,
   i.e. the strictest threshold that still passes 95% of them. 05b implements that; confirm.
4. **Annotator disagreement.** 05b treats a paraphrase as "preserved" only when both annotators say
   so (`--rule both`); `--rule either` is available. Which rule should the thesis state?
5. **Numbers via NER.** CARDINAL (and a digit regex) protect every number, e.g. "3 days", which also
   removes those tokens from obfuscation eligibility. Keep, or restrict to amounts/dates/times only?
6. **> 5% sample failure -> review the whole condition.** 05b flags the condition; the full review is a
   manual step and is not automated. Confirm.

## Step 05 — evaluation variants (2026-10-26)

7. **Paraphrased legitimate control: 121 of 334 variants excluded (36.2 %).** The single frozen run
   on the evaluation partitions (reports/variants_eval_report.json) excluded 121 of the 334
   ctrl_para_legit/para_high variants (113 for achieved fraction below 0.80, 5 cosine below 0.68,
   2 length ratio, 1 cosine and length), against 9 of 334 (2.7 %) for core_pos/para_high and 4 of 100
   (4.0 %) on the dev set; the report flags the control because the difference exceeds 5 points. By
   subclass: enron_ham 98 of 222 (44.1 %), hard_ham 23 of 112 (20.5 %). Two facts explain it. (a) The
   100 dev para_high variants were all E-PhishLLM records (seeded draw from the 400-item dev set), so
   the thresholds and the 0.80 minimum were never exercised on Enron or hard-ham text during
   calibration. (b) The control emails are longer and more structured than either phishing source:
   median 8 segments per body (max 116), median 16 protected spans per record (NUMBER 3,573, PERSON
   2,205, ORG 1,829, DATE 577, EMAIL 220 across 334 records), 234 truncated generations; 518 of 3,624
   attempt-0 sentences failed the span test and 644 the NLI test, and once those sentences are
   reverted the fraction actually rewritten falls under 0.80. The accepted control therefore has 213
   variants (63 pass, 150 regenerated) where Table 3.2 states 334. Nothing was changed (the thresholds
   are frozen and the evaluation data are read-only); the decision rests with the author: (i) keep the
   control at 213 and report the exclusion with the subclass breakdown; (ii) something else, which the
   methodology text should specify first. Either way the thesis text should say that the control
   exclusion rate is not comparable with the dev estimate because the dev paraphrases came from
   E-PhishLLM only.

8. **Generation is not bit-reproducible on this backend (spot check 171/179).** Two runs of the
   evaluation derivation that share the generation cache are byte-identical, but regenerating 179
   cached sentences with the same seeds and the cache bypassed (scripts/05c_spot_check_cache.py,
   reports/variants_eval_spot_check.json) reproduced 171 and changed one to three words in 8
   (4.5 %), with identical spans, sentence selection and finish reasons. The likely cause is
   floating-point reduction order in multi-threaded CPU inference (n_threads 16, llama-cpp-python
   0.3.36), which can change the sampled token at temperature 0.7 even with a fixed seed; this was
   not tested (a single-thread rerun of the 8 sentences would show it). Consequences for Section
   3.8: (a) the determinism claim should be worded as "the released variants, logs and cached
   generations reproduce the evaluation data byte-for-byte; generation itself reproduces 95.5 %
   of sentences on the same hardware"; (b) the cache lives under data/interim (gitignored), so
   either the cache or data/processed/variants_eval.jsonl has to be published with the code for
   the derivation to be reproducible by others. The variants are derived from Nahmias et al.
   (2024), CC BY-NC-SA 4.0, so publishing them under the same licence is permitted; the decision
   and the wording are the author's.
