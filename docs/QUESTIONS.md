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
