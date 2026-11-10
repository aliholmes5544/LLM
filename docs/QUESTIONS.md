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

    Status: declared 2026-10-31, not implemented at that date. The git commit that records this item precedes
    every evaluation metric in the repository; any later change to (a) to (e) is logged here with its date and
    reason. **Implemented 2026-11-01 (TASK_07 step 3, the first and only computation of the scores, commit
    "Step 07: scores computed (first and only computation)", tag v0.7.1-scored)** under (a) to (e) with
    refinements (1) to (7) below and the decisions of items 15 and 16; the only departure from the plan that the
    data forced is the hard-core sample size (item 17), whose post hoc extension is the one deviation logged below.

    **Refinements logged 2026-11-01, before any score was computed (decisions on item 15, author):**
    (1) Families named by the thesis research questions: F-RQ4 = the 30 zero_shot McNemar tests (24 phishing
    original-vs-variant, 6 control), the headline family; F-RQ2 = 8 size contrasts (Qwen 7B vs 14B, Gemma 9B
    vs 27B, delta-sens per phishing condition, zero_shot); F-RQ3 = 36 strategy-vs-zero_shot contrasts (3
    strategies x 6 models x para_high and obf_high). RQ1 (capability, generalisation) is descriptive with CIs
    and has no test family. Secondary families, Holm within each: the McNemar tests of each other strategy
    (one family per strategy), of the three baselines (one family) and of the ensemble (one family).
    (2) A contrast tested by the cluster bootstrap gets a two-sided percentile p = 2 x min(P(contrast <= 0),
    P(contrast >= 0)), floored at 1/B; the CI is the primary report. Reason: item 12e names Holm for every
    family but defines no p-value for a bootstrap contrast.
    (3) Item 12b: the cue-change split is four-way (stayed correct / flipped to incorrect / stayed incorrect /
    flipped to correct); it contains the two-way split declared above. Reason: the two added groups are needed
    to read a flip against its base rate.
    (4) Item 12c: "all six" = the six language models under zero_shot (baselines excluded); invalid counts as
    misclassified; the 30-item sample is stratified by the four phishing conditions, proportional allocation
    with a minimum of 5 per condition when available, seed 2026. Reason: the strata were unspecified.
    (5) Power note for Section 4.8: a priori, 10% discordant pairs, 5-point paired drop, n = 334, alpha 0.05;
    the observed discordance is reported post hoc as a labelled descriptive check.
    (6) Item 12e, sensitivity analysis without invalid outputs: for paired deltas and McNemar tests a pair is
    dropped when either member is invalid, so original and variant keep the same n; unpaired rates drop the
    invalid items of the condition. Reason: 12e did not say how exclusion applies to pairs (item 15h,
    2026-11-01).
    (7) Item 12b, cue lexicon frozen 2026-11-01 before any eval rationale was read: configs/cue_lexicon.yaml,
    sha256 e209c7a565add8bf7d88595b94d3f7174535ec93c6b35206225c58b8f43822fd,
    written by hand from 4,956 dev rationales (the six full-dev CoT cells of tag v0.7.0-devcot plus the smoke sets;
    reports/cue_lexicon_dev_report.json). Two refinements of 12b: each category holds several named sub-patterns
    (reported separately), and every match carries a polarity (asserted, or negated when a negation marker
    earlier in the same clause is not followed by a conjunction plus an asserting verb), because on dev most
    cue mentions in legitimate verdicts are denials ("does not contain any suspicious links"). Reason: 12b
    said "regex per category" and did not foresee negated mentions. Reporting choices in item 16.

    **Deviation logged 2026-11-01, after the scores were computed (decision on item 17, author):** item 12c,
    refinement (4), is kept as computed: only 8 items met the pre-registered criterion (all six models wrong on a
    phishing variant), and they are reported as the pre-registered sample. A clearly labelled post hoc extension is
    added for the qualitative coding only: phishing items (originals and variants) misclassified by at least 4 of
    the 6 language models under zero_shot, five strata (original plus the four variant conditions), the 8
    pre-registered items excluded, proportional allocation with a minimum of 5 per stratum where available, seed
    2026, 30 items (reports/hardcore_sample.csv, column `set` = preregistered | posthoc). Reason: only 8 items met
    the pre-registered criterion. The extension changes no computed number; its counts per stratum before sampling
    are in reports/secondary_report.json (`hardcore.sample.posthoc`) and in item 17.

    **Deviation logged 2026-11-09, after the scores were computed (supervisor request; item 18):** a two-stage
    indicator detector (docs/TASK_08_twostage.md) is added as an exploratory, post hoc, additional evaluated
    condition for three of the six models. Reason: requested by the supervisor after the step-07 scores were
    computed. Nothing in (a) to (e), the families or the Holm corrections changes; the two-stage detector gets its
    own families A-twostage-{model} and separate output files; RQ1 to RQ4 are unchanged.

## Step 06 integrity check of the evaluation results (2026-10-31)

