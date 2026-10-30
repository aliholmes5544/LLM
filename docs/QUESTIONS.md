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
   **Answered 2026-10-27 (author):** option (i). No threshold changed. Diagnosis only
   (scripts/05d_control_exclusion_diagnosis.py, reports/control_exclusion_diagnosis.json): the
   exclusions are sentence-level reverts on short, span-dense Enron bodies with few eligible
   sentences (1-4 eligible: 60 of 119 excluded; enron_ham 44.1 % vs hard_ham 20.5 %); interpretation
   in docs/CHANGES_FOR_THESIS.md (2026-10-27 entry). Control kept at 213 accepted variants.
   **Update 2026-10-27:** with the logical rule that a body byte-identical to its original is not a
   variant (reason "unchanged"; 18 control rows, 3 of them previously "pass"), the control has 210
   accepted variants and 124 exclusions (37.1 %). Table 3.2 updated to 1,327 variants, 544 controls,
   3,207 items per detector per strategy.

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
   **Answered 2026-10-27 (author):** data/processed/variants_eval.jsonl and
   data/interim/paraphrase_cache_eval.jsonl are the fixed evaluation artifact; downstream steps are
   byte-reproducible from them (run 2), generation is seeded but not bit-reproducible on the CPU
   backend (8/179 sentences differed by 1-3 words). sha256 of both files recorded in
   reports/variants_eval_report.json (fixed_artifacts) and docs/CHANGES_FOR_THESIS.md. Archived at
   submission under CC BY-NC-SA 4.0 (Nahmias licence), not in git.

## Step 06 — detection (2026-10-27)

9. **System message on models whose chat template has no system role.** TASK_06 section 2 puts the
   task definition (and, for `role`, the analyst persona) in the system message. The Gemma 2 chat
   template has only `user` and `model` turns; the model card of the GGUF notes "this model does not
   support a System prompt", and the embedded Jinja template rejects a system message. Implemented
   rule (configs/models.yaml `system_role: false`, configs/detection.yaml
   `system_role_fallback: prepend_to_user`): for gemma2-9b and gemma2-27b the system text is prepended
   to the user message, separated by a blank line, in every strategy; the prompt text itself is
   unchanged. Mistral-7B-Instruct-v0.3 accepts a system message but its own template folds it into the
   first user turn, so the two Gemma models receive the same wording as every other model, only in one
   turn. Consequence for the thesis: the `role` strategy differs from `zero_shot` by the system text
   for four models and by a user-message prefix for the two Gemma models; this is stated in Section
   3.5 and the per-model rendering is recorded in the raw results (prompt_hash per model). Please
   confirm or specify another handling.
   **Answered 2026-10-27 (author):** confirmed. The system text is prepended to the user message for the
   Gemma 2 models; the handling is noted in the run report.

10. **Few-shot examples: length cap and the scope of the persona check.** TASK_06 fixes the pool
    (`fewshot_pool` = traditional phishing + Enron ham), the counts (2 + 2), the seed and the
    persona/organisation rule, but not the example length. Four unrestricted examples (traditional
    phishing median 414 words, up to 600) plus a 600-word item would not fit n_ctx 4,096 with the
    prompt, so scripts/06_select_fewshot.py admits only bodies of 20 to 200 words
    (configs/detection.yaml `few_shot.min_words/max_words`; 254 of 2,299 traditional and 437 of 734
    Enron bodies qualify). The persona/organisation rule is implemented as: no PERSON or ORG entity
    token (spaCy en_core_web_sm, the step 05 model, tokens of at least 3 letters) shared with any
    `core_pos` original; `core_neg` is not included because its Enron mail shares "Enron" and Enron
    staff names with every Enron example and the rule's purpose is the SafeSecurity cast
    (METHODOLOGY_3.2.md Section 3.2.1). The step 04 near-duplicate check is re-applied to the chosen
    examples. Result (seed 2026, derive_rng("few_shot", class)): 21 candidates examined, 16 rejected
    for length, 1 for persona (shared tokens "mitchell", "williams"), 0 near-duplicates; chosen, in
    prompt order phish / legit / phish / legit:
    nah:traditional_phishing:84a636ab9a6e223503fc0a0d35767424 (161 words, advance-fee fraud),
    nah:enron_ham:15899597_1075855716918_JavaMail_evans_thyme (80 words, trading worksheet),
    nah:traditional_phishing:8f1706e54180856389c7d570674b2f2c (131 words, advance-fee fraud),
    nah:enron_ham:14352313_1075858637544_JavaMail_evans_thyme (26 words, a forwarded-message stub:
    header lines and "Here is the raw data file"). Two points for the author: (a) both phishing
    examples are 419-style fraud, which is what the Nahmias traditional collection mostly contains,
    so the examples do not show a credential-phishing pattern; (b) the fourth example is admissible
    under the 20-word minimum but carries little content. The draw is final under the current rule
    (no cherry-picking); if the author prefers a higher minimum (e.g. 40 words) the draw is repeated
    once with the new rule before any smoke test and the change is logged here and in
    CHANGES_FOR_THESIS.md. Nothing has been run against any model yet.
    **Answered 2026-10-27 (author):** redraw once with minimum body length 40 words (maximum 200) and
    the added rule that the two examples of the same label have word-level Jaccard similarity below
    0.30. Done before any model was run: slots 1 to 3 unchanged, slot 4 now
    nah:enron_ham:32834965_1075858643952_JavaMail_evans_thyme (99 words); same-label Jaccard 0.15
    (phishing) and 0.08 (legitimate). Old and new ids and the rule are logged in CHANGES_FOR_THESIS.md.