13. **Mistral-7B received no system message in any strategy (found by 06_check_integrity.py, 2026-10-31).**
    Evidence: for every item the role prompt of Mistral-7B has the same token count as its zero_shot prompt
    (5,207 of 5,207 items; the five other models show exactly +32 tokens for the longer role system text), and
    the two cells' raw outputs are byte-identical on all 5,207 items; the CPU smoke test shows the same
    pattern (20 of 20). Cause, verified on the laptop by loading the GGUF vocabulary and rendering the
    runner's messages: the template embedded in Mistral-7B-Instruct-v0.3-Q4_K_M.gguf supports only user and
    assistant turns, llama-cpp-python 0.3.36 maps it to its built-in "mistral-instruct" formatter, and that
    formatter silently drops every message whose role is not user or assistant. The messages the runner built
    did contain the system text (system_role: true in configs/models.yaml); it was discarded at formatting.
    Item 9's premise that the Mistral template folds the system message into the first user turn was wrong,
    and the smoke test could not detect the loss because it checks output format only. The item sets, hashes,
    backend, GPU and parser checks all pass for the four Mistral cells; they are complete, valid runs of a
    different prompt than intended: user turn only (task instruction, email, output rule, and for few_shot the
    examples, for cot the reasoning instruction), without the one-sentence system framing, and with role
    identical to zero_shot. The other five models are unaffected.
    Options: (a) set system_role: false for mistral-7b (the prepend rule already used for Gemma 2, item 9),
    add a guard in scripts/detect/backend.py that refuses to run a model whose chat format resolved to a
    built-in llama-cpp-python formatter while system_role is true, rerun the Mistral dev smoke test (gate),
    then rerun the four Mistral eval cells on the T4 with --force --reason "system message dropped by
    formatter, item 13" (the runner archives the current files next to the new ones; about 6.3 h of
    inference, about 7 compute units) and rerun 06_check_integrity.py; the thesis then states that
    Mistral-7B, like Gemma 2, receives the system text in the user turn. (b) Keep the current Mistral files,
    report Mistral under "no system framing" for zero_shot, few_shot and cot, and exclude the Mistral role cell
    (no role condition exists for it); this leaves RQ3 incomplete for one of six models and makes the Mistral
    columns not comparable with the others. Recommendation: (a); it is cheap, keeps the design uniform and is
    still a change made before any evaluation score was computed (the pre-registration of item 12 is not
    affected, as no metric has been calculated). Until answered, no Mistral result is used in step 07 and the
    current Mistral files stay in results/raw/ unchanged (they are what was run; the integrity report records
    their hashes and the failed check).
    **Answered 2026-10-31 (author):** option (a). Implemented in v0.6.2-detection-ready: system_role false for
    mistral-7b (prepend as for Gemma 2), guard in scripts/detect/backend.py against built-in formatters with
    system_role true, tests/test_system_text.py (system text delivered, role longer than zero_shot by the system
    tokens, for every model whose GGUF is present; run on Colab for the 14B and 27B), v1 Mistral cells and
    smoke rows archived under results/archive/mistral-7b_v1_no_system_text/, Mistral CPU smoke test rerun
    (0 invalid of 80, gate PASS in every cell), notebook fixes. The four Mistral evaluation cells and the
    Mistral GPU smoke test are rerun on Colab (TAG v0.6.2-detection-ready, MODELS mistral-7b). Details and
    thesis wording in CHANGES_FOR_THESIS.md (2026-10-31, v0.6.2).
    **Rerun complete 2026-11-01 (v0.6.3-detection-complete):** the four v2 Mistral cells pass
    06_check_integrity.py (24 of 24 cells, system_text_delivered true for every model, role prompt 32 tokens
    longer than zero_shot on every item); invalid 10 / 5 / 68 / 0 (zero_shot / few_shot / cot / role) against 117 / 15 / 288 / 117 in v1;
    GPU smoke 0 invalid of 80; CPU/GPU label agreement 80 of 80 for Mistral and 319 of 320 overall. Item closed.


## Step 06 baselines and proprietary reference (2026-11-01)