11. **Runtime of the laptop tier (2026-10-28).** The dev smoke test measured mean latencies of 5.6 to 8.9 s per
    inference on CPU (16 threads). The core evaluation (3,207 items x 4 strategies x 4 laptop models) projects to
    about 107 h, and the generalisation set (2,000 items x 4 strategies) adds about 66 h. Options: (a) run the
    laptop tier as planned over nights, in model order qwen25-7b, mistral-7b, llama31-8b, gemma2-9b, with completed
    cells cached so the run can be restarted; (b) move gemma2-9b and/or the generalisation set to Colab T4 (same
    GGUF, same decoding; only threads and GPU layers differ, which configs/cloud.yaml records); (c) reduce the
    generalisation set to a seeded subsample, which changes Table 3.2 and must be recorded in CHANGES_FOR_THESIS.md.
    (a) and (b) are not methodological changes. Awaiting the author's decision before 06_run_detection.py is run.

    **Answered 2026-10-28 (author):** all evaluation inference for all six models runs on Colab GPUs (T4 for the
    four laptop-tier models and Qwen2.5-14B; L4 for gemma-2-27b); the laptop is used for development and smoke tests
    only. Reason: identical hardware for all models removes a confound in RQ2, and the CPU projection (173 h) is not
    practical. The generalisation set is not subsampled. Implemented in configs/models.yaml (eval_tier, smoke_tiers),
    scripts/06_run_detection.py (--backend recorded per row) and notebooks/cloud_run.ipynb; estimate in
    CHANGES_FOR_THESIS.md.

## Pre-registration before step 07 (2026-10-31)

12. **Pre-registered secondary analyses and statistical plan (declared 2026-10-31, before any evaluation
    score was computed; results/raw exists but no metric has been calculated).** Declared by the author so
    that the analyses below can be reported as planned rather than exploratory. Nothing in this item was
    informed by an evaluation result: the only numbers seen so far are dev-partition smoke statistics
    (invalid rate, latency, token counts) and the eval item counts.

    (a) Ensemble detector: for each strategy, majority vote of the six detectors per item; an invalid
    prediction is an abstention; a 3-3 tie or fewer than 4 valid votes is scored as invalid. Reported as a
    seventh detector with the same metrics and deltas. No weighting, no tuning.

    (b) CoT rationale cue analysis: a fixed cue lexicon with the categories urgency, link/URL, sender/domain
    mismatch, credential/payment request, grammar/spelling, impersonation/authority, attachment, generic
    greeting. The lexicon (regex per category) is built and frozen from the dev-partition CoT outputs only,
    before being applied to eval. Report cue frequency per model and condition, and the change in cue
    frequency between an original and its paraphrase, split by whether the prediction flipped from correct
    to incorrect.

    (c) Hard-core analysis: items misclassified by all six models under zero_shot versus items misclassified
    by none, described by condition, body length, source and partition; a 30-item stratified random sample
    (seeded) of all-six failures for a qualitative error taxonomy coded by the author; descriptive only.

    (d) Cost-robustness frontier: median latency per inference (measured on the uniform GPU backend) against
    robustness delta, one point per (model, strategy).

    (e) Statistical plan for step 07: primary metric is the robustness delta (original minus variant) in
    sensitivity for phishing and in specificity for legitimate controls; 95% cluster bootstrap CIs with the
    original email as the cluster (B = 2000, seed 2026); McNemar for paired original-vs-variant comparisons;
    Holm correction within each family of comparisons (a family = one research question's set of tests),
    with uncorrected p-values also shown; effect sizes reported as differences in proportions with CIs;
    invalid outputs scored as incorrect in the primary analysis and excluded in a sensitivity analysis; the
    generalisation partitions reported separately and never pooled with the core set.

    Status: declared, not implemented. The git commit that records this item precedes every evaluation
    metric in the repository; any later change to (a) to (e) is logged here with its date and reason.