14. **Proprietary zero-shot reference (TASK_06 section 3, item 7 of section 6): may the evaluation e-mails be
    sent to a third-party API?** The reference run would send the subject and body of all 5,207 evaluation items
    (334 Nahmias spear-phishing e-mails and their variants, Enron and SpamAssassin ham, and 2,000 E-PhishLLM
    messages) to a commercial API. The Nahmias data are CC BY-NC-SA 4.0 (use for research is fine; the
    provider's terms on retention and training on submitted content are the question), and E-PhishLLM has no
    licence file (we do not redistribute it; an API call is transmission to a processor, not publication, but
    the authors' intent is unknown). Options: (a) run the reference with a provider whose API terms exclude
    training on customer content and state a retention limit, and record provider, model id, version, date,
    terms version and cost in the report; (b) run it on the Nahmias-derived partitions only (core_pos,
    variants, core_neg, controls) and skip gen_phish and gen_legit; (c) skip the reference (the scope allows
    it: "points of comparison", skipped cleanly without a key). Recommendation: (a) if the provider's terms are
    acceptable to the author, else (b). Until answered, scripts/06_run_proprietary.py is not written.
    **Answered 2026-11-01 (author):** the proprietary reference run is dropped. Reasons: (1) a proprietary model
    is outside the scope of Section 1.6 (open models run locally); (2) the licence status of the E-PhishLLM
    e-mails does not clearly permit their transfer to a third-party API; (3) a proprietary comparison is noted
    as future work in Chapter 5. scripts/06_run_proprietary.py is not written; `proprietary_ref` is removed from
    the TASK_06 definition of done and from CLAUDE.md. Item closed; tag v0.6.4-baselines-ready.


## Step 07 scoring specification: points that need the author's decision before any score is computed (2026-11-01)

15. **Ambiguities in docs/TASK_07_scoring.md and places where it extends QUESTIONS.md item 12.** Found while
    implementing step 1 (item table) and preparing step 2 (cue lexicon); none is resolved here. (a) to (f)
    concern step 3 only; (g) must be answered before step 2.

    (a) **Research-question numbering.** TASK_07 section 0 names RQ1 = robustness, RQ2 = model size, RQ3 =
    prompting strategy, and the Holm families F-RQ1, F-RQ2, F-RQ3 follow that scheme. The thesis (PROJECT_STATE
    section 2; METHODOLOGY_3.2 Tables; Table 3.1) has RQ1 = effectiveness, RQ2 = comparison across open models
    and the ML/DL baselines, RQ3 = zero-shot vs prompt-engineered, RQ4 = robustness under paraphrase and
    obfuscation; "model size" is one contrast inside RQ2, not a research question. Which labels go into the
    output files, tables and the CHANGES wording, and does the size family cover only the two size pairs
    (Qwen 7B vs 14B, Gemma 9B vs 27B) or every model comparison of RQ2 (including detectors vs baselines)?
    Item 12e says "a family = one research question's set of tests".

    (b) **Family membership of the other McNemar tests.** TASK_07 section 3 puts only the zero_shot tests of the
    six models (6 x 4 phishing conditions + 6 control tests = 30) into F-RQ1. deltas_long.csv also carries a
    McNemar p for every paired test under few_shot, cot and role (T4), for the three baselines and for the
    ensemble (item 12a: "scored as a seventh detector in every table"). Options: (i) those p-values are shown
    uncorrected only, with the family column empty; (ii) one family per strategy (F-RQ1 is the zero_shot one);
    (iii) one family holding all 7 detectors x 4 strategies x 5 tests plus the baselines. Default if
    unanswered: none; step 3 does not start.

    (c) **p-value of a bootstrap contrast.** F-RQ2 and F-RQ3 are "tested by cluster-bootstrap difference of
    deltas" and Holm-corrected, but no p-value is defined for a bootstrap contrast. Options: (i) two-sided
    percentile bootstrap p = 2 x min(P*(diff <= 0), P*(diff >= 0)), floored at 1/B, with the same B = 2000 and
    the per-table RNG stream; (ii) CIs only for RQ2/RQ3 contrasts, no p and no Holm. Item 12e is silent on this.

    (d) **Cue-change split.** Item 12b splits the original-vs-paraphrase cue change by "whether the prediction
    flipped from correct to incorrect" (two groups); TASK_07 section 4(b) uses four groups (stayed correct /
    flipped to incorrect / stayed incorrect / flipped to correct). The four-way split contains the two-way one.
    Confirm, and log it in item 12 as a refinement with today's date (the log must precede the computation).

    (e) **Hard-core sample.** Item 12c and TASK_07 section 4(c) ask for a seeded stratified sample of 30 all-six
    failures without naming the strata. Options: (i) by condition (original, para_low, para_high, obf_low,
    obf_high: 6 each); (ii) by condition x source (Nahmias phishing vs legitimate corpora); (iii) by item class.
    "All six" = the six language models under zero_shot, baselines excluded (reading of item 12c), to confirm.
    Invalid counts as misclassified (primary rule), to confirm.

    (f) **Power note.** TASK_07 section 3 asks for the McNemar power "under typical discordance" and "state the
    computed figure". Power depends on the assumed discordant proportion. Options: (i) a priori assumption
    stated now (for example 10%, 15% and 20% discordance for a 5-point paired drop, n = 334, alpha 0.05);
    (ii) the observed discordance of the zero_shot cells, which is post hoc and would be labelled as such.

    (g) **Basis of the CoT cue lexicon (blocks step 2).** The only dev CoT outputs in the repository are the
    smoke sets: 20 dev items (10 phishing, 10 legitimate) x 9 cells (CPU: gemma2-9b, llama31-8b, mistral-7b,
    qwen25-7b; GPU: the same four plus qwen25-14b) = 180 rationales about 20 distinct e-mails; gemma2-27b has no
    dev CoT output at all. TASK_07 section 0 names exactly these files. Options: (i) freeze the lexicon on these
    180 rationales as specified; (ii) first run the cot strategy on the full dev partition (400 originals + the
    accepted dev variants) for the four laptop models on the CPU (dev only, permitted by CLAUDE.md; roughly
    400 to 580 items x 4 models x about 12 s = 5 to 8 h of laptop time) and freeze on that; (iii) (ii) plus
    qwen25-14b and gemma2-27b on Colab (about 1 compute unit). The lexicon's regexes would be written by hand
    from reading the dev rationales and frozen with a hash; a larger basis reduces the risk that an eval
    rationale uses a phrasing the lexicon never saw, which would then be a (documented) limitation, not an
    error. Recommendation: (ii), because the cost is one laptop night and the lexicon is applied to 31,242 eval
    rationales.

    (h) **Sensitivity analysis on paired deltas.** Item 12e: invalid outputs are "excluded in a sensitivity
    analysis". For an unpaired rate the exclusion is clear; for a paired delta and its McNemar test, options:
    (i) drop a pair when either member is invalid (keeps the pairing; same n for original and variant);
    (ii) drop invalid items from each condition separately (unpaired denominators). The ensemble (item 12a)
    turns ties and sparse votes into invalid, so this choice affects it most.

    (i) **Readings taken as given unless corrected** (no decision needed if correct): spec(original) is reported
    separately for core_neg (1,002) and ctrl_modern_legit (334), as the TASK_07 table lists them; the paired
    specificity for the control delta uses the 210 core_neg originals that have an accepted para_high variant;
    acc, bal_acc and f1_phish on "core originals" use core_pos + core_neg + ctrl_modern_legit (1,670 items);
    the bootstrap RNG of a table is derive_rng(2026, "bootstrap", <table name>) in the project's seeding scheme,
    so every table is reproducible independently of execution order; the hard-core "body length" is the word
    count of the scored text (body_words in items.parquet).

    **Answered 2026-11-01 (author), (a) to (f); (g) and (h) pending.**
    (a) Thesis numbering everywhere in outputs, tables and wording: RQ1 effectiveness (capability on core
    originals and the generalisation set; descriptive with CIs, no test family); RQ2 model comparison (family
    F-RQ2 = the two size pairs Qwen 7B/14B and Gemma 9B/27B, contrasts on delta-sens per phishing condition
    under zero_shot = 8 contrasts; every other model comparison descriptive); RQ3 prompting (family F-RQ3 =
    3 strategies x 6 models x 2 conditions = 36 contrasts); RQ4 robustness (family F-RQ4 = the 30 zero_shot
    McNemar tests: 24 phishing + 6 control). TASK_07 relabelled accordingly.
    (b) The McNemar tests under few_shot, cot and role, for the three baselines and for the ensemble are
    computed and reported with Holm applied within each as its own secondary family (one family per strategy,
    one for the baselines, one for the ensemble). They are secondary; F-RQ4 is the headline.
    (c) Two-sided percentile-bootstrap p for every contrast: p = 2 x min(P(contrast <= 0), P(contrast >= 0)),
    floored at 1/B; stated in the Section 4.3 wording. CIs remain the primary report.
    (d) Confirmed: the four-way split (stayed correct / flipped to incorrect / stayed incorrect / flipped to
    correct) refines the two-way split of item 12b and contains it; logged in item 12 on 2026-11-01.
    (e) Confirmed: "all six" = the six language models under zero_shot, baselines excluded; invalid counts as
    misclassified. Strata = the four phishing conditions; allocation proportional to the number of all-six
    failures per condition with a minimum of 5 per condition when available; seed 2026.
    (f) A priori: assume 10% discordant pairs and report the McNemar power for a 5-point paired drop (n = 334,
    alpha 0.05); also report the observed discordance post hoc as a descriptive check, labelled as such.
    (g) **Answered 2026-11-01 (author):** run the cot strategy on the full dev partition for all six models on
    Colab (uniform GPU backend, dev only), not on the laptop: STRATEGIES = cot only; the dev item set is the
    runner's normal one, dev originals AND the accepted dev variants, because the lexicon must see rationales
    written about paraphrased and obfuscated text (796 items: {'original': 400, 'para_low': 100, 'para_high': 96, 'obf_low': 100, 'obf_high': 100}); run from tag
    v0.7.0-devcot; the lexicon is frozen on the full-dev rationales plus the smoke sets. L4 handling for
    gemma2-27b with PARTITION = dev confirmed from the code: the runner applies the eval_tier check to eval
    runs only, the notebook selects the models of the chosen TIER and asserts the GPU, and the dev rows go to
    results/raw/gemma2-27b/cot/dev.jsonl (report cell gemma2-27b/cot/dev), synced to Drive. Parameters and
    time estimate in CHANGES_FOR_THESIS.md (2026-11-01, v0.7.0-devcot).
    (h) **Answered 2026-11-01 (author):** drop the pair when either member is invalid (same n for original and
    variant). Logged in item 12 as refinement (6).
    (i) **Answered 2026-11-01 (author):** all four readings confirmed. Item 15 complete.

## Step 07 step 2: cue lexicon frozen; reporting choices for the cue analysis (2026-11-01)

16. **Cue lexicon: how the frequencies are reported in step 3 (item 12b, TASK_07 section 4b).** The lexicon is
    frozen (configs/cue_lexicon.yaml, sha256 e209c7a565add8bf..., full hash in item 12 refinement 7) and was
    developed on dev only: 4,956 rationales, of which 369 (7.4%) are empty (the model wrote only the
    FINAL line; qwen25-7b 276 of 836, mistral-7b 93 of 836). Among the non-empty rationales
    86.3% assert at least one category; 30% of the link mentions are negated. Defaults below are
    applied in step 3 unless the author decides otherwise; none of them requires re-freezing the lexicon, since
    sub-patterns and polarity are recorded per match.

    (a) **Frequency = asserted mentions.** Default: "cue frequency" in T10 and F6 is the share of rationales that
    assert the category (at least one match outside a negation scope); negated-only mentions are reported in a
    separate column, not added to the frequency. Alternative: count any mention regardless of polarity (the
    literal reading of 12b), which would make "no suspicious links" a link cue.
    (b) **Denominator = rationales with text.** Default: per cell (model x condition) the denominator is the
    number of rows with a non-empty rationale, and the empty-rationale rate is reported as its own column (on
    dev it is 33% for qwen25-7b and 11% for mistral-7b, 0 for the others). Alternative: all rows of the
    cell, which deflates the frequencies of the two models that often skip the reasoning.
    (c) **Sub-pattern placement.** Four placements are judgment calls within the eight pre-registered categories
    and are frozen as named sub-patterns so that each can be excluded by name in step 3 without re-freezing:
    pressure_threat (threats, pressure, suspension) under urgency; character_anomaly (inserted spacing,
    homoglyphs, digit-for-letter substitutions, which the models describe as misspellings) under grammar /
    spelling; malware (malware, virus, infected) under attachment; authority_figure (a CEO, IT department or
    other authority is named, whether or not impersonation is alleged) under impersonation / authority.
    Default: keep all four.
    (d) **Readings taken as given unless corrected:** the cue-change analysis of 12b uses the primary analysis
    (invalid = incorrect) for the four-way outcome split of item 15d; a pair enters the cue-change table only
    when both members have a non-empty rationale (the change in cue presence is undefined otherwise), and the
    number of pairs excluded for this reason is reported; the polarity heuristic is applied as frozen and its
    known failure modes (a "lack of X, the Y, ..." list leaks the negation onto Y; "without verifying the
    attachment" negates an existing attachment) are stated as a limitation in Section 4.8, not corrected by hand.

    **Answered 2026-11-01 (author), item closed:** (a) confirmed, frequency = asserted mentions, negated in a
    separate column; (b) confirmed, denominator = rationales with text, empty-rationale rate as its own column;
    (c) keep the four judgment-call sub-patterns in the primary cue analysis as frozen, no exclusion variant (the
    categories were pre-registered and the lexicon is frozen; an exclusion variant would add analyses not in the
    plan); (d) confirmed. Implemented in scripts/07_secondary.py (cues_frequency.csv, cues_change.csv, cues_pairs.csv).

## Step 07 step 3 computed: hard-core sample smaller than pre-registered (2026-11-01)

17. **Hard-core sample (item 12c, refinement 4): only 8 eligible items, not 30.** Under zero_shot, 102 of the
    5,207 items are misclassified by all six language models, but only 8 of them lie in the four pre-registered
    strata (phishing variants: para_low 5, para_high 3, obf_low 0, obf_high 0). The
    other all-six failures are 39 generalisation-set phishing e-mails, 34 core legitimate e-mails,
    14 paraphrased legitimate controls and 7 phishing originals. The script applied the rule as written
    (minimum 5 per condition "when available", proportional allocation) and drew all 8 eligible items
    (seed 2026); reports/hardcore_sample.csv holds them with the coding columns, and the texts are in
    data/processed/hardcore_sample_text.jsonl. This is reported as a result in itself (obfuscation and, to a
    lesser degree, paraphrase make the phishing e-mails easier for every model, so near-unanimous misses are rare
    on variants). Options for the qualitative coding, for the author to decide; none changes a computed number:
    (i) code the 8 items as drawn (the pre-registered sample, undersized);
    (ii) add, as a clearly labelled post hoc extension, the 7 phishing originals missed by all six (the same
    coding guide applies) and a seeded sample of the 48 legitimate e-mails called phishing by all six (false
    positives, which need a different code list);
    (iii) also sample the 39 generalisation-set failures (E-PhishLLM), reported apart from the core set.
    Recommendation: (ii), because the false positives are where the hard core actually is, and the coding guide
    (docs/HARDCORE_CODING_GUIDE.md) can take a second code list for them.

    **Answer (author, 2026-11-01):** keep the pre-registered sample as computed (the 8 all-six failures among the
    phishing variants) and report it as such. Add a clearly labelled post hoc extension, logged in item 12 as a
    deviation with the reason "only 8 items met the pre-registered criterion": items missed by at least 4 of the
    6 language models under zero_shot, across five strata (original plus the four variant conditions),
    proportional allocation with a minimum of 5 per stratum where available, seed 2026, 30 items. Both sets go to
    reports/hardcore_sample.csv (column `set` = preregistered | posthoc); the coding guide asks, for an original,
    "why does this spear-phishing e-mail look legitimate?" and, for a variant, "what changed relative to the
    original?". Legitimate e-mails called phishing (options ii and iii) are not sampled.
    **Implemented 2026-11-01** (scripts/07_secondary.py, commit "Hard-core sample: pre-registered 8 + post-hoc 30
    (item 17)"). Items missed by at least 4 of 6 among the phishing originals and variants, before sampling:
    original 119, para_low 70, para_high 47, obf_low 3, obf_high 0 (239); after removing the 8 pre-registered
    items (all variants): 119, 65, 44, 3, 0 (231). Allocation of the 30 (proportional, largest remainder, minimum
    5 where at least 5 are available): original 16, para_low 8, para_high 6, obf_low 0, obf_high 0. The three obf_low items
    receive no slot because the stratum holds fewer than the minimum of 5 and its proportional share rounds to
    zero; the rule was applied as written. The post hoc sample is drawn from a separate random stream
    ("hardcore_sample_posthoc", seed 2026), so the pre-registered rows are unchanged (sample_id 1 to 8); the post
    hoc rows are sample_id 9 to 38. Status: closed; the author's manual coding of the 38 rows is pending.

## TASK_08 two-stage indicator detector: deviation and open points before step 2 (2026-11-09)

18. **Exploratory, post hoc addition at the supervisor's request (docs/TASK_08_twostage.md, specification
    2026-11-09).** Deviation from the pre-registered plan of item 12, logged with its date and reason: after the
    step-07 scores were computed (2026-11-01, tag v0.7.1-scored), the supervisor asked for a two-stage pipeline
    (indicator extraction by the same language model, then one logistic regression per model) to be evaluated as
    an **additional condition inside the existing framework**, for `qwen25-7b`, `gemma2-9b` and `gemma2-27b`. It is
    not a proposed system, nothing is tuned for accuracy, and RQ1 to RQ4 are unchanged; the primary outcome is the
    difference of robustness deltas between the two-stage pipeline and the same model's direct zero_shot verdict.
    The frozen artefacts (results/raw, results/scores/*.csv, the study's configs and prompts) were verified
    byte-identical before and after step 1 (sha256 list of 64 files; recorded in the commit message of step 1).

    **Step 1 implemented 2026-11-09** (no extraction run): configs/twostage.yaml, prompts/extract_indicators.txt,
    scripts/06_run_twostage.py (modes extract, fit, predict), scripts/twostage/{parse,stage2}.py,
    tests/test_twostage.py. Readings taken where the specification left a choice; each is reversible before step 2
    and none touches a frozen file. **Please confirm or correct (a) to (k) before step 2 (smoke).**

    (a) **Parse failure: invalid row versus explicit feature level.** Section 4 says a parse failure makes the row
    `invalid`, scored as incorrect exactly as in step 06; section 5 says the one-hot features encode parse failure
    explicitly. Reading implemented: at prediction a parse failure is `invalid` (section 4 governs scoring); at
    fitting on dev a parse-failed row stays in the fitting set with the explicit `invalid` level lit for every
    indicator (section 5), so the fitted model has seen that pattern but never emits a label for it. Alternative:
    drop parse failures from fitting too.

    (b) **Cross-validation metric for C.** Section 5 says "C chosen on dev by cross-validation" without a metric.
    Provisional in configs/twostage.yaml: 5-fold stratified, shuffled with seed 2026, metric balanced_accuracy,
    ties to the smallest C, grid 0.01 to 10 (7 values). Alternatives: f1_phish (the baselines' selection metric,
    configs/baselines.yaml) or neg_log_loss. The metric must be fixed before the fit (step 3).

    (c) **Scoring path.** Section 7 says "scored by the existing 07_score.py into results/scores/additional/
    twostage_{model}/". 07_score.py is the frozen pre-registered computation and cannot take an extra detector
    without changing its outputs; the additional-model path scripts/07_score_model.py (SpearShift, 2026-11-01) does
    exactly this but expects the four prompting strategies of a language model. Plan for step 5: extend
    07_score_model.py with a `--strategies lr` option (one strategy, kind "twostage"), families A-twostage-{model}
    as section 7 names them; the difference-of-deltas comparison (two-stage minus direct zero_shot, same clusters,
    same seed, bootstrap p of item 12 refinement 2) as a small new script or an option of the same script. The
    spec also says F-RQ1 to F-RQ4 keep their counts; there is no F-RQ1 family (RQ1 is descriptive, item 15a), read
    as F-RQ2 to F-RQ4 plus the S-* families.

    (d) **Tables T1 to T11 "gain rows" (section 8) versus the frozen-tables statement.** README and CLAUDE.md say an
    added model enters neither the ensemble nor the tables and figures of Chapter 4, and the .tex files are
    regenerated by 07_tables_figures.py from the frozen CSVs. Options: (i) regenerate T1 to T11 with extra rows for
    the three two-stage detectors read from results/scores/additional/, the existing rows verified unchanged as
    section 8 asks (changes the committed .tex files and the README statement); (ii) keep T1 to T11 as they are and
    put every two-stage number into T12 and F8 only. The spec says (i); confirm, because (i) changes committed
    outputs of the pre-registered computation (not the CSVs).

    (e) **Parse rule details.** "Missing or out-of-vocabulary key" is read as: a missing key, an unknown (extra)
    key, a value outside the indicator's list, or a non-boolean for `is_question` / `is_complaint` each make the row
    invalid; `"yes"` / `"no"` strings for the booleans are invalid. The first balanced {...} is taken even inside
    prose or a code fence (the prompt forbids both, but the rule is about the output). Confirm.

    (f) **Volunteered verdict.** The spec asks for a check of how often the model volunteers a verdict. Rule
    implemented: any of the words phishing, legitimate, phish, scam, malicious, fraudulent, spam as a whole word
    anywhere in the raw output (the prompt uses none of them), reported per cell as `volunteered_verdicts`; the
    value never enters the label. Confirm the word list.

    (g) **`sender_domain_mismatch` on text only.** Detectors see subject and body only (CLAUDE.md), so no sender
    header exists. The prompt defines it as an inconsistency inside the text (claimed identity versus names,
    addresses, domains or signature in the body). Confirm the definition, or drop the indicator (it would then be
    seven threat indicators, departing from the eight frozen cue categories).

    (h) **Runner phases and the intermediate file.** Section 6 names one output file per partition in the runner
    schema. Because stage 2 does not exist until the dev extraction is complete, the runner writes the stage-1 rows
    to results/raw/twostage_{model}/extract/{partition}.jsonl (resumable, the file that costs compute) and the
    final rows to results/raw/twostage_{model}/lr/{partition}.jsonl in `predict` mode (deterministic, seconds).
    `label_pred` of the final rows is the stage-2 label, `raw_output` the extraction JSON string, `score` p_phish,
    plus parse_ok and ind_<key> columns. Confirm the two-file layout.

    (i) **Integrity check at step 4.** scripts/06_check_integrity.py knows the six models and the three baselines
    only; the two-stage files carry config_hash and stage2_sha256 like the baselines. Plan: add a `--twostage`
    check (exact item set, hashes against configs/twostage.yaml and the report, GPU of the eval tier, label
    reproducible from the stored indicators and the fitted model) into reports/integrity_check_twostage.json,
    leaving the committed integrity_check.json untouched. Confirm.

    (j) **Compute units.** The runner records wall time, tier and GPU per session; Colab's compute-unit rate is not
    readable from inside the runtime, so the measured rate of section 9 step 2 will be the author's reading of the
    Colab usage page before and after the smoke, entered into reports/twostage_report.json by hand (as for the
    86.9 units of the main study). Confirm.

    (k) **Budget projection basis.** Section 2 gives about 24 units (9.6 T4, 14.5 L4). The step-2 smoke (20 dev items
    per model) will give seconds per item; the projection multiplies by 796 + 5,207 items per model. If the
    projection exceeds 28 units, the stop rule of section 11 applies before any full run; the fallback order of
    section 11 (qwen25-7b and gemma2-27b first) is implemented as the order of the commands, not in code.

    **Answered 2026-11-09 (author); each decision implemented the same day and, where it corrects the spec,
    docs/TASK_08_twostage.md amended in the same commit (sections 3, 4, 5, 7, 8 and 9 step 2):**
    (a) Sections 4 and 5 conflicted. A parse failure is NEVER a feature level: at prediction it short-circuits to
    invalid (scored incorrect, as in step 06); at fitting the row is excluded from the dev fit entirely and the
    number excluded is reported. "unclear" is a legitimate level and stays. Section 5 amended.
    (b) 5-fold, balanced accuracy, ties to the smallest C, with one change: folds grouped by source e-mail
    (StratifiedGroupKFold, group = the item id before "#"), because dev holds originals together with their own
    variants and ungrouped folds would make the selection optimistic. Implemented in scripts/twostage/stage2.py.
    (c) 07_score.py is not touched. scripts/07_score_model.py gained --strategies and --kind twostage (families
    A-twostage-{model}); tests/test_score_model.py checks that an existing model scored through it still
    reproduces its frozen rows exactly, with the default strategies passed explicitly.
    (d) The objection stands and the spec was wrong: the two-stage detector does NOT gain rows in T1 to T11; it is
    reported only in tab_t12_twostage.tex (own capability block in the T1 format) and figure F8; every committed
    .tex stays byte-identical. Section 8 amended.
    (e) Relax, then be strict: normalise case and the obvious synonyms first (yes/no/unclear case-insensitive;
    true/false/yes/no/1/0 for the booleans), then mark the row invalid only if a value is still out of vocabulary.
    A missing key is invalid. An extra key is ignored, never fatal, counted and reported. The normalisation table
    is frozen in configs/twostage.yaml (parse.normalise). Rationale: invalid means the architecture failed, not
    that the model wrote "Yes". Section 4 amended.
    (f) Word list accepted; diagnostic counter only, checked over the whole raw output, inside and outside the
    JSON; it never changes a row.
    (g) Key renamed to sender_claim_inconsistency, defined in the config as "the body makes claims about the sender
    or the organisation that are internally inconsistent", since the detector never sees a real sender address.
    Section 3 amended; prompt updated.
    (i) Yes: 06_check_integrity.py --twostage (scripts/twostage/integrity.py) writes
    reports/integrity_check_twostage.json with the same assertions plus parse_ok counts and the stage-2 hash.
    (j)(k) Both recorded per session: wall-clock x the published rate (1.15 units/h on T4, 1.94 on L4) and the Colab
    "Available compute units" reading before and after (ground truth; --units-before/--units-after of the runner,
    UNITS_BEFORE/UNITS_AFTER of notebooks/cloud_twostage.ipynb); both numbers and the gap are reported.
    F-RQ1: the reading is correct, RQ1 is descriptive (item 15a); section 7 amended to F-RQ2 to F-RQ4.
    The config_hash of every row changed with these decisions (configs/twostage.yaml re-frozen; hashes in the
    step-2 commit message). Item 18 closed; step 2 (smoke) follows below.

    **Step 2, part 1 (2026-11-09): CPU smoke on the laptop, 20 dev items (10 phishing, 10 legitimate, the seeded
    sample of configs/detection.yaml) for the two models whose GGUF is on the laptop; results/smoke_twostage/, cells
    smoke/<model>/laptop in reports/twostage_report.json. Format gate (parse failures <= 10%):**
    qwen25-7b: parse failures 0/20 (0%) ; volunteered verdicts 0 (0%); rows with extra keys 0; output tokens mean 117.6; CPU median latency 17.604 s (not the tier's latency).
    gemma2-9b: parse failures 0/20 (0%) ; volunteered verdicts 0 (0%); rows with extra keys 0; output tokens mean 112.1; CPU median latency 25.209 s (not the tier's latency).
    Gate PASSED on every row; no prompt revision. The gemma2-9b cell was 19/20 after the first session (stopped by the system for low
    memory, 7 GB WSL, 5.8 GB GGUF) and completed on 2026-11-09 by a resumed session that ran the one missing item.
    A runner defect found by this smoke and fixed in the same commit: the extraction cell statistics used the detection
    runner's cell_stats(), which expects label_pred; extraction rows have none, so the report update crashed after the
    first cell (rows were intact). Replaced by extract_stats(); --stats-only rewrites a cell's statistics from its file.
    gemma2-27b has no laptop GGUF (16.6 GB, L4 tier): its smoke, and the GPU latency and compute-unit measurement of all
    three, run on Colab with notebooks/cloud_twostage.ipynb (MODE = smoke; TIER colab_t4 for qwen25-7b and gemma2-9b, colab_l4
    for gemma2-27b; UNITS_BEFORE in cell 1, UNITS_AFTER in cell 9, entered by the author).
    **Step 2, part 2 preparation (2026-11-09, author's request):** the budget is projected for two plans, A = dev + the full eval
    partition (6,003 items per model, the plan of TASK_08 section 2) and B = dev + the core eval only, gen_phish and
    gen_legit excluded (4,003 items per model), so that the fallback is decided on numbers before step 3. Implemented as
    `06_run_twostage.py budget` (scripts/twostage/budget.py; report `budget_projection`; measured basis = the GPU smoke cell of the
    model on its tier and the span-measured unit rate when recorded, else the prior below) and `06_run_twostage.py units`
    (records the Colab reading before/after against the sessions it covers, the wall-clock estimate, the gap and the rate per
    span hour; report `compute_units`); notebook cell 9 runs both after the extraction cell. **Prior projection** (basis: the
    main study's GPU CoT mean latency of the same model and tier, low = as CoT, high = scaled by the CPU smoke's output-token
    ratio; published rates 1.15 units/h T4, 1.94 L4):
    qwen25-7b (colab_t4): 2.05 to 4.636 s/item; plan A 3.9 to 8.9 units, plan B 2.6 to 5.9 units;
    gemma2-9b (colab_t4): 2.94 to 6.218 s/item; plan A 5.6 to 11.9 units, plan B 3.8 to 8.0 units;
    gemma2-27b (colab_l4): 4.4 to 9.629 s/item; plan A 14.2 to 31.1 units, plan B 9.5 to 20.8 units (output-token ratio borrowed from the other models' mean, no CPU smoke);
    plan A total 23.8 to 52.0 units, plan B total 15.9 to 34.7 units, against 24 planned and the stop rule at 28: at the high end both plans exceed the stop rule; at the low end A fits the plan
    exactly and B fits with margin. The GPU smoke (one Colab session per tier, MODE = smoke) replaces the prior with measured
    seconds per item and a measured unit rate before any full run.
    **Budget raised, plan A confirmed (2026-11-09, author):** 100 compute units were purchased on 2026-11-09; the Colab reading is
    now 113.12 available. TASK_08 section 2 and section 11 amended: the stop rule rises from 28 to 60 compute units, which covers
    the high end of the plan A projection (52.0); the section 11 fallback of dropping a model (keeping qwen25-7b and gemma2-27b)
    no longer applies. Plan A (dev plus the full eval partition, 6,003 items per model, all three models) is confirmed; plan B
    stays in the report as a comparison only. configs/twostage.yaml budget.compute_units_stop 28 -> 60 (the budget block is outside
    config_hash, so no row hash changes); the planned figure of 24 stays as the original estimate. The parse-failure gate and the
    GPU smoke before the full run are unchanged.
    **Step 2, part 2 (2026-11-10): GPU smoke of all three models on their tiers (notebooks/cloud_twostage.ipynb, MODE = smoke,
    commit 2c89fbb; cells smoke/<model>/colab_t4 and smoke/gemma2-27b/colab_l4; results/smoke_twostage/<model>/colab_*.jsonl).
    Format gate (parse failures <= 10%) PASSED in every cell; no prompt revision:**
    qwen25-7b (colab_t4, Tesla T4): parse failures 0/20 (0%); volunteered verdicts 0 (0%); rows with extra keys 0; finish reasons {'stop': 20}; median latency 3.763 s, mean 3.709 s; output tokens mean 117.5; model load 20.3 s.
    gemma2-9b (colab_t4, Tesla T4): parse failures 0/20 (0%); volunteered verdicts 0 (0%); rows with extra keys 0; finish reasons {'stop': 20}; median latency 5.808 s, mean 5.6 s; output tokens mean 112.1; model load 25.5 s.
    gemma2-27b (colab_l4, NVIDIA L4): parse failures 0/20 (0%); volunteered verdicts 0 (0%); rows with extra keys 0; finish reasons {'stop': 20}; median latency 9.879 s, mean 10.058 s; output tokens mean 131.3; model load 5.3 s.
    qwen25-7b GPU against the laptop CPU rows: identical indicator sets 16/20, identical values 256/260 (the format is stable across backends; greedy decoding is not byte-identical across backends, as in the main study's 99.7% label agreement).
    gemma2-9b GPU against the laptop CPU rows: identical indicator sets 18/20, identical values 258/260 (the format is stable across backends; greedy decoding is not byte-identical across backends, as in the main study's 99.7% label agreement).
    gemma2-27b wraps the object in a ```json fence; the first-balanced-object rule parses it (TASK_08 section 4).
    **Compute units (item 18j/k), from the author's Colab readings entered in notebook cell 9:**
    colab_t4 (2026-11-10T12:48:00Z): 113.12 -> 112.93 = 0.19 units; extraction wall 186.6 s, estimate at the published rate 0.06, gap 0.13; span 323.9 s -> 2.112 units/h (published 1.15).
    colab_t4 (2026-11-10T12:50:53Z): 113.12 -> 112.93 = 0.19 units; extraction wall 186.6 s, estimate at the published rate 0.06, gap 0.13; span 497.6 s -> 1.375 units/h (published 1.15).
    colab_l4 (2026-11-10T13:06:11Z): 112.93 -> 112.56 = 0.37 units; extraction wall 201.4 s, estimate at the published rate 0.109, gap 0.261; span 541.2 s -> 2.461 units/h (published 1.94).
    The T4 entry exists twice because cell 9 was run twice (the same readings, a longer span the second time); the projection uses the
    latest entry per tier. Caveat: a 5 to 9 minute smoke measures the rate poorly: the Colab display has a resolution of 0.01 units
    and updates with a lag, so part of the 0.19 and 0.37 units may belong to the set-up cells; the T4 rate lies between 1.375 and
    2.112 units/h, the L4 rate near 2.461, both above the published 1.15 and 1.94. The full dev run measures it properly.
    **Revised projection (reports/twostage_report.json budget_projection, basis measured: mean GPU latency per item + one load, x the
    latest span-measured rate of the tier):**
    qwen25-7b (colab_t4): 3.709 s/item at 1.375 units/h: plan A 8.5 units, plan B 5.7 units;
    gemma2-9b (colab_t4): 5.6 s/item at 1.375 units/h: plan A 12.8 units, plan B 8.6 units;
    gemma2-27b (colab_l4): 10.058 s/item at 2.461 units/h: plan A 41.3 units, plan B 27.5 units;
    plan A total 62.6 units (about 32.3 GPU hours: 6.2 + 9.3 on T4, 16.8 on L4); plan B total 41.8 units; planned 24, stop 60: plan A exceeds the stop rule, plan B between the planned budget and the stop rule.
    Sensitivity to the rate: at the published rates plan A is 50.4 units; with the first T4 entry (2.112 units/h) it is 74.1.
    gemma2-27b alone is two thirds of the cost: 10.06 s/item against 4.40 s for its CoT cell (131 output tokens against 54).
    **Question for the author (2026-11-10):** the measured plan A projection (62.6 units, point estimate from 20 items and a coarse rate
    reading) passes the stop rule of 60 set on 2026-11-09 (section 11: stop and report rather than improvise). 113.12 units are available
    before the smoke, 112.56 after it. Options: (1) confirm plan A anyway, raising the stop rule once more (e.g. to 80, well inside the
    available units, with the dev run's measured rate as the checkpoint before eval); (2) plan B (41.8 units); (3) plan A for the two
    T4 models and plan B for gemma2-27b (8.5 + 12.8 + 27.5 = 48.8 units). No full run is started until this is answered.
    **Answered 2026-11-10 (author): option 1.** Plan A is confirmed for all three models including the generalisation partitions;
    the stop rule rises from 60 to 80 compute units, with 112.56 available. Reasons recorded: the cost is affordable; the
    generalisation arm must cover all three models for the comparison to be consistent; option 3 would leave gemma2-27b without
    generalisation results; the headroom over the 62.6 projection is for resumes and error, not for widening scope. Checkpoint:
    after the dev run, recompute the rate from that longer span and report it before the eval run starts; if the revised plan A
    projection passes 80, stop and ask. Implemented: configs/twostage.yaml budget.compute_units_stop 80 (outside config_hash);
    TASK_08 sections 2 and 11 amended; `06_run_twostage.py budget` prefers the dev extraction cell as its basis (basis
    measured_dev) and reports the eval-only remainder, so notebook cell 9 after the dev session is the checkpoint. For the
    thesis (docs/CHANGES_FOR_THESIS.md): the GPU-versus-laptop indicator agreement (256/260 qwen25-7b, 258/260 gemma2-9b) and
    the gemma2-27b code fence handled by the first-balanced-object rule.
    **Step 3, part 1 (2026-11-10): full dev extraction, 796 x 3, done (notebooks/cloud_twostage.ipynb at 4c8ecc0, MODE = dev; T4 session
    for qwen25-7b and gemma2-9b, L4 session for gemma2-27b; results/raw/twostage_<model>/extract/dev.jsonl, 796 rows each, one
    session per cell, no resume needed):**
    qwen25-7b (Tesla T4): 796/796 rows; parse failures 0 (0%); volunteered verdicts 0; rows with extra keys 0; finish reasons {'stop': 796}; latency median 4.72 s, mean 4.79 s; output tokens mean 117.3; model load 1.8 s; extraction wall 3815.2 s.
    gemma2-9b (Tesla T4): 796/796 rows; parse failures 0 (0%); volunteered verdicts 0; rows with extra keys 0; finish reasons {'stop': 796}; latency median 5.89 s, mean 6.012 s; output tokens mean 112.1; model load 2.4 s; extraction wall 4788.3 s.
    gemma2-27b (NVIDIA L4): 796/796 rows; parse failures 0 (0%); volunteered verdicts 0; rows with extra keys 0; finish reasons {'stop': 796}; latency median 9.823 s, mean 9.952 s; output tokens mean 131.3; model load 5.3 s; extraction wall 7925.1 s.
    Every row carries config_hash defa94b131fd60ac and the frozen prompt hash; no truncated input. Against the 20-item GPU smoke the mean
    latency moved from 3.71 to 4.79 s (qwen25-7b), 5.60 to 6.01 s (gemma2-9b) and 10.06 to 9.95 s (gemma2-27b): the smoke sample
    was not representative of the dev items' length for the two T4 models, which is why the checkpoint uses the dev cell.
    **Compute units (checkpoint readings, notebook cell 9):**
    T4 session: 112.35 -> 107.62 = 4.73 units over a span of 10432.2 s (2.90 h) -> 1.632 units/h (published 1.15); extraction wall 8603.5 s, estimate wall x published rate 2.749, gap +1.981.
    L4 session: 107.45 -> 103.58 = 3.87 units over 8095.3 s (2.25 h) -> 1.721 units/h (published 1.94); extraction wall 7925.1 s, estimate 4.271, gap -0.401.
    The author's session boundaries were 112.56 -> 107.62 (T4) and 107.62 -> 103.58 (L4); cell 1 recorded 112.35 and 107.45 just before
    the extraction cell, so the set-up cells (clone, wheels, GGUF download) cost 0.21 and 0.17 units outside the spans. Total for the
    dev extraction 8.98 units (8.60 inside the measured spans); 103.58 available. The T4 is billed above its published rate (1.63
    against 1.15 units/h, the 2.9 h span confirms the smoke's reading), the L4 below (1.72 against 1.94); the smoke's 2.461 for the L4
    was the short-span artefact anticipated in the caveat above.
    **Checkpoint (item 18 option 1; `06_run_twostage.py budget`, basis measured_dev = dev cell mean latency + one load, x the dev span
    rate of the tier):**
    qwen25-7b (colab_t4): 4.79 s/item at 1.632 units/h: plan A 13.0 units (eval only 11.3), plan B 8.7 (eval only 7.0);
    gemma2-9b (colab_t4): 6.012 s/item at 1.632 units/h: plan A 16.4 units (eval only 14.2), plan B 10.9 (eval only 8.7);
    gemma2-27b (colab_l4): 9.952 s/item at 1.721 units/h: plan A 28.6 units (eval only 24.8), plan B 19.0 (eval only 15.3);
    plan A total 58.0 units, of which 50.3 remain for the eval partition; plan B 38.7 (31.0 remaining); planned 24, stop 80: plan A between the planned budget and the stop rule.
    **The revised plan A projection (58.0) does NOT pass the stop rule of 80**; the remaining eval cost (50.3) is
    half of the 103.58 units available. The eval run is not started by this record; it waits for the author's go.
    **Step 3, part 2 (2026-11-10): stage 2 fitted per model on the dev extractions (`06_run_twostage.py fit`; models/twostage/<model>_lr.joblib,
    gitignored, sha256 in the report; one-hot of the 13 indicators, LogisticRegression lbfgs, C from the grid by 5-fold StratifiedGroupKFold
    balanced accuracy with the source e-mail as the group, threshold 0.5; two consecutive fits gave identical coefficients):**
    qwen25-7b: 796 of 796 rows used, 0 excluded (no parse failure); 596 phish / 200 legit; 400 source e-mails as groups; C = 3.0; dev balanced accuracy 0.889 grouped cv (sd 0.017 over folds), 0.892 resubstitution; intercept +6.38; five largest |coef|: credential_or_payment_request=yes +2.055, credential_or_payment_request=no -2.050, grammar_anomaly=yes +2.033, grammar_anomaly=no -2.029, link_or_url=yes +1.193; sha256 ab29422a46c3.
    gemma2-9b: 796 of 796 rows used, 0 excluded (no parse failure); 596 phish / 200 legit; 400 source e-mails as groups; C = 3.0; dev balanced accuracy 0.890 grouped cv (sd 0.028 over folds), 0.891 resubstitution; intercept +3.47; five largest |coef|: urgency=yes +1.644, urgency=no -1.636, credential_or_payment_request=yes +1.623, credential_or_payment_request=no -1.615, impersonation_authority=yes +1.366; sha256 894eb6593398.
    gemma2-27b: 796 of 796 rows used, 0 excluded (no parse failure); 596 phish / 200 legit; 400 source e-mails as groups; C = 3.0; dev balanced accuracy 0.866 grouped cv (sd 0.023 over folds), 0.884 resubstitution; intercept +2.48; five largest |coef|: credential_or_payment_request=no -2.103, credential_or_payment_request=yes +1.956, language_pattern=machine_like -1.845, language_pattern=human_like +1.688, urgency=yes +1.538; sha256 ca0ee18c5afd.
    Reading the coefficients: the one-hot of a yes/no/unclear indicator gives a mirrored pair (yes +, no -) when "unclear" is never
    emitted (its coefficient stays at 0.0), so the indicator's effect is the yes-minus-no difference, about 4.1 for
    credential_or_payment_request and grammar_anomaly in qwen25-7b, 3.3 for urgency in gemma2-9b, 4.1 for credential_or_payment_request
    in gemma2-27b. credential_or_payment_request, urgency, impersonation_authority, grammar_anomaly and link_or_url point towards
    phish in all three models. language_pattern = machine_like points towards LEGIT in all three (strongest in gemma2-27b, -1.845
    against human_like +1.688): on dev, the LLM-written spear-phishing reads as human-like to the extractor while part of the
    Enron and hard-ham originals read as machine-like; a dev observation, to be checked on eval, not a claim. The positive intercepts
    reflect the 596:200 class ratio of dev (originals plus the accepted phish variants). C = 3.0 won in all three grids; the
    grid's cv curve is flat from 0.1 upwards (within one sd), so the choice is not sensitive.
    Status: step 3 complete (dev extraction 3 x 796/796, checkpoint 58.0 < 80, stage 2 fitted); the eval extraction (step 4, plan A,
    MODE = eval, T4 session then L4 session) awaits the author's go; no eval run started.
