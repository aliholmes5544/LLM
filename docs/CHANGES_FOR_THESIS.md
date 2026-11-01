# Changes for the thesis text (append-only; the advisor chat consumes this file)

## From steps 01–04 (2026-10-11)
- Table 3.2 actual counts: core_neg = 1,002 (hard_ham 308 + enron_ham 694); baseline training
  = 3,033 (traditional 2,299 + enron 734) plus validation 337; dev = 400; generalization
  1,000/1,000 with salutation strata named 599 / generic 330 / none 71.
- Section 3.2.2: cross-collection near-duplicate removal reduced traditional phishing from
  3,227 to 2,654 (573 near-duplicate campaign messages) and hard ham to 308.
- Section 3.2.2: 83 records with fewer than 5 words dropped (enron 78, hard_ham 3, traditional 2);
  746 bodies truncated at 600 words (traditional 455, enron 195, hard_ham 96); spear unaffected.
- Section 3.2.2: 3,673 placeholder tokens neutralized in E-PhishLLM (424 distinct forms).
- Leakage check after partitioning: 0 near-duplicates of evaluation items in train/valid/dev.

## From step 05, development set only (2026-10-13; thresholds still provisional)
- Section 3.2.3 / 3.3: paraphrase model fixed as Phi-3.5-mini-instruct (GGUF Q4_K_M, llama.cpp,
  temperature 0.7, top-p 0.9, max tokens 3x input); the Phi family is therefore excluded from the
  detector set (configs/variants.yaml: excluded_from_detectors).
- Section 3.2.3, sentence unit: a segment is rewritten only if it has at least 3 alphabetic words
  outside protected spans, is not a greeting line, and ends with sentence punctuation or has at
  least 8 words; greeting lines, titles, signature lines and link labels are copied verbatim. On
  the 100 dev emails this gives 498 rewritable sentences out of 943 segments (median 5 per email).
- Section 3.2.3, protected spans on dev: 375 spans over 100 emails (PERSON 142, placeholder phrases
  78, ORG 75, numbers 35, DATE 34, TIME 4, EMAIL 3, MONEY 3); median 3.5 per email, 0 to 12.
- Section 3.2.3, obfuscation on dev: eligible tokens median 43 per email (4,425 total); obf_low
  451 edits, obf_high 1,335 edits; operations drawn uniformly (obf_high: homoglyph 335, digit 324,
  zero-width 354, separator 322); integrity replay reproduced the original in 100 % of variants.
- Section 3.2.3, paraphrase on dev with the provisional thresholds (cosine 0.80, NLI 0.70):
  para_low 79 pass / 11 regenerated / 10 excluded; para_high 70 / 16 / 14. Failures at the first
  attempt were NLI 16 and 21, cosine 3 and 8, protected span 2 and 2, length 0 and 0 (para_low and
  para_high respectively); no generation was truncated. Median cosine 0.954 (para_low) and 0.917
  (para_high); median length ratio 1.04 and 1.08.
- Section 3.2.3, manual review: 40 variants sampled (10 per condition) in
  reports/manual_review_sample_dev.csv; obfuscated rows also carry readability columns. The
  calibrated thresholds, Cohen's kappa and the sample failure rate with 95 % CI follow from
  scripts/05b_calibrate_variants.py once rated.

## Step 05 refinements, development set only (2026-10-13; thresholds still provisional)
- Section 3.2.3, sentence-level fallback: a rewritten sentence that fails the NLI test (or loses a
  protected span) is rewritten once more with a new seed; if it still fails it is replaced by its
  original sentence instead of discarding the whole variant. Each variant records
  achieved_fraction = retained rewrites / selected sentences, and is excluded when the fraction is
  below 0.40 (para_low) or 0.80 (para_high) or when the final body fails the variant-level tests
  (cosine >= 0.80, length ratio in [0.70, 1.40], protected spans). The retry regenerates only the
  failing sentences; if only a variant-level test failed, all selected sentences are regenerated.
- Section 3.2.3, dev results after the fallback (same provisional thresholds): para_low 79 pass /
  19 regenerated / 2 excluded (was 79 / 11 / 10); para_high 70 / 24 / 6 (was 70 / 16 / 14).
  Sentences reverted to the original: 7 of 275 selected (para_low) and 11 of 498 (para_high).
  achieved_fraction: para_low min 0.50, 5th percentile 0.75, mean 0.978, median 1.0 (94 variants
  at 0.8-1.0, 5 at 0.6-0.8, 1 at 0.4-0.6); para_high min 0.75, 5th percentile 0.80, mean 0.979,
  median 1.0 (97 at 0.8-1.0, 3 at 0.6-0.8). Minimum NLI entailment among retained sentences is
  now 0.74 (para_low) and 0.75 (para_high), median 0.995.
- Section 3.2.3, tests failed by each excluded variant (reports/variants_dev_report.json,
  conditions.*.excluded_failed_tests): para_low eph:12308 and eph:14228 fail cosine only;
  para_high eph:12308, eph:14228 and eph:1823 fail cosine only, eph:12656, eph:13635 and eph:5004
  fail the fraction minimum only. No exclusion involves length or protected spans. Whether cosine
  alone over-rejects paraphrases that NLI and the raters accept is therefore a question for the
  calibration (thr_cos unchanged at 0.80 until the rated sample is returned).
- Section 3.2.3, manual review sample extended to 57 variants: the stratified 10 % per condition
  (40) plus every excluded paraphrase variant (8, of which 7 were not already sampled) plus a
  seeded sample of 10 regenerated paraphrases. Each row carries auto_outcome
  (pass / regenerated / excluded) and failed_tests; 05b reports the false-rejection rate (share of
  "preserved" ratings among automatically excluded variants) with a Wilson 95 % CI, and the
  raters' verdicts per failed-test combination.

## Step 05 calibration on the rated development sample (2026-10-25; thresholds frozen)
Three raters (A, B, C) rated the 57-variant sample for meaning (preserved / partly / not). The
human label is the majority label (given by at least two raters; no row was split). Statistics
from scripts/05b_calibrate_variants.py, written to reports/variants_calibration.json.
- Section 3.2.3 thresholds calibrated on dev: cosine >= 0.68, NLI entailment >= 0.70 (human
  label = majority of three raters). thr_cos = 0.68 is the highest grid value at which at least
  95 % of the 35 paraphrases labelled "preserved" pass (97.1 % pass at 0.68; the 95 % target is
  not reached anywhere at or above 0.70, so the grid was extended down to 0.60). thr_nli stays at
  the pre-specified 0.70 and is **not calibrated**: the sentence-level fallback reverts every
  sentence below 0.70, so the rated bodies carry no NLI score under it and the sample cannot
  support a lower value (the mechanical rule returns 0.90, the top of the grid, with 97.1 % pass;
  this value is reported but not adopted).
- Section 3.2.3 inter-rater agreement (n = 57): Fleiss' kappa 0.137; pairwise percent agreement
  AB 86.0 %, AC 93.0 %, BC 89.5 %; PABAK AB 0.72, AC 0.86, BC 0.79. Cohen's kappa is near zero
  (AB -0.03, AC 0.47, BC -0.03) because 55 of 57 majority labels are "preserved"; PABAK (2 p_o - 1)
  is the prevalence-adjusted figure to report alongside it.

  | group | n | unanimous | Fleiss kappa | pair | % agreement | Cohen kappa | PABAK |
  |---|---|---|---|---|---|---|---|
  | all | 57 | 48 | 0.137 | AB / AC / BC | 86.0 / 93.0 / 89.5 | -0.03 / 0.47 / -0.03 | 0.72 / 0.86 / 0.79 |
  | paraphrase | 37 | 28 | 0.111 | AB / AC / BC | 78.4 / 89.2 / 83.8 | -0.05 / 0.44 / -0.04 | 0.57 / 0.78 / 0.68 |
  | obfuscation | 20 | 20 | 1.000 | all | 100 | 1.00 | 1.00 |

  Per rater: A preserved 52 / partly 5; B preserved 54 / not 3; C preserved 54 / partly 3.
- Rater B's three "not" ratings (eph:14738#para_low, eph:13635#para_high, eph:14893#para_high, all
  noted "link missing") are each outvoted by the other two raters. Decision: rater B is retained
  and the disagreement is resolved by majority labelling rather than by excluding the rater; the
  three rows are labelled "preserved".
- Section 3.2.3 false rejection by automatic test (share labelled "preserved" among the variants
  that test alone excluded): cosine 4/5 = 80 % (95 % CI 37.5-96.4 %); achieved fraction 3/3 =
  100 % (43.9-100 %); length, protected spans and NLI excluded no variant on their own (NLI only
  triggers the sentence-level retry; 15 of the 16 variants it alone flagged at the first attempt
  were rated "preserved" after the retry). Any exclusion: 7/8 = 87.5 % (52.9-97.8 %).
- Cosine-only exclusions under the provisional 0.80, with cosine value and human label:
  eph:14228#para_high 0.625 preserved; eph:14228#para_low 0.686 preserved; eph:12308#para_high
  0.731 partly (A: "credentials confused", C: "login wording muddled"); eph:12308#para_low 0.752
  preserved; eph:1823#para_high 0.794 preserved. All five have NLI minimum >= 0.99 and length
  ratio 1.00-1.09.
- Residual error among accepted paraphrases (auto_outcome pass or regenerated, n = 29): 1/29 =
  3.4 % not fully preserved (rated "partly"; Wilson 95 % CI 0.6-17.2 %); strictly "not" 0/29
  (0-11.7 %). Reweighted to the population counts of pass / regenerated variants the point
  estimate is 1.2 %. Among the 20 accepted obfuscated variants 0/20 (0-16.1 %).
- Manual-sample failure rate (majority "not") per condition: para_low 0/16 (95 % CI 0-19.4 %),
  para_high 0/21 (0-15.5 %), obf_low 0/10 (0-27.8 %), obf_high 0/10 (0-27.8 %); no condition
  exceeds the 5 % review trigger. "Not fully preserved" (partly or not): para_high 2/21 = 9.5 %
  (2.6-28.9 %), all others 0.
- Display issue in the first rating round: the raters opened the UTF-8 CSV in Excel, which decoded
  it in the system code page Windows-1256 (Arabic). 29 of the 57 rows were shown with garbled
  characters (all 20 obfuscated rows, whose Cyrillic homoglyphs and zero-width spaces appeared as
  Arabic letters, plus 3 para_low and 6 para_high rows containing a curly apostrophe or an umlaut).
  scripts/05a_merge_ratings.py repairs the workbook text (every repaired cell equals the CSV text)
  and records the affected rows in reports/ratings_merge_dev.json. Consequence: the meaning ratings
  of the 20 obfuscated rows were made on mis-rendered text and are re-rated, together with
  readability (2 / 1 / 0), from reports/readability_dev.xlsx, which openpyxl writes as true
  Unicode; the first-round values are kept in rating_A/B/C_cp1256. The nine paraphrase rows are
  not re-rated (the garbling there was confined to one or two punctuation characters).
- Readability of the obfuscated variants: pending (rated from the clean sheet; merged by
  scripts/05a_merge_ratings.py --readability; statistics in 05b once rated).

## Step 05 dev re-run with the frozen thresholds (2026-10-25; cosine 0.68, NLI 0.70)
- Section 3.2.3, dev results with the frozen thresholds (same seed, same cached generations;
  obfuscated variants byte-identical to the previous run, integrity 100/100): para_low 81 pass /
  19 regenerated / 0 excluded (was 79 / 19 / 2); para_high 76 / 20 / 4 (was 70 / 24 / 6).
  Exclusions now: para_high eph:14228 (cosine 0.625, the only cosine exclusion) and eph:12656,
  eph:13635, eph:5004 (achieved fraction below 0.80). Variant-level cosine failures at the first
  attempt fell from 3 to 1 (para_low) and 8 to 1 (para_high); retried sentences from 27 to 22 and
  57 to 32; reverted sentences unchanged (7 and 11). Final-body cosine: para_low min 0.686, 5th
  percentile 0.838, median 0.956; para_high min 0.625, 5th percentile 0.789, median 0.923.
- Four of the five former cosine-only exclusions are recovered (one more than the three expected
  from the calibration print-out, because eph:14228#para_low at 0.686 clears 0.68): eph:12308
  para_low and para_high now pass, eph:14228#para_low and eph:1823#para_high are regenerated.
  eph:14228#para_high (0.625) stays excluded.
- Ten variants changed status (6 regenerated -> pass, 2 excluded -> pass, 2 excluded ->
  regenerated). Eight of them changed body as well: under 0.80 their first attempt failed only
  the cosine test and was regenerated, whereas under 0.68 the first attempt is kept. Five of the
  eight are in the rated sample (eph:12308 para_low and para_high, eph:16367#para_low,
  eph:11434#para_high, eph:4123#para_high): their rated body (reports/manual_review_sample_dev.csv)
  is the former attempt-1 body, not the body now in data/processed/variants_dev.jsonl. In
  particular eph:12308#para_high, whose rated attempt-1 body (cosine 0.731) was labelled "partly",
  is now accepted with its unrated attempt-0 body (cosine 0.707). The sample CSV and
  reports/variants_calibration.json are kept as records of the provisional run (cosine 0.80) on
  which the thresholds were chosen; scripts/05_derive_variants.py no longer rewrites a sample that
  carries ratings and reports instead what a fresh draw would select (54 rows: 40 stratified +
  4 excluded + 10 regenerated).
- Re-rating of the changed paraphrases (2026-10-25): reports/readability_dev.xlsx carries sheets
  para_changed_A/B/C with the 8 paraphrases whose accepted body changed (eph:12308#para_low,
  eph:16367#para_low, eph:11434#para_high, eph:12308#para_high, eph:14108#para_high,
  eph:15264#para_high, eph:16367#para_high, eph:4123#para_high), showing the body accepted under the
  frozen thresholds with a meaning drop-down (no readability column). On merge
  (scripts/05a_merge_ratings.py --readability) the new ratings become rating_A/B/C for these rows,
  the first-round ratings of the superseded attempt-1 bodies move to rating_A/B/C_prov together with
  the superseded body (variant_body_prov) and provisional outcome (auto_outcome_prov,
  failed_tests_prov), and the three variants outside the first-round sample are appended, so the
  sample grows from 57 to 60 rows. The residual-error estimate among accepted items (Section 3.2.3)
  will be recomputed on the bodies accepted under the frozen thresholds (cosine 0.68, NLI 0.70)
  once these ratings are in; the 1/29 figure above refers to the provisional run. The threshold
  calibration and the false-rejection analysis remain those of the provisional run, since the
  thresholds were chosen on it (scripts/05b_calibrate_variants.py has to read the *_prov columns for
  those analyses before it is rerun on the merged file; it currently stops with a message when it
  finds them).

## Step 05 final dev-set statistics (2026-10-25; re-rated obfuscation rows and changed paraphrases)
The raters returned reports/readability_dev.xlsx (sheets A/B/C: 20 obfuscated rows, readability
and meaning from clean text; sheets para_changed_A/B/C: the 8 paraphrases whose accepted body
changed). Merged by scripts/05a_merge_ratings.py --readability: 60 rows (16 para_low, 24 para_high,
10 obf_low, 10 obf_high), no empty rating cell, no split majority. Two further rows changed status
without a change of body (eph:14228#para_low and eph:1823#para_high, excluded -> regenerated) and
carry the provisional outcome in auto_outcome_prov. scripts/05b_calibrate_variants.py now keeps the
two runs apart: the provisional-run analyses (threshold calibration, false rejection per test,
cosine-only exclusions) are read from reports/variants_calibration_provisional.json (the committed
output of the provisional run, renamed) and verified against the *_prov / *_cp1256 columns (five
checks: per-condition labels, false rejection, cosine-only labels, residual error, agreement; all
consistent); agreement, residual error, per-condition rates and readability are computed from the
current columns on the bodies accepted under the frozen thresholds. Output:
reports/variants_calibration.json (sections provisional_run and frozen_run).
- Obfuscated rows re-rated from clean text: meaning ratings identical to the first round for all
  three raters (0 of 20 changed per rater); majority "preserved" 20/20 under both. The cp1256
  display therefore did not change any meaning rating.
- Changed paraphrases re-rated on the body accepted under cosine 0.68: 7 of 8 "preserved" by
  majority; eph:12308#para_high is again "partly" (A partly, B preserved, C partly), as its
  superseded attempt-1 body was. The other four re-rated rows keep "preserved"; eph:11434#para_high
  is now unanimous (C had rated the superseded body "partly").
- Section 3.2.3 inter-rater agreement on the final sample (n = 60): Fleiss' kappa 0.163; pairwise
  percent agreement AB 86.7 %, AC 95.0 %, BC 91.7 %; PABAK AB 0.73, AC 0.90, BC 0.83; Cohen's kappa
  AB -0.03, AC 0.55, BC -0.02 (58 of 60 majority labels "preserved"); 52 rows unanimous. Paraphrase
  rows (n = 40): Fleiss 0.144, percent agreement 80.0 / 92.5 / 87.5 %, PABAK 0.60 / 0.85 / 0.75.
  Obfuscation rows (n = 20): unanimous "preserved", all statistics 1.0.
- Residual error among paraphrases accepted under the frozen thresholds (pass + regenerated,
  n = 36): 2/36 = 5.6 % not fully preserved (both "partly": eph:12308#para_high and
  eph:14356#para_high; Wilson 95 % CI 1.5-18.1 %); strictly "not" 0/36 (0-9.6 %). Reweighted to the
  population counts (para_low 81 pass / 19 regenerated, para_high 76 / 20): 4.7 %. Among the 20
  accepted obfuscated variants 0/20 (0-16.1 %); all accepted items together 2/56 = 3.6 % (1.0-12.1 %).
  This replaces the provisional 1/29 figure.
- Manual-sample failure rate (majority "not") per condition: para_low 0/16 (95 % CI 0-19.4 %),
  para_high 0/24 (0-13.8 %), obf_low 0/10 (0-27.8 %), obf_high 0/10 (0-27.8 %); no condition
  exceeds the 5 % review trigger. "Not fully preserved": para_high 2/24 = 8.3 % (2.3-25.9 %),
  all other conditions 0.
- Section 3.2.3 readability of the obfuscated variants (2 reads normally / 1 noticeably odd but
  every word readable / 0 at least one word unrecognisable), majority of three raters: obf_low
  0 / 10 / 0, obf_high 0 / 10 / 0. Unreadable-word rate 0/10 in both conditions (95 % CI 0-27.8 %);
  neither condition reaches the 10 % flag. Every obfuscated variant was judged noticeably odd
  (odd or worse 10/10, 72.2-100 %). Per rater: A gave one obf_low variant (eph:16547) a 2, all
  other ratings are 1. Agreement: 19 of 20 unanimous; percent agreement AB 95 %, AC 95 %, BC 100 %;
  PABAK 0.90 / 0.90 / 1.00; Cohen's kappa 0.00 / 0.00 / 1.00 and Fleiss' kappa -0.02, which are
  uninformative here because 59 of 60 ratings fall in one category.
- Thresholds unchanged: cosine 0.68 (calibrated, provisional run), NLI 0.70 (pre-specified).

## Step 05 evaluation variants (2026-10-26; single frozen run on core_pos and ctrl_para_legit)
Derived once with the frozen configs/variants.yaml (cosine 0.68, NLI 0.70, length 0.70-1.40,
minimum achieved fraction 0.40 low / 0.80 high; run_variants_eval.sh refuses to start if the file
differs from HEAD) by `python scripts/05_derive_variants.py --target eval` at commit a8dbb6f, then
run a second time against the generation cache and the three outputs compared by hash, then a cache
spot check (scripts/05c_spot_check_cache.py). No manual sample is drawn from evaluation data; the
dev residual-error estimate (2/36 among accepted paraphrases) stands. Targets (configs/
variants_eval.yaml): core_pos 334 spear_llm x para_low, para_high, obf_low, obf_high;
ctrl_para_legit 334 (enron_ham 222, hard_ham 112) x para_high only; 668 unique records, 1,002
paraphrase pairs, 668 obfuscation pairs, 1,670 rows in data/processed/variants_eval.jsonl. The
only overlap with another partition is the intended one (ctrl_para_legit is a seeded sample of
core_neg); no training, dev or valid item is touched.
- Protected spans: 10,935 over 668 records. core_pos 2,084 (median 6 per record; ORG 1,095,
  PERSON 841, PLACEHOLDER 51, CARDINAL 29, NUMBER 29, DATE 26, TIME 13). ctrl_para_legit 8,851
  (median 16, max 231; NUMBER 3,573, PERSON 2,205, ORG 1,829, DATE 577, EMAIL 220, MONEY 192,
  CARDINAL 190, TIME 53, PLACEHOLDER 12).
- Section 3.2.3 obfuscation on core_pos: obf_low 334 variants, 3,598 edits (homoglyph 917, digit
  876, zero-width 923, separator 882; 38 redraws), integrity 334/334; obf_high 334 variants,
  10,763 edits (2,778 / 2,653 / 2,653 / 2,679; 106 redraws), integrity 334/334. Eligible tokens
  per body: min 35, median 106, max 190 (35,810 in total).
- Section 3.2.3 paraphrase on core_pos, para_low (half of the eligible sentences; 1,805 of 3,440
  selected): 219 pass / 115 regenerated / 0 excluded. First attempt: 130 sentences failed NLI,
  19 failed the span test; 139 sentences retried, of which 75 failed NLI and 10 spans again; 82
  sentences reverted to the original. Achieved fraction min 0.40 / 5th percentile 0.75 / median
  1.00 / mean 0.954. Final-body cosine min 0.885, 5th percentile 0.948, median 0.976; length ratio
  0.913-1.131; 2 truncated generations.
- Section 3.2.3 paraphrase on core_pos, para_high (all 3,440 eligible sentences): 129 pass / 196
  regenerated / 9 excluded (2.7 %). All 9 exclusions are for achieved fraction below 0.80 (0.667-
  0.778) with cosine 0.932-0.994; no exclusion involves cosine, length or spans. First attempt:
  253 sentences failed NLI, 34 spans; 270 retried, 135 failed NLI and 23 spans again; 149 reverted.
  Achieved fraction min 0.667 / 5th percentile 0.853 / median 1.00 / mean 0.956. Final-body cosine
  min 0.827, 5th percentile 0.901, median 0.951; length ratio 0.874-1.166; 4 truncated generations.
- Section 3.2.3 paraphrased legitimate control (ctrl_para_legit, para_high, 3,624 eligible
  sentences; bodies min 1 / median 8 / max 116 segments): 63 pass / 150 regenerated / 121 excluded
  (36.2 %; 113 fraction, 5 cosine, 2 length, 1 cosine and length; enron_ham 98 of 222, hard_ham 23
  of 112). First attempt: 644 sentences failed NLI, 518 spans; 894 retried, 412 failed NLI and 397
  spans again; 599 reverted; 234 truncated generations. Achieved fraction min 0.00 / 5th percentile
  0.333 / median 0.862 / mean 0.799. Final-body cosine min 0.551, 5th percentile 0.769, median
  0.929; length ratio 0.839-1.833. Open question: docs/QUESTIONS.md item 7.
- Comparison with the dev exclusion rates (reports/variants_eval_report.json, dev_comparison):
  core_pos/para_low 0.0 % vs 0.0 %; core_pos/para_high 2.7 % vs 4.0 % (-1.3 points); obf_low and
  obf_high 0.0 % vs 0.0 %; ctrl_para_legit/para_high 36.2 % vs 4.0 % (+32.2 points, flagged, the
  only condition above the 5-point margin).
- Table 3.2 and Section 3.2.4 counts as derived: accepted variants para_low 334, para_high 325,
  obf_low 334, obf_high 334 (1,327 items where the text says 1,336); controls 213 paraphrased
  legitimate + 334 modern legitimate (547 where the text says 668); items per detector per
  prompting strategy 334 + 1,002 + 1,327 + 547 = 3,210 (text: 3,340). These figures hold if the
  author keeps option (i) of question 7; they change if the control is handled otherwise.
- Section 3.8 determinism: run 1 took 29,903 s (8 h 18 min; 13:24-21:43 UTC), of which 364.8 min
  for the 7,064 first-attempt sentence generations (about 3.1 s per sentence, 16 threads, CPU) and
  24.8 min for the first-attempt checks. The cache (data/interim/paraphrase_cache_eval.jsonl,
  gitignored) holds 8,228 rows: 7,064 attempt-0 and 1,164 attempt-1 generations, exactly the
  distinct (record, sentence, attempt) triples in the variants file (para_low sentences share
  their keys with para_high, since the generation seed depends on record, sentence index and
  attempt only). Run 2 against the cache: 10,172 hits, 0 misses, 1,940.8 s; variants_eval.jsonl,
  obfuscation_log_eval.jsonl and variants_eval_report.json byte-identical to run 1 (sha256
  a4672bb6..., d7a8865c..., 38daee49...). The report hash changed afterwards only because the spot
  check attaches its result under cache_spot_check.
- Section 3.8 cache spot check (reports/variants_eval_spot_check.json): 10 core_pos records drawn
  with derive_rng(seed, "spot_check", "core_pos"), 20 paraphrase variants, 179 sentence
  generations repeated with the same seeds and the cache bypassed, 436 s. Protected spans and
  sentence selection identical to the eval run; no cache row missing; 171 of 179 generations
  byte-identical (95.5 %), 8 differ (7 at attempt 0, 1 at attempt 1, in 6 records, all with
  finish reason "stop"): same sentence structure, one to three words substituted (e.g. "will be"
  vs "will prove", "strategy" vs "approach", "framework" vs "defenses"). Generation with
  llama-cpp-python 0.3.36 on this CPU at temperature 0.7 is therefore not bit-reproducible for
  every sentence; the reproducibility of the variants rests on the cached generations and the
  released variants file, not on regenerating them (docs/QUESTIONS.md item 8).

## Step 05 control-exclusion diagnosis and reproducibility decision (2026-10-27; no threshold changed)
Author's decisions on docs/QUESTIONS.md items 7 and 8. Diagnosis by scripts/05d_control_exclusion_
diagnosis.py, output reports/control_exclusion_diagnosis.json; nothing was re-derived.
- Section 3.2.3, paraphrased legitimate control (ctrl_para_legit/para_high, 121 of 334 excluded,
  36.2 %). Excluded versus accepted variants: body length median 95 vs 141 words; eligible
  sentences median 5 vs 8; protected spans per record median 13 vs 17; variants with at least one
  truncated generation 54 of 121 (44.6 %) vs 61 of 213 (28.6 %); achieved fraction median 0.667
  vs 0.933. Source collection: enron_ham 98 of 222 excluded (44.1 %), hard_ham 23 of 112 (20.5 %).
  Exclusion rate by eligible sentences: 1-4 sentences 60 of 119 (50.4 %), 5-9 23 of 77 (29.9 %),
  10-19 26 of 70 (37.1 %), 20 or more 12 of 65 (18.5 %); by body length: under 50 words 31 of 72
  (43.1 %), 50-99 31 of 71 (43.7 %), 100-199 24 of 73 (32.9 %), 200-399 10 of 47 (21.3 %), 400 or
  more 25 of 71 (35.2 %). Of the 113 exclusions for achieved fraction, all 113 have fraction equal to
  (eligible - reverted) / eligible, so the mechanism is entirely sentence-level reverts (325 reverted
  sentences after a failed retry), and 53 of the 113 have fewer than 5 eligible sentences, where the
  0.80 minimum leaves no room for a single revert (4 sentences, 1 reverted: 0.75). Fifteen excluded
  variants had every selected sentence reverted (fraction 0.0) and are byte-identical to the
  original; three accepted variants have no eligible sentence at all (fraction recorded as 1.0) and
  are likewise identical to the original.
- Interpretation (analytical, for the thesis text): the control exclusions are not a sign that the
  paraphraser changes the meaning of legitimate mail more often; they follow from the interaction
  of three properties of the Enron and hard-ham material with the frozen rules. The bodies are short
  and fragmentary (median 8 segments, many with 1-4 eligible sentences), so one sentence that fails
  the NLI or span test and is reverted after its retry already drops the achieved fraction below
  0.80; they are dense in protected spans (names, numbers, e-mail addresses, 16 per record against
  6 for the spear-phishing originals), which the 3.8B paraphraser drops or alters more often (518 of
  3,624 first-attempt sentences failed the span test, against 34 of 3,440 for core_pos); and they
  contain long run-on lines that hit the generation length limit (234 truncated generations against
  4). The spear-phishing originals, by contrast, are uniform 7-23 segment prose with few spans, and
  their 9 exclusions all fall in bodies with 5-9 eligible sentences (7 of 120, 5.8 %, against 2 of
  212 with 10-19 sentences). The thresholds are not changed. The control is kept at 213 accepted
  variants, reported with this breakdown; the thesis should state that the control's exclusion rate
  is not comparable with the dev estimate (dev paraphrases were E-PhishLLM text only) and that the
  three unchanged accepted controls are counted as controls with no paraphrasable sentence.
- Section 3.8, reproducibility decision: data/processed/variants_eval.jsonl and data/interim/
  paraphrase_cache_eval.jsonl are the fixed evaluation artifact. Every step downstream of
  generation is byte-reproducible from them (run 2 reproduced run 1 byte-identically from the
  cache); generation itself is seeded but not bit-reproducible on the CPU backend (8 of 179 sampled
  sentences differed by 1-3 words). sha256 recorded in reports/variants_eval_report.json
  (fixed_artifacts) and reports/variants_eval_fixed_artifacts.json:
  variants_eval.jsonl a4672bb621a3bb6107c58a19ce66d30efd05979dc36fed2771704d1ffe3fb7a9
  (5,604,858 bytes, 1,670 rows); paraphrase_cache_eval.jsonl
  694cd11b27045dfd6d7256b6f2bfae366e77d6c9d1be6fb02b9e6b0aac6297d7 (4,714,876 bytes, 8,228 rows).
  Both files are archived at submission under CC BY-NC-SA 4.0 (the Nahmias et al., 2024, licence),
  not in git.

## Step 05 unchanged-variant rule; evaluation variants re-derived from the cache (2026-10-27)
Logical correction, not a threshold change: a "variant" whose body is byte-identical to its original
is not a variant and is excluded with reason "unchanged". scripts/05_derive_variants.py applies the
rule uniformly to every partition and condition (paraphrase: after the four existing tests;
obfuscation: next to the integrity test, whose rows now carry a failed_tests list like the paraphrase
rows). The development set is unaffected: none of its 400 variants is identical to its original
(checked; the dev outputs were not re-derived).
- Re-derivation (run_variants_eval.sh at commit 3d3a10b, 13:24-13:59 UTC, 2,083.9 s): cache hits
  10,172, cache misses 0, so no sentence was generated anew; the cache is unchanged (sha256
  694cd11b...). Against the previous run: all 1,670 variant bodies and subjects byte-identical;
  obfuscation log byte-identical (sha256 d7a8865c...); 984 rows identical in every field; the 668
  obfuscation rows differ only by the added empty failed_tests list; 18 ctrl_para_legit/para_high
  rows carry the new reason "unchanged" (15 of them already excluded for fraction 0.0, all selected
  sentences reverted; 3 previously "pass" with no eligible sentence, now excluded). No other row
  changed. The second run of the script (determinism check) was stopped by the host while the
  session was idle, at the first-attempt checks, before writing anything; the run-1 outputs are
  complete and hashed (data/interim/variants_eval_run1.sha256). The earlier determinism proof
  (2026-10-26, two byte-identical runs) covers the unchanged generation and check stages; the
  determinism run is to be repeated when the machine is free.
- Section 3.2.3 / Table 3.2 counts after the rule: core_pos para_low 334 accepted (219 pass, 115
  regenerated), para_high 325 (129 / 196; 9 excluded, fraction), obf_low 334, obf_high 334 (integrity
  334/334); ctrl_para_legit para_high 210 accepted (60 pass, 150 regenerated), 124 excluded (37.1 %:
  fraction 98, fraction+unchanged 15, unchanged 3, cosine 5, length 2, cosine+length 1; enron_ham 101
  of 222, hard_ham 23 of 112). Dev comparison for the control: 37.1 % vs 4.0 % (+33.1 points,
  flagged). Table 3.2 therefore reads: variants 1,327 accepted items (334 + 325 + 334 + 334),
  paraphrased legitimate control 210 of 334, controls 544, items per detector per prompting strategy
  334 + 1,002 + 1,327 + 544 = 3,207; the table in docs/METHODOLOGY_3.2.md is updated accordingly.
- Diagnosis re-run (reports/control_exclusion_diagnosis.json): excluded vs accepted controls, body
  words median 88 vs 142.5; eligible sentences median 4 vs 8; spans per record median 13 vs 17;
  fraction median 0.667 vs 0.932; by collection enron_ham 45.5 %, hard_ham 20.5 %; of the 98
  fraction-only exclusions 38 have fewer than 5 eligible sentences and all 98 have fraction equal to
  (eligible - reverted) / eligible. No accepted variant is identical to its original any more
  (previous run: 3). The interpretation of the 2026-10-27 diagnosis entry stands.
- Fixed artifact (Section 3.8): data/processed/variants_eval.jsonl sha256
  d898cece2d0f5d399a036bdeab8d63c9246b4eb91fd8298c299285b354d46389 (5,618,458 bytes, 1,670 rows);
  data/interim/paraphrase_cache_eval.jsonl sha256
  694cd11b27045dfd6d7256b6f2bfae366e77d6c9d1be6fb02b9e6b0aac6297d7 (4,714,876 bytes, 8,228 rows,
  unchanged). Recorded in reports/variants_eval_fixed_artifacts.json and in
  reports/variants_eval_report.json (fixed_artifacts). The previous variants hash (a4672bb6...) is
  superseded. The spot check (171/179) remains valid: spans, sentence selection and generations are
  untouched by the rule.

## Step 06 item 1: detector set, decoding, prompts, label rule, few-shot examples (2026-10-27; no model run)
Implements TASK_06 sections 1, 2 and 4 (Chapter 3 Sections 3.5 to 3.7). No weights were downloaded and no
inference was run; everything below is configuration and code, frozen only after the dev smoke test (item 2).
- Section 3.5, paraphraser exclusion: configs/variants.yaml names the paraphrase model
  bartowski/Phi-3.5-mini-instruct-GGUF (Phi-3.5-mini-instruct, 3.8B, MIT; excluded_from_detectors: [phi]).
  None of the six detectors (Llama 3.1, Mistral, Gemma 2, Qwen2.5) belongs to the Phi family, so no
  substitution is needed and the table of TASK_06 section 1 stands.
- Section 3.5, detector set (configs/models.yaml): GGUF Q4_K_M files from the bartowski repositories,
  original repository, file size and licence per model: llama31-8b = Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf
  (4.92 GB; card licence "llama3.1", LLAMA 3.1 COMMUNITY LICENSE AGREEMENT, open-weight; gated);
  mistral-7b = Mistral-7B-Instruct-v0.3-Q4_K_M.gguf (4.37 GB; apache-2.0); gemma2-9b = gemma-2-9b-it-Q4_K_M.gguf
  (5.76 GB; card licence "gemma", Gemma Terms of Use, open-weight; gated); qwen25-7b =
  Qwen2.5-7B-Instruct-Q4_K_M.gguf (4.68 GB; apache-2.0); qwen25-14b = Qwen2.5-14B-Instruct-Q4_K_M.gguf
  (8.99 GB; apache-2.0; Colab T4); gemma2-27b = gemma-2-27b-it-Q4_K_M.gguf (16.65 GB; gemma; Colab L4).
  Licence strings are the model-card front-matter values read on 2026-10-27; sha256 of each file is
  filled in by 06_download_models.py on first download. Context 4,096 tokens; the chat template embedded
  in each GGUF is applied. Gemma 2 has no system role: the system text is prepended to the user message
  (QUESTIONS.md item 9).
- Section 3.6, decoding (configs/detection.yaml): greedy (temperature 0, top-p 1.0, repeat penalty 1.0,
  sampler seed 2026), max_tokens 16 for zero_shot / few_shot / role and 256 for cot, no stop sequences
  beyond the template end token, one run per cell.
- Section 3.5, prompts (prompts/zero_shot.txt, few_shot.txt, cot.txt, role.txt; "### system" / "### user"
  sections, placeholders {subject} and {body}): the output rule in all four is "Answer with exactly one
  word: PHISHING or LEGITIMATE."; cot asks for a few sentences of analysis and then "FINAL: PHISHING" or
  "FINAL: LEGITIMATE"; role replaces the system message by an email-security-analyst persona, user message
  identical to zero_shot (checked by diff); few_shot inserts four labelled examples as "Example n /
  Subject / Body / Answer" blocks before the item. Hashes are recorded at freezing (item 2).
- Section 3.5, few-shot examples (scripts/06_select_fewshot.py, prompts/few_shot_examples.json,
  reports/fewshot_selection.json): drawn once from fewshot_pool with seed 2026, admissible body length 20
  to 200 words, no PERSON/ORG entity token shared with a core_pos original (spaCy en_core_web_sm; 204
  protected tokens), no near-duplicate of an evaluation item; 21 candidates examined, 16 rejected for
  length, 1 for a shared persona token, 0 near-duplicates; the second run reproduced both files
  byte-identically. Chosen (prompt order phish, legit, phish, legit):
  nah:traditional_phishing:84a636ab9a6e223503fc0a0d35767424 (161 words),
  nah:enron_ham:15899597_1075855716918_JavaMail_evans_thyme (80 words),
  nah:traditional_phishing:8f1706e54180856389c7d570674b2f2c (131 words),
  nah:enron_ham:14352313_1075858637544_JavaMail_evans_thyme (26 words). The file stores ids and sha256 of
  subject and body only; the texts are rendered from records.jsonl at run time (no data in git).
  Observations for the author in QUESTIONS.md item 10.
- Section 3.6, label extraction (scripts/common.py: extract_label): lowercase; for cot, the text after the
  last "final:" (whole output if absent); punctuation and whitespace runs stripped; whole-word search for
  "phishing" and "legitimate"; exactly one present gives the label (returned as the record class values
  phish / legit), both, neither or empty gives "invalid", which is scored as incorrect and reported per
  cell with a sensitivity analysis excluding it (step 07). 15 unit tests in tests/test_extract_label.py
  pass (python -m unittest discover tests).

## Step 06 few-shot redraw (2026-10-27; author's decision on QUESTIONS.md item 10)
- Section 3.5, few-shot example rules: minimum body length raised from 20 to 40 words (maximum 200
  unchanged) and a new rule that the two examples of the same label must have word-level Jaccard
  similarity below 0.30 (configs/detection.yaml few_shot.min_words / max_same_label_jaccard;
  scripts/06_select_fewshot.py rule (d)). The persona/organisation rule, the near-duplicate rule, the pool,
  the seed and the derivation of the random streams are unchanged. The draw was repeated once, before any
  model was run.
- Old ids (first draw, 20-word minimum, no similarity rule; prompt order phish, legit, phish, legit):
  nah:traditional_phishing:84a636ab9a6e223503fc0a0d35767424 (161 words),
  nah:enron_ham:15899597_1075855716918_JavaMail_evans_thyme (80),
  nah:traditional_phishing:8f1706e54180856389c7d570674b2f2c (131),
  nah:enron_ham:14352313_1075858637544_JavaMail_evans_thyme (26, forwarded-message stub).
- New ids (final): slots 1 to 3 unchanged; slot 4 is now
  nah:enron_ham:32834965_1075858643952_JavaMail_evans_thyme (99 words, a reply about a gym appointment with
  the quoted original message). Same-label word Jaccard: phishing pair 0.15, legitimate pair 0.08 (both
  below 0.30). Selection: 30 candidates examined, 23 rejected for length, 3 for a shared PERSON/ORG token
  with a spear-phishing original ("mitchell"/"williams", "john"/"williams", "john"/"taylor"), 0 for
  near-duplication, 0 for similarity (reports/fewshot_selection.json). Both phishing examples remain
  advance-fee fraud messages, which is the dominant content of the Nahmias traditional collection; the
  thesis states this when describing the few-shot condition.
- QUESTIONS.md item 9 confirmed: for the two Gemma 2 models the system text is prepended to the user
  message; the run report (reports/smoke_dev_report.json, later reports/detection_run_report.json) carries
  this note.

## Step 06 items 2 and 3: laptop-tier models downloaded; dev smoke test (2026-10-27 to 2026-10-28)
- Section 3.5 / 3.7, detector files (bartowski GGUF, Q4_K_M; sha256 pinned in configs/models.yaml and
  reports/models_download_report.json; files under models/, not in git):
  llama31-8b: Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf, 4,920,739,232 bytes, sha256 7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c, licence llama3.1 (LLAMA 3.1 COMMUNITY LICENSE AGREEMENT, Llama 3.1 Version Release Date: July 23, 2024).
  mistral-7b: Mistral-7B-Instruct-v0.3-Q4_K_M.gguf, 4,372,812,000 bytes, sha256 1270d22c0fbb3d092fb725d4d96c457b7b687a5f5a715abe1e818da303e562b6, licence apache-2.0.
  gemma2-9b: gemma-2-9b-it-Q4_K_M.gguf, 5,761,057,728 bytes, sha256 13b2a7b4115bbd0900162edcebe476da1ba1fc24e718e8b40d32f6e300f56dfe, licence gemma (Gemma Terms of Use).
  qwen25-7b: Qwen2.5-7B-Instruct-Q4_K_M.gguf, 4,683,074,240 bytes, sha256 65b8fcd92af6b4fefa935c625d1ac27ea29dcb6ee14589c55a8f115ceaaa1423, licence apache-2.0.
- Section 3.6, smoke test (TASK_06 section 5; reports/smoke_dev_report.json, results/smoke_dev/): 20 dev items
  (5 per subclass, seeded), 4 models x 4 strategies = 320 inferences, llama-cpp-python 0.3.36, CPU only
  (16 threads, n_ctx 4,096, greedy, seed from configs/data.yaml). Gate (invalid <= 10 % per cell) PASSED in all
  16 cells. No input was truncated (longest prompt 1,718 tokens, Mistral few_shot). Per cell: invalid / median
  latency s / max latency s:
  llama31-8b (load 6.1 s): zero_shot 0/20, 3.42, 11.33; few_shot 0/20, 3.96, 14.09; cot 0/20, 14.28, 24.08; role 0/20, 3.13, 11.27.
  mistral-7b (load 5.6 s): zero_shot 2/20, 3.96, 12.33; few_shot 0/20, 4.7, 16.27; cot 2/20, 11.39, 22.8; role 2/20, 4.11, 12.27.
  gemma2-9b (load 12.6 s): zero_shot 0/20, 4.54, 16.89; few_shot 0/20, 4.93, 18.28; cot 0/20, 12.9, 26.5; role 0/20, 4.34, 14.42.
  qwen25-7b (load 5.0 s): zero_shot 0/20, 2.85, 10.75; few_shot 0/20, 3.53, 13.06; cot 0/20, 7.38, 17.9; role 0/20, 3.17, 10.64.
- Invalid outputs: 6/320 (1.9 %), all from Mistral-7B-Instruct-v0.3, none from the other three models. In
  zero_shot and role the same two E-PhishLLM phishing items (eph:14893, eph:11599) received the hedge
  "Insufficient information to determine with certainty. However, it's important to", cut at 16 tokens. In cot
  one answer named both words after FINAL ("as either PHISHING or LEGITIMATE") and one ended without a FINAL
  line. These are refusals to commit, not parser gaps; the rule in decision 4 scores them as incorrect. No
  prompt was revised (dev invalid rate before = after).
- QUESTIONS.md item 9 applied: gemma2-9b (system_role false) received the system text prepended to the user
  message; its four cells had 0 invalid outputs. gemma-2-9b-it loaded in 12.6 s within the 7 GB WSL memory cap.
- Runtime measurement for the order of work, item 3 (Section 3.7, the time risk): mean latency over all four
  strategies on the smoke items was llama31-8b 7.76 s, mistral-7b 7.71 s, gemma2-9b 8.91 s, qwen25-7b 5.56 s
  per inference. Projected CPU time for the core evaluation (3,207 items x 4 strategies = 12,828 inferences
  per model): llama31-8b 27.7 h, mistral-7b 27.5 h, gemma2-9b 31.8 h, qwen25-7b 19.8 h, total about 107 h;
  the generalisation set (2,000 items x 4 strategies) adds about 66 h, total about 173 h for the laptop tier.
  Few-shot prompts are 4 to 5 times longer (median about 1,000 tokens) but cost only about 0.5 s more per item;
  cot costs 2 to 4 times a single-word strategy. Whether to move part of the laptop tier to Colab is the
  author's decision (QUESTIONS.md item 11).

## Step 06: all evaluation inference moves to Colab GPUs; detection runner and notebook (2026-10-28)
- Decision (QUESTIONS.md item 11, author, 2026-10-28): all evaluation inference for all six detectors runs on
  Colab GPUs, the T4 runtime for the four 7B to 9B models and Qwen2.5-14B, the L4 runtime for gemma-2-27b. The
  laptop is used for development and the dev smoke test only. Reasons given: identical hardware class for every
  model removes a confound in RQ2, and the CPU projection (about 173 h) is not practical. The generalisation set
  is not subsampled. Sections 3.7 and 4.2.1: "every detector was run with llama-cpp-python 0.3.36 (CUDA build,
  Q4_K_M, n_ctx 4,096, greedy decoding, fixed seed) on Colab GPUs: NVIDIA T4 (15 GB) for the 7B to 14B models
  and NVIDIA L4 (24 GB) for the 27B model; the laptop CPU served development and the dev smoke test." The earlier
  sentence about running the small models on the laptop is withdrawn. configs/models.yaml records eval_tier and
  smoke_tiers per model; every result row records the backend (cpu / cuda); the run report records the GPU name
  and the llama-cpp-python version per cell.
- Evaluation item set per (model, strategy), read from the data by scripts/detect/items.py (Table 3.2): 5,207 =
  core_pos 334 originals + 1,327 variants (para_low 334, para_high 325, obf_low 334, obf_high 334) + core_neg
  1,002 + ctrl_modern_legit 334 + ctrl_para_legit para_high 210 + gen_phish 1,000 + gen_legit 1,000. Per model 4
  x 5,207 = 20,828 inferences; six models 124,968 inferences. Development set (dev originals + accepted dev
  variants): 796 items.
- GPU time and cost estimate (Section 3.7; to be replaced by the measured values from
  reports/smoke_gpu_report.json and reports/detection_run_report.json). Assumptions: llama.cpp prompt processing
  / generation speeds of 1000 / 30 tokens per s for 7B to 9B Q4_K_M on a T4,
  500 / 15 for 14B on a T4 and 600 / 12 for 27B on an L4
  (community figures for the T4 range from 35 to 43 generated tokens per s for 8B Q4_K_M, so these are
  conservative); median prompt and output token counts per strategy from the dev smoke test (Qwen tokens for
  the 14B, Gemma tokens for the 27B); 0.05 s call overhead; a factor of 1.3 for model loading, Drive
  synchronisation, smoke runs and session restarts. Estimated hours per model: llama31-8b T4 9.7 h; mistral-7b T4 9.3 h; gemma2-9b T4 8.0 h; qwen25-7b T4 6.6 h; qwen25-14b T4 12.9 h; gemma2-27b L4 16.6 h.
  Totals: T4 about 47 h, L4 about 17 h. Compute units at the rates measured by
  C. McCormick (March 2026): T4 1.19 and L4 1.71 units per hour, giving about
  55 + 28 = 84 units (USD 8 at USD 0.10 per unit); with the
  higher community figures (T4 1.76, L4 assumed 2.57) about 125 units (USD
  12). Google publishes no units-per-hour table; the live rate shown in the Colab resource
  panel is authoritative. 100 units = USD 9.99 (the author used a Colab Pro subscription, not pay-as-you-go;
  final consumption in the entry of 2026-11-01, step 07). Sessions are limited in length and can
  disconnect, hence the per-item resumability of the runner and the Drive synchronisation every 10 minutes.
- Hashes of the two Colab-only files were pinned from the Hugging Face LFS metadata (2026-10-28) and are verified
  by scripts/06_download_models.py before any inference: Qwen2.5-14B-Instruct-Q4_K_M.gguf 8,988,110,976 bytes,
  sha256 e47ad95dad6ff848b431053b375adb5d39321290ea2c638682577dafca87c008; gemma-2-27b-it-Q4_K_M.gguf
  16,645,381,632 bytes, sha256 503a87ab47c9e7fb27545ec8592b4dc4493538bd47b397ceb3197e10a0370d23. The four
  hashes computed on the laptop on 2026-10-27 equal the LFS metadata of their files.
- New code (TASK_06 section 5): scripts/06_run_detection.py (one row per item, resumable at item level,
  refuses to overwrite a finished eval file without --force --reason, refuses eval runs when the frozen configs
  or prompts differ from HEAD or when the tier is not the model's eval_tier; --backend recorded in every row;
  GPU name, llama-cpp-python version and per-session timings in reports/detection_run_report.json);
  scripts/06_compare_smoke.py (per-cell percent agreement of labels and of raw outputs between two smoke runs,
  reports/smoke_backend_agreement.json); scripts/detect/stats.py; notebooks/cloud_run.ipynb (Drive mount,
  clone at a tag, CUDA wheel of llama-cpp-python 0.3.36 from the official index, sha256-verified downloads,
  data pulled from Drive with the fixed-artefact hash check, GPU smoke test with CPU agreement, resumable eval
  cells, results synced to Drive); requirements-detect.txt. Trial of the runner on the laptop (dev partition,
  qwen25-7b zero_shot, first 6 then 8 items): resume added exactly the 2 missing items, a third call reported
  the cell complete, the backend and tier guards refused as designed; the trial outputs were deleted.
- Cross-backend reproducibility: greedy decoding on a GPU is not guaranteed to reproduce CPU outputs token for
  token (different kernels, accumulation order); cell 7 of the notebook measures the agreement between the
  committed CPU smoke run (results/smoke_dev/) and the GPU run on the same 20 dev items per cell, and the
  thesis reports it. The CPU smoke rows predate the backend field ("unrecorded" in the comparison).
- 2026-10-29, first Colab resume: the runner refused (exit 1) a cell whose eval file was already complete, which
  aborted the notebook loop. Fixed in v0.6.1-detection-ready: a complete file whose rows carry the current prompt
  and model hashes is skipped with exit 0 and left untouched; the refusal remains for --force without --reason
  and for hash mismatches (scripts/detect/resume.py, tests/test_resume.py). Results produced under
  v0.6-detection-ready are unaffected (same code path for inference).

## Pre-registration of secondary analyses and the statistical plan (2026-10-31; nothing computed)

- QUESTIONS.md item 12 pre-registers, before any evaluation score was computed (results/raw exists on Drive,
  no metric has been calculated), five fixed elements: (a) an unweighted majority-vote ensemble of the six
  detectors reported as a seventh detector, (b) a CoT rationale cue analysis with a lexicon frozen on dev,
  (c) a descriptive hard-core analysis of items all six models miss versus none, with a seeded 30-item
  qualitative sample, (d) a cost-robustness frontier of GPU latency against robustness delta, and (e) the
  statistical plan for step 07 (robustness delta as primary metric, cluster bootstrap CIs with B = 2000 and
  seed 2026 clustered on the original email, McNemar for paired comparisons, Holm correction per research
  question with uncorrected p-values shown, differences in proportions with CIs, invalid scored incorrect in
  the primary analysis and excluded in a sensitivity analysis, generalisation partitions never pooled).
- Wording for Section 3.2 (Research Methodology, pre-registration): "The secondary analyses and the
  statistical plan were fixed in writing (repository file docs/QUESTIONS.md, item 12, committed 2026-10-31)
  before any evaluation metric was computed. The commit precedes every evaluation score in the repository
  history, so the analyses reported in Chapter 4 can be distinguished from exploratory ones; any departure
  from the plan is logged in the same file with its date and reason."
- Wording for Section 3.6 (Proposed Algorithm, secondary analyses): "Beyond the primary comparisons, four
  pre-registered secondary analyses are defined. An ensemble detector takes, for each strategy, the majority
  vote of the six models per item; an invalid output is an abstention, and a 3-3 tie or fewer than four valid
  votes is scored as invalid; it is reported as a seventh detector without weighting or tuning. A rationale
  cue analysis applies a lexicon of eight cue categories (urgency, link or URL, sender or domain mismatch,
  credential or payment request, grammar or spelling, impersonation or authority, attachment, generic
  greeting), built and frozen on the development partition only, to the chain-of-thought outputs, and reports
  cue frequency per model and condition and its change between an original and its paraphrase, split by
  whether the prediction flipped from correct to incorrect. A hard-core analysis contrasts items misclassified
  by all six models under zero-shot prompting with items misclassified by none, by condition, body length,
  source and partition, and codes a seeded stratified sample of 30 all-six failures into a qualitative error
  taxonomy. A cost-robustness frontier plots the median latency per inference on the uniform GPU backend
  against the robustness delta, one point per model and strategy. The statistical plan is stated in Section
  4.3." (The plan itself, item (e), belongs with the metrics in Section 4.3 under the chapter template.)

## Step 06: all 24 detection cells run on Colab GPUs; GPU/CPU smoke agreement; integrity check (2026-10-28 to 2026-10-31)

- Every evaluation cell (6 models x 4 strategies, 5,207 items each, 124,968 rows) was run once on its
  eval_tier with notebooks/cloud_run.ipynb at tags v0.6-detection-ready (two llama31-8b cells),
  v0.6.1-detection-ready (all others) and v0.6.2-detection-ready (the four Mistral-7B cells, rerun with the
  system text prepended, 2026-10-31 to 2026-11-01; entries below): Tesla T4 for llama31-8b, mistral-7b, gemma2-9b, qwen25-7b and qwen25-14b,
  NVIDIA L4 for gemma2-27b; llama-cpp-python 0.3.36 CUDA build, backend cuda in every row. Runs took place
  2026-10-28 21:20 UTC to 2026-10-31 05:42 UTC (Mistral rerun 2026-10-31 18:07 UTC to 2026-11-01 00:46 UTC). Two cells were resumed after a Colab session ended
  (llama31-8b/cot, qwen25-14b/cot); the run report records only the last session of each, so inference-time
  totals below are sums of the per-item latencies. No cell was forced or overwritten. results/raw/ (79 MB)
  is committed to git as the thesis artefact; the Colab logs (logs/) are not.
- scripts/06_check_integrity.py (TASK_06 section 6 item 8; reports/integrity_check.json): every cell has
  exactly the expected 5,207 items (same item builder as the runner), no duplicates, prompt and model hashes
  equal to the frozen values in every row, backend cuda in every row, the GPU of the run report equal to the
  model's eval_tier, label_pred reproducible from raw_output with the frozen parser in every row, and the
  sha256 of each results file recorded as a fixed-artefact hash. Result on 2026-10-31: 20 of 24 cells pass;
  the four Mistral-7B cells failed one check, system_text_delivered, described next. After the Mistral rerun
  (2026-11-01) all 24 cells pass, including system_text_delivered for every model: the role prompt is exactly
  32 tokens longer than the zero_shot prompt on all 5,207 items of each of the six models.
- **Finding (2026-10-31): Mistral-7B never received the system message.** The role and zero_shot prompts share
  the user text and differ only in the system text (the role text is longer). For the five other models every
  item's role prompt is exactly 32 tokens longer than its zero_shot prompt; for Mistral-7B the two prompts have
  the same token count on all 5,207 items and the two cells' raw outputs are byte-identical on all 5,207
  items. Cause, verified on the laptop with the GGUF's vocabulary only: the chat template embedded in
  Mistral-7B-Instruct-v0.3-Q4_K_M.gguf is the old Mistral template that supports only user and assistant
  turns, and llama-cpp-python 0.3.36 maps it to its built-in "mistral-instruct" formatter
  (guess_chat_format_from_gguf_metadata), whose format_mistral_instruct() silently discards messages whose
  role is not user or assistant. The runner's chat messages for Mistral therefore contained the system text,
  but the formatter dropped it before tokenisation. The statement in QUESTIONS.md item 9 that "Mistral-7B
  accepts a system message but its own template folds it into the first user turn" was wrong. The CPU smoke
  test showed the same symptom (identical zero_shot and role outputs and token counts) and nobody compared the
  two cells. Consequences: in all four Mistral cells the model saw only the user turn, which still contains
  the task instruction and the output rule, so the cells are well-defined zero_shot, few_shot and cot runs
  without the one-sentence system framing that the other models received; the Mistral role cell is not a role
  run at all (it equals zero_shot). Options and the recommended remedy are in QUESTIONS.md item 13; until it is
  answered, no Mistral result is used in step 07. The other five models are unaffected (Llama 3.1, Qwen2.5 via
  their GGUF templates with a system turn; Gemma 2 via the prepend rule of item 9).
- Note on Llama 3.1: its official chat template inserts the lines "Cutting Knowledge Date: December 2023" and
  "Today Date: 26 Jul 2024" into the system turn (the date is a template constant, not the run date), so the
  Llama prompts carry these two lines before the system text. Deterministic and identical for every item; it
  is why the Llama prompts are about 20 tokens longer than the Qwen prompts for the same text.
- GPU/CPU smoke agreement (reports/smoke_backend_agreement.json, recomputed 2026-11-01 with the v2 Mistral
  smoke rows; the same 20 dev items per cell, 4 laptop models x 4 strategies = 320 inferences on the laptop
  CPU and on the Colab T4; gemma2-9b, llama31-8b and qwen25-7b on 2026-10-28, mistral-7b v2 on 2026-10-31):
  labels agree on 319 of 320 (99.7%); 15 of 16 cells at 100%, including the four v2 Mistral cells, and
  qwen25-7b/cot at 95%. The single disagreement is a genuine label flip, qwen25-7b/cot on eph:5768 (phish on
  CPU, legit on GPU; the rationale text differs from the first sentence on). Raw outputs are byte-identical
  in all 12 single-word cells; the four CoT cells are byte-identical in 25 to 40% of items only (qwen25-7b 25,
  mistral-7b 30, gemma2-9b 40, llama31-8b 40), because long greedy generations diverge once a single token
  differs, while reaching the same label in all but one item. The earlier figure of 98.8% (316 of 320) was
  computed with the archived v1 Mistral rows; it is recorded in the Mistral entry below and belongs to that
  incident only.
- Wording for Section 4.2.1 (Environment): "All evaluation inference ran on Google Colab GPUs with the same
  GGUF files, decoding settings and llama-cpp-python build (0.3.36, CUDA) for every model: a Tesla T4 (15 GB)
  for the five models of up to 14B parameters and an NVIDIA L4 (24 GB) for gemma-2-27b. The laptop CPU was
  used only for development and for a 20-item smoke test on the development partition. Before the evaluation
  the smoke test was repeated on the T4; the extracted labels agreed with the CPU run on 319 of 320 inferences
  (99.7%); the single disagreement was a label flip in the chain-of-thought condition of Qwen2.5-7B. The raw
  outputs were byte-identical in all twelve single-word cells; chain-of-thought rationales differed in
  wording in most items while yielding the same label." (Revised 2026-11-01 after the Mistral rerun.)
- Wording for Section 4.8 (Threats to validity): "Greedy decoding is deterministic for a given software build
  and hardware, but not across hardware: the CPU and GPU runs of the same 320 development inferences differed
  in one label (0.3%) and in the wording of most chain-of-thought rationales. The evaluation therefore uses
  one hardware configuration per model, uniform across the six models, and archives the raw outputs so that
  every score can be recomputed from them. The 0.3% cross-backend disagreement on 320 development inferences
  is a floor on the measurement noise against which small differences between models or strategies should
  be read. The decision to run all
  evaluation inference on GPUs was taken before any evaluation item was processed (docs/QUESTIONS.md item 11)."
- Measured latency per inference on the GPU (median seconds per cell, from reports/detection_run_report.json;
  last column: total inference time of the model's four cells in hours):

| model | GPU | zero_shot | few_shot | cot | role | hours |
|---|---|---|---|---|---|---|
| llama31-8b | Tesla T4 | 0.32 | 0.35 | 3.50 | 0.33 | 6.9 |
| mistral-7b | Tesla T4 | 0.40 | 0.45 | 3.07 | 0.41 | 6.6 |
| gemma2-9b | Tesla T4 | 0.47 | 0.52 | 2.84 | 0.48 | 6.7 |
| qwen25-7b | Tesla T4 | 0.29 | 0.32 | 2.09 | 0.30 | 4.5 |
| qwen25-14b | Tesla T4 | 0.58 | 0.66 | 7.07 | 0.63 | 13.8 |
| gemma2-27b | NVIDIA L4 | 0.63 | 0.66 | 4.33 | 0.63 | 9.5 |

  Single-word strategies take 0.3 to 0.7 s per item on the GPU (against 2.9 to 4.9 s on the laptop CPU in the
  smoke test); CoT takes 2.1 to 7.1 s. Total inference time 38.6 h on the T4 and 9.5 h on the L4
  (48.1 h; Mistral row and totals revised 2026-11-01 to the v2 cells, the v1 row is in the Mistral
  entry below), against the 2026-10-28 estimate of about 47 h and 17 h; the single-word cells were
  faster than estimated and the CoT cells slower.
- Invalid outputs per cell (count and rate of the 5,207 items; scored as incorrect in the primary analysis,
  excluded in the pre-registered sensitivity analysis, QUESTIONS.md item 12e):

| model | zero_shot | few_shot | cot | role |
|---|---|---|---|---|
| llama31-8b | 1 (0.02%) | 0 (0.00%) | 2 (0.04%) | 0 (0.00%) |
| mistral-7b | 10 (0.19%) | 5 (0.10%) | 68 (1.31%) | 0 (0.00%) |
| gemma2-9b | 4 (0.08%) | 0 (0.00%) | 21 (0.40%) | 3 (0.06%) |
| qwen25-7b | 0 (0.00%) | 0 (0.00%) | 5 (0.10%) | 0 (0.00%) |
| qwen25-14b | 2 (0.04%) | 7 (0.13%) | 60 (1.15%) | 0 (0.00%) |
| gemma2-27b | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) |

  Total 188 of 124,968 rows (0.15%). The maximum is mistral-7b/cot at 1.31%, then
  qwen25-14b/cot at 1.15%, both far below the 10% smoke gate; gemma2-27b produced no invalid output in any
  strategy. The Mistral row shows the v2 cells (system text prepended, 2026-11-01); the v1 counts are in the
  Mistral entry below.
- Truncated inputs: 1 of 124,968 rows (mistral-7b/few_shot; the few-shot prompt is the longest and the Mistral
  tokenizer the least compact, so one body was cut at a sentence boundary to fit n_ctx 4,096). No other cell
  truncated any input. The runner's truncated_input flag identifies the row
  (nah:enron_ham:19167790_1075855710738_JavaMail_evans_thyme, core_neg; the same item was the one truncated
  row of the archived v1 Mistral run).
- Cost (revised 2026-11-01, final figures in the entry of 2026-11-01 below): Colab charged 1.15 compute units
  per hour on the T4 and 1.94 on the L4 during these runs (author's reading of the Colab usage page). Before
  the Mistral rerun the author read about 60 compute units for the 24 cells including model downloads, the GPU
  smoke test and idle time (100 compute units cost USD 9.99). The 2026-10-28 estimate (84 to 125 compute
  units) was conservative.

## Mistral-7B: system text delivered by prepend; v1 cells archived; notebook fixes (2026-10-31, v0.6.2-detection-ready)

- **What was wrong.** In all four Mistral-7B evaluation cells (and in its CPU and GPU smoke tests) the model
  never received the system message. llama-cpp-python 0.3.36 recognises the chat template embedded in
  Mistral-7B-Instruct-v0.3-Q4_K_M.gguf (user and assistant turns only) and formats the conversation with its
  built-in "mistral-instruct" formatter instead of the GGUF's Jinja template; that formatter copies user and
  assistant messages and silently drops any other role. configs/models.yaml declared system_role: true for
  Mistral, so the runner sent the system text as a separate message and it was discarded before tokenisation.
  Mistral therefore saw only the user turn: the task instruction, the email and the output rule (plus the four
  examples under few_shot and the reasoning instruction under cot), without the one-sentence system framing
  that every other model received, and its role cell was the zero_shot cell under another name (same prompt
  tokens, byte-identical outputs on all 5,207 items). The 2026-10-27 smoke report had already recorded
  chat_format "mistral-instruct" for Mistral, but the consequence was not recognised; QUESTIONS.md item 9
  stated, wrongly, that the Mistral template folds the system message into the first user turn.
- **How it was found.** scripts/06_check_integrity.py (2026-10-31) compares, per model, the prompt token count
  of the role cell with that of the zero_shot cell for every item: the two user texts are identical and the role
  system text is longer, so the difference must be positive (it is exactly 32 tokens for the five other models);
  for Mistral it was 0 on every item. The cause was then verified on the laptop by loading the GGUF vocabulary
  only and rendering the runner's messages through llama-cpp-python's formatter selection (the rendered Mistral
  prompt contained no system text). No evaluation metric had been computed at that point; the pre-registration
  of QUESTIONS.md item 12 stands.
- **What changed (option (a) of item 13, author's decision 2026-10-31).** (1) configs/models.yaml: system_role
  false for mistral-7b, so detect.prompts.messages() prepends the system text to the user turn, separated by a
  blank line, exactly as for the two Gemma 2 models (item 9); the prompt files are unchanged (same prompt_hash).
  (2) scripts/detect/backend.py: a Detector now records the chat format llama-cpp-python chose and refuses
  (SystemExit) to run any model that would go through a built-in formatter while system_role is true; the run
  and smoke reports record chat_format and builtin_formatter per model. render_chat_prompt() reproduces the
  exact prompt string create_chat_completion builds. (3) tests/test_system_text.py: for every model whose GGUF
  is present, the rendered zero_shot and role prompts must contain the system text, and the role prompt must be
  longer than the zero_shot prompt by the tokens of the extra system text (within 2); and a built-in formatter
  must come with system_role false. 28 tests pass on the laptop (the four laptop GGUFs; qwen25-14b and
  gemma2-27b are checked by the same test on Colab, cell 6 of the notebook, after their download).
  (4) notebooks/cloud_run.ipynb: cell 3 changes to /content before removing an old clone and keeps the model
  weights in /content/models (symlinked as models/ in the repo dir) so they survive a re-clone; cell 5 moves
  the Drive copies of a model whose results folder was removed from the repository at the tag and archived
  under results/archive/<model>_v*/ into DRIVE_DIR/results/archive/ once (marker file), so those cells start
  fresh while later partial results still restore; cell 6 runs tests/test_system_text.py on the downloaded
  models; the MODELS parameter still selects a subset (MODELS = "mistral-7b" for the rerun).
- **Which results were archived.** results/archive/mistral-7b_v1_no_system_text/ holds, unchanged, the four v1
  Mistral evaluation cells (raw/{strategy}/eval.jsonl, 5,207 rows each, Colab T4, 2026-10-29), the v1 CPU
  smoke rows (smoke_dev/, 2026-10-27) and GPU smoke rows (smoke_gpu/, 2026-10-28), and copies of
  detection_run_report.json, integrity_check.json, smoke_dev_report.json and smoke_backend_agreement.json as
  they stood with the v1 cells; README.md in that folder explains them. They were removed from results/raw/,
  results/smoke_dev/ and results/smoke_gpu/ (git mv, history preserved). reports/integrity_check.json then
  reported 20 of 20 present cells passing and the four Mistral cells missing; the live detection_run_report.json
  and smoke_backend_agreement.json kept the v1 Mistral entries until the rerun replaced them on 2026-11-01
  (entry below).
- **Mistral CPU smoke test rerun (laptop, 2026-10-31, system text prepended; same 20 dev items):**

| cell | invalid v1 | invalid v2 | prompt tokens v1 | prompt tokens v2 | median s v1 | median s v2 | predictions v2 |
|---|---|---|---|---|---|---|---|
| zero_shot | 2/20 | 0/20 | 245 | 278 | 4.0 | 3.7 | {'phish': 9, 'legit': 11} |
| few_shot | 0/20 | 0/20 | 1151 | 1184 | 4.7 | 4.7 | {'phish': 10, 'legit': 10} |
| cot | 2/20 | 0/20 | 289 | 322 | 11.4 | 12.6 | {'phish': 9, 'legit': 11} |
| role | 2/20 | 0/20 | 245 | 310 | 4.1 | 3.6 | {'phish': 10, 'legit': 10} |

  Gate (invalid <= 10% per cell): PASS in every cell; 0 invalid of 80 against 6 of 80 in v1. The
  prompt token medians now exceed the v1 values by the system text (role by about 32 tokens more than
  zero_shot, as for the other models). Dev-set label agreement between v1 and v2 rows: zero_shot 18/20, few_shot 20/20, cot 16/20, role 18/20 (descriptive,
  dev only; not an evaluation result). The Mistral GPU smoke test and the four evaluation cells are rerun on
  Colab with TAG v0.6.2-detection-ready and MODELS = "mistral-7b"; about 6.3 h of T4 inference (7 compute
  units) by the v1 timings.
- **v1 figures (archived run; cite only as part of this incident, never as results).** GPU/CPU smoke agreement
  computed with the v1 Mistral rows: 316 of 320 (98.8%), every cell at or above 95%. Three of its four
  disagreements were Mistral-7B outputs invalid on the CPU and valid on the GPU (eph:11599 under zero_shot and
  role: "Insufficient information to determine with certainty" on CPU, LEGITIMATE on GPU; eph:7515 under cot:
  the FINAL line followed by a run-on sentence on CPU); the fourth was the qwen25-7b/cot flip on eph:5768 that
  remains in the final comparison. v1 evaluation cells (Colab T4, 2026-10-29): invalid 117 (2.25%) zero_shot,
  15 (0.29%) few_shot, 288 (5.53%) cot, 117 (2.25%) role; median latency 0.38 / 0.44 / 2.76 / 0.38 s; prompt
  token medians 235 / 1,141 / 279 / 235; 6.3 h of T4 inference (about 7 compute units); one truncated input
  (few_shot). Their sha256 values are in results/archive/mistral-7b_v1_no_system_text/integrity_check_v1.json.
- **Wording for Section 3.7 (Implementation details):** "Each detector receives the prompt through the chat
  template embedded in its GGUF file, applied by llama-cpp-python. Two templates do not carry a system message
  to the model: Gemma 2 rejects the system role, and the Mistral-7B template is handled by a built-in formatter
  of llama-cpp-python that discards system messages. For these three models the system text is prepended to
  the user turn, separated by a blank line, in every strategy; the prompt text is identical for all six models.
  The framework verifies delivery before any run: a model routed through a built-in formatter is refused unless
  this prepend rule is configured, a unit test renders the prompts of every model and checks that the role
  prompt exceeds the zero-shot prompt by exactly the system text, and the integrity check applies the same
  test to the prompt token counts recorded in every results file."
- **Wording for Section 4.8 (Threats to validity):** "A first run of the four Mistral-7B cells was made with the
  system text sent as a system message, which llama-cpp-python's formatter for this model silently dropped; the
  model saw the user turn only, and its role condition was identical to zero-shot. The defect was detected by
  the integrity check on the recorded prompt token counts before any evaluation score had been computed, the
  cells were rerun with the system text prepended to the user turn, and the first run is archived with the
  repository as evidence (results/archive/). The episode shows that prompt delivery must be verified at the
  token level, not inferred from the API; it also means that for three of the six models the system text
  reaches the model inside the user turn, a difference in position, not in wording, that is stated with the
  results."

## Step 06 complete: Mistral-7B v2 cells; 24 of 24 cells pass the integrity check (2026-11-01, v0.6.3-detection-complete)

- The four Mistral-7B evaluation cells and the Mistral GPU smoke test were rerun on a Colab Tesla T4 with
  notebooks/cloud_run.ipynb at TAG v0.6.2-detection-ready (commit 071e3a0), TIER colab_t4, MODELS "mistral-7b",
  2026-10-31 18:07 UTC to 2026-11-01 00:46 UTC (6.6 h of session time, no disconnect, no forced
  overwrite). Every row and the run report record system_role false, chat_format "mistral-instruct" and
  builtin_formatter true: the model went through llama-cpp-python's built-in formatter as before, but the
  system text now travels inside the user turn, and the backend guard admitted the run because system_role is
  false. GPU smoke test (20 dev items x 4 strategies): 0 invalid of 80, gate PASS; labels identical to the
  laptop CPU v2 run on all 80 items.
- scripts/06_check_integrity.py on 2026-11-01: 24 of 24 cells pass, system_text_delivered true for all six
  models (token difference role minus zero_shot exactly 32 on all 5,207 items of every model);
  124,968 rows, 188 invalid (0.15%), 1 truncated input. The
  results tree was checksummed before and after the check (unchanged). sha256 of the four v2 Mistral files
  (reports/integrity_check.json): zero_shot ae398b4ea3bf1a1a17162d2c6907ecc6b9bbd1f3d71ca2dc9bd0f22bf41fb659, few_shot cc3319ae78c0b13be79ec0cf7bcfa43dcb9a028139f12ffa2157263de3431380,
  cot 12af2b005f6987d20618f54ed068eeecfc52dd3bbd6541bab6fbe5e41ab278d4, role 705704b8c260b57ec583f43f4dc5d3ba44ddc7c4565b1dcc2c39626e75a3b758.
- reports/detection_run_report.json: each Mistral cell lists two sessions. The first (2026-10-29) is the
  archived v1 run, kept because the Drive copy of the report retained the cell entries and the runner appends
  sessions; the per-cell metrics (n, invalid, latency, tokens, finish reasons, hashes, git_commit 071e3a0)
  are those of the v2 run. The archived report with the v1 metrics is
  results/archive/mistral-7b_v1_no_system_text/detection_run_report_v1.json.
- Mistral-7B v1 (no system text, archived) against v2 (system text prepended; the cells used in Chapter 4):

| cell | invalid v1 | invalid v2 | median s v1 | median s v2 | prompt tokens v1 | prompt tokens v2 |
|---|---|---|---|---|---|---|
| zero_shot | 117 (2.25%) | 10 (0.19%) | 0.38 | 0.40 | 235 | 268 |
| few_shot | 15 (0.29%) | 5 (0.10%) | 0.44 | 0.45 | 1,141 | 1,174 |
| cot | 288 (5.53%) | 68 (1.31%) | 2.76 | 3.07 | 279 | 312 |
| role | 117 (2.25%) | 0 (0.00%) | 0.38 | 0.41 | 235 | 300 |

  The system text adds about 33 tokens to zero_shot, few_shot and cot and 65 to role (the role system text is
  longer), as for the other models. Invalid outputs fell in every strategy; the v2 Mistral rates
  (0.19 / 0.10 / 1.31 / 0.00%) are of the same order as those of the other models, and mistral-7b/cot at 1.31%
  is now the highest cell of the study, followed by qwen25-14b/cot at 1.15%. No label was compared with the
  ground truth; the pre-registration of QUESTIONS.md item 12 stands.
- GPU/CPU smoke agreement recomputed with scripts/06_compare_smoke.py: 319 of 320 (99.7%), the four v2 Mistral
  cells at 100% (raw outputs byte-identical in zero_shot, few_shot and role, 30% in cot), the only remaining
  disagreement the qwen25-7b/cot flip on eph:5768. The agreement bullet and the Section 4.2.1 and 4.8 wording
  of the entry of 2026-10-28 to 2026-10-31 above were revised in place to these figures; 98.8% (316 of 320)
  appears only in the Mistral incident entry.
- Final GPU time and cost. Session wall-clock from the run report: T4 38.8 h over all sessions
  (of which the archived v1 Mistral run 6.3 h and the v2 rerun 6.6 h), L4 9.5 h; at
  1.15 and 1.94 compute units per hour this is 44.6 + 18.4 = 63 compute units for
  inference alone (about USD 6.3 at USD 9.99 per 100 units), of which the Mistral
  incident cost 7.2. Model downloads, the GPU smoke tests and idle time come on top.
- **Colab cost after step 06 (author's reading of the Colab balance, 2026-11-01; superseded by the final
  figure in the entry "Step 07: dev CoT run complete" below):** 75.7 compute units consumed for step 06
  (100 units of a Colab Pro subscription, 24.27 remaining): about 62 for the first full pass over the 24
  cells, about 7 for the Mistral v2 rerun, and the rest (about 7) idle sessions and model downloads; rates
  1.15 compute units per hour on the T4 and 1.94 on the L4. The DistilBERT baseline and the six dev CoT cells
  of step 07 came on top; the final Section 3.7 wording is in that later entry.
- Housekeeping: 36 Zone.Identifier transfer artefacts deleted; the Drive copy of the Colab download report
  (six models, Mistral re-verified 2026-10-31) is kept as reports/models_download_report_colab.json and the
  laptop report reports/models_download_report.json (four models) restored from git after the copy had
  overwritten it.
- TASK_06 section 6 status: items 1, 2, 3, 5, 6 and 8 done; item 4 (baselines tfidf_lr, tfidf_svm, distilbert)
  and item 7 (proprietary zero-shot reference) remain. Step 07 scoring does not start before the baselines
  exist, so that every detector and baseline is scored by the same code in one pass.
- Wording for Section 4.2.1 (addition): "The four Mistral-7B cells were run twice; the first run is archived and
  excluded (Section 4.8), and all results reported for Mistral-7B come from the second run, in which the system
  text reached the model. Including the repeated run, evaluation inference took about 39 hours on the T4
  and 10 hours on the L4, about 63 Colab compute units."

## Step 06 baselines: TF-IDF + logistic regression and TF-IDF + linear SVM (2026-11-01); DistilBERT prepared for Colab

- Interface approved on 2026-11-01 (TASK_06 section 3, decision 3; the script keeps the TASK_06 name
  scripts/06_run_baselines.py and the CLAUDE.md step-07 row points at it). configs/baselines.yaml fixes every
  setting before the evaluation run: text = subject + blank line + body (the two fields the detectors see);
  training partition `train` (3,033 records: 2,299 traditional phishing + 734 Enron ham, the Nahmias protocol,
  no E-PhishLLM record); `valid` (337: 255 + 82) for the choice of C and the sanity check only; evaluation on
  exactly the 5,207 detector items built by detect.items.eval_items. Features: word 1 to 2-grams, min_df 2,
  lowercase, sublinear tf, no vocabulary cap; classifiers LogisticRegression (lbfgs, max_iter 1000) and
  LinearSVC (squared hinge, max_iter 10,000), no class re-weighting (the 76% phishing training prior is part of
  the protocol); C grid {0.1, 0.3, 1, 3, 10}, chosen by F1 of the phishing class on `valid`, ties to the
  smallest C; decision rules fixed in the config: p(phish) >= 0.5 for the logistic regression and DistilBERT,
  decision value > 0 for the SVM. Seed 2026 from configs/data.yaml. Nothing is chosen on an evaluation
  partition; the config was committed (frozen) before the first eval run and the runner refuses an eval run
  while configs/baselines.yaml is uncommitted or modified (checked: it refused before the freeze commit).
- Output in the detector runner's schema, results/raw/baseline_{key}/supervised/{valid,eval}.jsonl, one row per
  item: item_id, partition, condition, label_true, model (baseline_tfidf_lr, ...), strategy (supervised),
  raw_output ("p_phish=0.125011" or "decision_function=-0.83"), label_pred, invalid (always false; a baseline
  always answers), score, config_hash (sha256 of the baseline's own config block + text settings + seed; the
  counterpart of prompt_hash), model_hash (sha256 of the sorted vocabulary, coefficients and intercept of the
  fitted model), n_prompt_tokens (non-zero TF-IDF features of the item), n_output_tokens 0, finish_reason n/a,
  latency_s, truncated_input (always false for TF-IDF), backend cpu. Resumable, skip-when-complete and
  refuse-to-overwrite exactly as the detector runner (the two runners now share detect.resume.read_rows;
  tests/test_resume.py and the new tests/test_baselines.py, 38 tests in all, pass). The fitted models are saved
  to models/baselines/ (gitignored; file sha256 in the report).
- Model selection on `valid` (precision, recall, F1 of the phishing class; false positives and misses out of 82
  legitimate and 255 phishing records). These are selection and sanity figures, not evaluation results:

  TF-IDF + logistic regression (chosen C = 1.0; ties among 1, 3 and 10 resolved to the smallest):

| C | precision | recall | F1 | FP | FN |
|---|---|---|---|---|---|
| 0.1 | 0.8615 | 1.0000 | 0.9256 | 41 | 0 |
| 0.3 | 0.9770 | 1.0000 | 0.9884 | 6 | 0 |
| 1.0 | 0.9961 | 1.0000 | 0.9980 | 1 | 0 |
| 3.0 | 0.9961 | 1.0000 | 0.9980 | 1 | 0 |
| 10.0 | 0.9961 | 1.0000 | 0.9980 | 1 | 0 |

  TF-IDF + linear SVM (chosen C = 0.3; ties among 0.3 to 10 resolved to the smallest):

| C | precision | recall | F1 | FP | FN |
|---|---|---|---|---|---|
| 0.1 | 0.9961 | 1.0000 | 0.9980 | 1 | 0 |
| 0.3 | 1.0000 | 1.0000 | 1.0000 | 0 | 0 |
| 1.0 | 1.0000 | 1.0000 | 1.0000 | 0 | 0 |
| 3.0 | 1.0000 | 1.0000 | 1.0000 | 0 | 0 |
| 10.0 | 1.0000 | 1.0000 | 1.0000 | 0 | 0 |

  Sanity check on `valid` with the chosen C: tfidf_lr F1 0.998 (precision 0.9961, recall
  1.0, 1 false positive of 82); tfidf_svm F1 1.000 (0 errors of 337). The task on
  `valid` is the easy in-distribution one (traditional phishing against Enron ham), so near-perfect F1 is the
  expected sanity result and says nothing about the spear-phishing evaluation; vocabulary 88,605
  features; fitting the whole grid takes 8.84 s (LR) and 1.26 s (SVM) on the laptop CPU.
- Determinism: a refit on the same machine reproduces the model_hash bit for bit (model_hash_reproduced true in
  reports/baselines_report.json for both models; the second valid run was skipped as already complete with
  matching hashes). model_hash tfidf_lr 20259f940b276711..., tfidf_svm 80cf13cbd09419a3....
- Evaluation cells written on the laptop (eval_tier laptop; the GPU rule of CLAUDE.md concerns LLM inference):
  baseline_tfidf_lr/supervised/eval.jsonl and baseline_tfidf_svm/supervised/eval.jsonl, 5,207 rows each, the
  same partition and condition counts as every detector cell, about 1 ms per item (2.2 s and
  2.1 s for the whole set), no truncation. Predicted-label counts are in the report
  (pred_counts); no label was compared with the ground truth on eval (scoring is step 07; QUESTIONS.md item 12
  stands). Rerunning an eval cell skips it; --force without --reason is refused (both checked).
- scripts/06_check_integrity.py now has a baselines section: for every baseline of configs/baselines.yaml it
  checks the exact item set, duplicates, item metadata, model and strategy fields, config_hash against the
  frozen config block, model_hash against reports/baselines_report.json, backend of the eval tier, label_pred
  reproducible from the stored score with the fixed rule, invalid false everywhere, and the report entry's
  consistency; results go to the "baselines" key of reports/integrity_check.json. Result 2026-11-01: tfidf_lr
  and tfidf_svm pass; distilbert is reported missing, so the overall exit code stays 1 until the Colab run is
  copied back (24/24 detector cells pass as before).
- DistilBERT (configs/baselines.yaml: distilbert-base-uncased, 3 epochs, lr 2e-5, batch 16, max 512 tokens,
  AdamW, linear schedule without warm-up, weight decay 0.01, fp32, deterministic kernels, seed 2026, no early
  stopping and no epoch selection; truncated inputs flagged per item in training and scoring) is implemented
  in scripts/baselines/distilbert.py as a plain PyTorch loop and run by notebooks/cloud_baselines.ipynb on a
  Colab T4: the notebook clones the repository at REF, installs requirements-baselines.txt (torch is the Colab
  CUDA build, version recorded), pulls the processed data from Drive, restores the checkpoint and partial
  results from Drive, trains once (checkpoint models/baselines/distilbert.pt, sha256 = model_hash of every
  row, copied to Drive, not to git), scores valid then eval with the same script and schema, and syncs
  results/raw/baseline_distilbert/ and reports/baselines_report.json after each cell. The Hugging Face
  snapshot commit of the pretrained weights is recorded in the report. Not run yet.
- Wording for Section 3.5 / 4.4 (Baselines): "Three supervised baselines are trained on the traditional
  phishing and Enron ham records of the training partition (3,033 messages) following the protocol of Nahmias
  et al. (2024), and evaluated on exactly the items the language models receive. Two use TF-IDF features over
  word unigrams and bigrams (minimum document frequency 2, sublinear term frequency) with a logistic regression
  and a linear support vector machine respectively; the regularisation strength is the only tuned parameter,
  chosen on a held-out validation split of the same training distribution (337 messages) by the F1 of the
  phishing class over the grid 0.1, 0.3, 1, 3, 10, giving C = 1.0 and C = 0.3. The third baseline
  fine-tunes DistilBERT (base, uncased) for three epochs with learning rate 2e-5 and batch size 16 on inputs
  truncated to 512 tokens, with a fixed seed and no early stopping. Decision thresholds are fixed in advance
  (probability 0.5, decision value 0). On the validation split the two TF-IDF models reach F1 0.998 and
  1.000, which confirms that the pipeline is sound but, since validation and training share one
  distribution, says nothing about the spear-phishing evaluation. Baseline predictions are stored in the same
  one-row-per-item format as the language-model outputs and pass the same integrity check."

## Proprietary reference dropped (2026-11-01, QUESTIONS.md item 14; tag v0.6.4-baselines-ready)

- Decision (author, 2026-11-01): the optional proprietary zero-shot reference of TASK_06 section 3 is not run.
  Reasons: a proprietary model is outside the scope set in Section 1.6 (open models run locally, no hosted
  API); the licence status of the E-PhishLLM e-mails does not clearly permit their transfer to a third-party
  API; and a proprietary comparison belongs to future work. `proprietary_ref` is removed from the TASK_06
  definition of done and from CLAUDE.md; scripts/06_run_proprietary.py is not written. The repository is
  tagged v0.6.4-baselines-ready at this state (detector cells complete, TF-IDF baselines complete, DistilBERT
  prepared for Colab).
- Wording for Section 3.5 / 4.4 (Baselines): "No proprietary model is included as a point of comparison: the
  study evaluates open models run locally (Section 1.6), and the licence terms of one of the evaluation corpora
  do not clearly permit sending its messages to an external service."
- Wording for Section 5.5 (Future work): "A comparison with a proprietary model under the same zero-shot prompt
  would place the open models' results against the strongest commercially available detector; it was not
  attempted here because the data licences do not clearly permit transfer to a third-party service, and it
  would require either a corpus released under terms that allow it or a provider agreement on retention and
  training use."

## Step 06 complete: DistilBERT baseline on Colab T4; 24 cells + 3 baselines pass the integrity check (2026-11-01, v0.6.5-step06-complete)

- Run: notebooks/cloud_baselines.ipynb at REF v0.6.4-baselines-ready (commit cf6a308), Tesla T4, torch
  2.11.0+cu130, transformers 5.19.0, pretrained distilbert-base-uncased at Hugging Face snapshot
  12040accade4e8a0f71eabdb258fecc2e7e948be. Training on `train` (3,033 e-mails: 2,299 traditional phishing, 734 Enron
  ham) with the frozen settings (3 epochs, lr 2e-5, batch 16, max 512 tokens, AdamW, weight decay 0.01, linear
  schedule, fp32, seed 2026, no early stopping): 570 steps in 503 s, mean training loss per epoch
  0.0871, 0.00914, 0.00237. Checkpoint models/baselines/distilbert.pt (268 MB, gitignored, copy on Drive),
  **sha256 274764c766ff7a29dfd440822ba5a64f332a6a5ba3976be16422308472af6db1** = model_hash of every DistilBERT row.
- Scoring: valid 337 rows (5.9 s), eval 5,207 rows (75.3 s, median 0.01 s per item on the T4).
  Sanity check on `valid`: precision 1.0, recall 1.0, F1 1.0 (no error on 337 records; the
  in-distribution task, as for the TF-IDF models). No eval label was compared with the truth.
- Truncation at 512 wordpieces (subject + body): 1,503 of 3,033 training e-mails (49.6%),
  171 of 337 validation e-mails, and 330 of 5,207 evaluation items (6.3%) exceeded the limit
  and were cut; every row carries the truncated_input flag. On the evaluation set the truncated items are all
  legitimate: 266 core_neg originals (long Enron threads and SpamAssassin hard ham) and 64 paraphrased
  ctrl_para_legit items; no spear-phishing original or variant and no E-PhishLLM message was cut (the Nahmias
  spear-phishing bodies are 59 to 324 words). The TF-IDF baselines and the language models (n_ctx 4,096; one
  truncated input in 124,968 rows) saw these e-mails in full.
- Determinism: the run requested deterministic kernels (torch.use_deterministic_algorithms(True, warn_only=True),
  cuDNN deterministic, seeded data order, fp32), but the author's reading of the Colab log shows that the
  attention kernel used on the T4 has no deterministic implementation and ran in its non-deterministic form
  (warning, not an error). A retraining can therefore produce a checkpoint that differs in the last bits. As
  for the variant generation (QUESTIONS.md item 8), the fixed artefact is the saved checkpoint, identified by
  its sha256 above, not the training procedure; scoring with the saved checkpoint is deterministic (the runner
  refuses to score with a checkpoint whose hash differs from the recorded one).
- Integrity (scripts/06_check_integrity.py, 2026-11-01): 24 of 24 detector cells and 3 of 3 baselines pass;
  results/raw/baseline_distilbert/supervised/eval.jsonl sha256 ef6a404ddcf08332b0304b21bca7b689b349b44a71476d16927002fba45478e3. The results tree was
  checksummed before and after (unchanged). Four Zone.Identifier transfer artefacts deleted.
- TASK_06 definition of done, checked item by item: configs/models.yaml, configs/detection.yaml and prompts/
  frozen with hashes in the reports (and configs/baselines.yaml for the baselines); results/raw/ complete for
  6 models x 4 strategies + 3 baselines, every file passing the integrity check; per-cell invalid rates and
  latencies in reports/detection_run_report.json (baselines in reports/baselines_report.json); every prompt
  revision, model substitution and throughput estimate in this file; no evaluation item was used to choose or
  change anything (prompts and thresholds fixed on dev / valid, C chosen on valid, pre-registration item 12
  unchanged, no metric computed). Step 06 is complete at tag v0.6.5-step06-complete.
- Wording for Section 4.4 (Baselines, addition): "The DistilBERT baseline was fine-tuned on a Colab T4 with the
  settings above in 8.4 minutes and reached F1 1.0 on the validation split, like the TF-IDF models. Its
  input is limited to 512 wordpieces: 50% of the training e-mails and 330 of the 5,207 evaluation
  items (6.3%), all of them legitimate messages from the Enron and SpamAssassin corpora, were truncated,
  whereas the language models received every message in full. The fine-tuned checkpoint is archived with its
  hash and is the artefact scored in this chapter."
- Wording for Section 4.8 (Threats to validity, addition): "Fine-tuning on the GPU was not bitwise reproducible:
  the attention kernel available on the T4 has no deterministic implementation, so a retraining with the same
  seed can yield slightly different weights. As with the paraphrase generation, the saved checkpoint, identified
  by its SHA-256 hash, is treated as the fixed artefact, and all DistilBERT results derive from it
  deterministically. The truncation of long legitimate e-mails at 512 tokens is a limitation of the DistilBERT
  baseline only and may affect its false positive rate on the Enron and SpamAssassin negatives; it does not
  touch the spear-phishing items."

## Step 07 item 1: scoring item table built; no metric computed (2026-11-01)

- docs/TASK_07_scoring.md (approved 2026-11-01) committed first. scripts/07_build_items.py (functions in
  scripts/scoring/items.py, tests/test_build_items.py, 6 tests; whole suite 44 tests pass) verifies the sha256
  and row count of the 27 input files against reports/integrity_check.json, joins every prediction with its
  item's partition, condition, item class, partition set, cluster (source e-mail id), source, subclass and body
  length, and writes results/scores/items.parquet (140,589 rows x 20 columns; sha256
  857b43eb24d3f57c0cd05444291556b816b35bd68292df3d475268ac43ec0dbc) and results/scores/pairs.csv (1,537 accepted variants
  paired with their originals; sha256 4e953bb64eb5a6bcbcb9b3a426038d727e7872e43d2b0a5cb42c1dc146affa9e); reports/items_build_report.json holds the input
  and output hashes. A rebuild is byte-identical (--check). pandas 3.1.0 and pyarrow 26.0.0 pinned.
- Structure (Section 4.2.2): 5,207 items per cell over 3,670 clusters; item classes
  {'gen_legit': 1000, 'gen_phish': 1000, 'legit_core_neg': 1002, 'legit_ctrl_modern': 334, 'legit_ctrl_para': 210, 'phish_original': 334, 'phish_variant': 1327}; pairs per condition {'legit_ctrl_para/para_high': 210, 'phish_variant/obf_high': 334, 'phish_variant/obf_low': 334, 'phish_variant/para_high': 325, 'phish_variant/para_low': 334}. All 210 paraphrased legitimate controls
  descend from core_neg records, so every control variant has an original prediction in every cell.
- No prediction was compared with its label: the table carries label_true and label_pred side by side and has
  no correctness column (asserted by a test); the pre-registration of QUESTIONS.md item 12 stands.
- Nine points where TASK_07 is ambiguous or extends item 12 are written to QUESTIONS.md item 15 for the author;
  (g), the basis of the CoT cue lexicon, must be answered before step 2, the others before step 3.

## Step 07: decisions on QUESTIONS.md item 15 (a) to (f) logged; RQ labels fixed (2026-11-01, before any score)

- The author answered item 15 (a) to (f) on 2026-11-01; the decisions are recorded under item 15, the ones that
  refine the pre-registration are logged under item 12 with the date, and docs/TASK_07_scoring.md now uses the
  thesis numbering: RQ1 effectiveness (descriptive, no test family), RQ2 model comparison (F-RQ2 = 8 size
  contrasts), RQ3 prompting (F-RQ3 = 36 strategy contrasts), RQ4 robustness (F-RQ4 = 30 zero_shot McNemar
  tests, the headline family); secondary Holm families for the other strategies, the baselines and the
  ensemble; bootstrap-contrast p two-sided percentile floored at 1/B with the CI primary; four-way cue-change
  split; hard-core strata and sample rule; a priori power assumption (10% discordance). Still no metric
  computed. (g) (basis of the cue lexicon) and (h) (sensitivity analysis on paired deltas) are awaited.
- Wording for Section 4.3 (statistics; to be completed in step 3): "Confidence intervals are 95% percentile
  intervals from a cluster bootstrap with the original e-mail as the resampling unit (B = 2000). Paired
  original-versus-variant comparisons use the exact McNemar test; contrasts between models or between prompting
  strategies are differences of robustness deltas, with a two-sided bootstrap p-value equal to twice the
  smaller tail proportion of the bootstrap distribution, floored at 1/B. p-values are Holm-corrected within
  each family of tests, one family per research question (the 30 zero-shot robustness tests for RQ4, the 8 size
  contrasts for RQ2, the 36 strategy contrasts for RQ3), and reported alongside their uncorrected values and
  the effect size with its interval. Effectiveness (RQ1) is reported descriptively with intervals."

## TASK_07 item 15 complete; dev CoT run for the cue lexicon (2026-11-01, v0.7.0-devcot)

- Decisions (g), (h), (i) of QUESTIONS.md item 15 recorded; (h) is logged in item 12 as refinement (6). The cue
  lexicon (item 12b) will be frozen on the CoT rationales of the full dev partition for all six detectors plus
  the smoke sets, all dev only, run on Colab with the uniform GPU backend. Dev item set = the runner's dev set:
  796 items (400 originals, 596 phishing and 200 legitimate, plus the accepted dev variants
  para_low 100, para_high 96, obf_low 100, obf_high 100), so the rationales cover paraphrased and
  obfuscated text as on eval. Rows go to results/raw/<model>/cot/dev.jsonl (report cells <model>/cot/dev);
  eval files are not touched (the runner's cell is keyed by partition).
- L4 handling of gemma2-27b for a dev run, checked in the code: 06_run_detection.py applies the eval_tier
  check to eval runs only; the notebook chooses the models whose eval_tier equals TIER (gemma2-27b alone for
  colab_l4) and asserts the runtime GPU; results sync to Drive after the cell.
- Estimate from the eval CoT mean latencies: T4 run (llama31-8b, mistral-7b, gemma2-9b, qwen25-7b,
  qwen25-14b) about 4.2 h (4.8 compute units); L4 run (gemma2-27b) about 1.0 h (1.9 compute units).
- Colab parameters, notebooks/cloud_run.ipynb: T4 run TAG "v0.7.0-devcot", TIER "colab_t4", MODELS "",
  STRATEGIES "cot", PARTITION "dev", RUN_SMOKE False, RUN_EVAL True; L4 run the same with TIER "colab_l4".
  Afterwards copy results/raw/<model>/cot/dev.jsonl for the six models and reports/detection_run_report.json
  back; step 2 then builds the lexicon from these files and the smoke sets and freezes it with a hash.

## Step 07: dev CoT run complete (6 x 796 rationales for the cue lexicon); final Colab consumption (2026-11-01)

- The cot strategy was run on the full dev partition for all six detectors on Colab from tag v0.7.0-devcot
  (QUESTIONS.md item 15g): 796 dev items per model (400 originals, 396 accepted dev variants), one session
  each, all complete, GPU backend (cuda), llama-cpp-python 0.3.36, prompt hash of prompts/cot.txt unchanged.
  Files results/raw/<model>/cot/dev.jsonl (6 x 796 rows) and the six cells <model>/cot/dev in
  reports/detection_run_report.json are committed; the 24 eval files and the 3 baseline files are
  byte-identical to the committed versions (checked by sha256 against HEAD), and the 24 existing report cells
  are unchanged. These rows are dev data: they serve only to write the cue lexicon (TASK_07 step 2) and are
  never scored.

  | model | GPU | invalid (rate) | latency median / mean s | wall h | output tokens median | empty rationale |
  |---|---|---|---|---|---|---|
  | llama31-8b | Tesla T4 | 1 (0.13%) | 4.48 / 4.67 | 1.03 | 92 | 0 |
  | mistral-7b | Tesla T4 | 8 (1.01%) | 3.24 / 3.27 | 0.72 | 69 | 91 |
  | gemma2-9b | Tesla T4 | 1 (0.13%) | 3.52 / 3.61 | 0.80 | 54 | 0 |
  | qwen25-7b | Tesla T4 | 0 (0.00%) | 2.24 / 2.07 | 0.46 | 46 | 262 |
  | qwen25-14b | Tesla T4 | 4 (0.50%) | 8.49 / 8.64 | 1.91 | 92 | 0 |
  | gemma2-27b | NVIDIA L4 | 1 (0.13%) | 4.41 / 4.47 | 0.99 | 55 | 0 |

  Invalid outputs 15 of 4,776 (0.3%). "Empty rationale" = the output is only the "FINAL:" line, so
  the rationale contributes no cue (mostly qwen25-7b, which often answers without reasoning on dev).
  Wall-clock: T4 4.92 h for the five smaller models (about 5.7 compute units at 1.15 per hour),
  L4 0.99 h for gemma2-27b (about 1.9 compute units at 1.94 per hour); the pre-run estimate was
  4.2 h and 1.0 h.
- Housekeeping: 41 Zone.Identifier transfer artefacts deleted (no results file modified). The Drive copy also
  brought an untracked duplicate results/raw/mistral-7b_v1_no_system_text/ (four eval files, byte-identical to
  results/archive/mistral-7b_v1_no_system_text/raw/); it is not committed and can be deleted.
- **Final Colab consumption (author's reading of the balance, 2026-11-01): 86.9 compute units in total,
  13.12 remaining of the 100 units of a Colab Pro subscription, about USD 8.70.** This covers the 24
  detector cells (first pass about 62 units), the Mistral-7B rerun (about 7), the DistilBERT baseline, the six
  dev CoT cells (about 8), and model downloads and idle session time. Rates 1.15 compute
  units per hour on the Tesla T4 and 1.94 on the NVIDIA L4.
- Wording for Section 3.7 (Implementation details, cost), replacing the earlier draft: "All GPU work ran on
  Google Colab under a Colab Pro subscription and consumed 86.9 compute units in total (about USD 8.70 at the
  2026 price of USD 9.99 per 100 units): about 62 units for the first pass over the 24 model-strategy cells,
  about 7 for the repeated Mistral-7B cells (Section 4.8), about 8 for the chain-of-thought run on the
  development partition that served to build the cue lexicon (Section 4.3), and the remainder for the
  DistilBERT baseline, model downloads and idle session time. Colab charged 1.15 units per hour on the Tesla
  T4 and 1.94 on the NVIDIA L4. Evaluation inference alone took about 39 hours on the T4 and 9.5 hours on the
  L4."

## Step 07 step 2: CoT cue lexicon frozen on dev (2026-11-01); no score computed

- configs/cue_lexicon.yaml, **sha256 e209c7a565add8bf7d88595b94d3f7174535ec93c6b35206225c58b8f43822fd**, version 1, eight
  pre-registered categories (QUESTIONS.md item 12b) with 21 named sub-patterns in total; scripts/scoring/cues.py
  (loader, matcher, polarity heuristic), scripts/07_freeze_lexicon.py (dev-only freeze and report, --check
  reproduces the report), tests/test_cue_lexicon.py (17 tests, including a guard that fails if the YAML
  changes without re-freezing); whole suite 61 tests OK. common.cot_rationale() splits the rationale from the
  verdict with the same marker rule as extract_label.
- Basis: 4,956 dev rationales, the six full-dev CoT cells (6 x 796, tag v0.7.0-devcot, Colab) plus the smoke
  sets (9 x 20); every row asserted to be partition dev and strategy cot; a path containing "eval" is refused.
  369 rationales are empty (only the FINAL line): qwen25-7b 276, mistral-7b 93.
- Polarity: a match is negated when a negation marker (no, not, n't, never, without, lack(s), absence of, free
  of, neither, nor, rather than, instead of) occurs earlier in the same clause and no conjunction plus
  asserting verb ("and uses", "but contains") stands between them; clauses start at sentence punctuation,
  contrastive conjunctions and ", and the ...". A category is asserted when at least one match is not negated.
  Motivation from dev: legitimate verdicts list the cues they do not find ("There are no suspicious links,
  requests for personal information, or urgent calls to action"); on dev 30% of link mentions and
  26% of credential/payment mentions are negated.
- Dev counts (rationales mentioning / asserting / only negating each category; sub-pattern figures are
  asserted matches, several per rationale possible):

  | category | sub-patterns | mentioned | asserted | negated |
  |---|---|---|---|---|
  | urgency | deadline (114), pressure_threat (602), urgent_language (2203) | 2117 | 1703 | 414 |
  | link / URL | click (454), link (2001) | 2300 | 1607 | 693 |
  | sender / domain mismatch | sender_address (228), spoof_mismatch (28), unknown_sender (178) | 566 | 368 | 198 |
  | credential / payment request | credentials (967), payment_request (947), personal_information (1096) | 2464 | 1828 | 636 |
  | grammar / spelling | character_anomaly (499), grammar (600), spelling (675) | 1128 | 1086 | 42 |
  | impersonation / authority | authority_figure (593), impersonation (401) | 794 | 756 | 38 |
  | attachment | attachment (522), file_download (386), malware (172) | 761 | 639 | 122 |
  | generic greeting | generic_greeting (529), not_personalized (80) | 610 | 582 | 28 |

  Asserted categories per rationale (all 4,956, empty included): {'0': 999, '1': 881, '2': 1156, '3': 963, '4': 473, '5': 96, '6': 18, '7': 1}.
  Among the 4,587 non-empty rationales 86.3% assert at least one category.
- Three seeded example matches per category (seed 2026; the report holds one negated example per category as
  well), for the author's review of the regexes:
  - urgency (urgent_language, "urgency"): This email uses common phishing tactics like creating a sense of urgency ("at your earliest convenience") and including a shortened, suspicious link. The misspell...
  - urgency (pressure_threat, "scare"): The email uses scare tactics, urging immediate action due to "potential vulnerabilities" and threats of data b...
  - urgency (urgent_language, "urgency"): ...onal language with misspellings like "re4ching" and "plea​se". It also creates a sense of urgency with "Action Required" and pressures the recipient to click a link without providing cont...
  - link / URL (link, "link"): ...one, a vague reference to the CEO's office, and a request to verify credentials through a link. The email also lacks specific details about the company's policies and procedures, which...
  - link / URL (link, "link"): The email asks the recipient to review a document and provides a link. However, there are no red flags such as urgent language, requests for personal informati...
  - link / URL (link, "link"): ...review related to a specific project on renewable energy strategies. It includes a direct link to access the document. However, without verifying the sender's email address and the leg...
  - sender / domain mismatch (spoof_mismatch, "do not match"): ... indicative of phishing attempts. The sender's name and the company name in the signature do not match, and the bank details provided seem unusual and could be fabricated to trick the recipien...
  - sender / domain mismatch (unknown_sender, "suspicious email address"): ... a verbal telephone communication to discuss the deal. Additionally, the email contains a suspicious email address and multiple promotional links from Yahoo, which may be an attempt to distract the recipi...
  - sender / domain mismatch (sender_address, "sender's email address"): ...ars to be requesting sensitive healthcare data, which is unusual for a collaboration. The sender's email address is not provided, and the request seems urgent, which are common tactics in phishing attem...
  - credential / payment request (payment_request, "payment"): ... overdue payment for an order. The email includes the invoice number, the amount due, and payment instructions. However, the sender's email address is not clearly visible, which is a red ...
  - credential / payment request (credentials, "account suspension"): This email uses scare tactics, urging immediate action and threatening account suspension. It asks for personal information through a suspicious link. These are common hallmarks o...
  - credential / payment request (payment_request, "transferring the money"): ...y that the sender needs help transferring. The email also asks the recipient to assist in transferring the money, which is a common tactic used by scammers to gain the trust of their victims. Additional...
  - grammar / spelling (character_anomaly, "unusual formatting"): ...and could apply to many different software solutions. The email contains misspellings and unusual formatting, which are common red flags for phishing attempts.
  - grammar / spelling (character_anomaly, "unusual character"): The email contains several spelling errors and unusual character substitutions, which are common red flags for phishing attempts. The request for immediat...
  - grammar / spelling (spelling, "misspelled"): ...nt Required") and requesting action without verifying the sender's identity. The slightly misspelled words and the unusual formatting of the email address are also red flags.
  - impersonation / authority (authority_figure, "IT support"): ...common tactic in phishing attempts. However, it includes specific details such as a named IT support team member and a company name, which could indicate legitimacy. The inclusion of a deadl...
  - impersonation / authority (authority_figure, "government"): First analysis: The email claims to be from a high-ranking government official offering a business partnership to transfer a large sum of money into the recipi...
  - impersonation / authority (impersonation, "claims to have"): This email is a typical example of a Nigerian prince or widow scam, where the sender claims to have a large sum of money that they wish to transfer but needs assistance from the recipient t...
  - attachment (attachment, "attachment"): ...ze the others as they come in and redistribute the report. The email also includes a file attachment, which suggests that it is a legitimate business communication. The sender's name and the...
  - attachment (attachment, "attachment"): ...ements, such as a misspelled word ("dоcuments", "contr4ct", "inp​ut", "rel4tions") and an attachment with a suspicious name. Additionally, the email asks the recipient to click on a link, wh...
  - attachment (attachment, "attachment"): ... (CRM initiative), and uses a professional tone. However, the phrase "Promptly access the attachment" could be seen as slightly urgent and potentially manipulative, which is a common tactic ...
  - generic greeting (generic_greeting, "generic greeting"): ...etails through a provided link, which is a common tactic in phishing emails. The use of a generic greeting ("Hello Sarah") and the mention of a specific project ("customer outreach initiatives") w...
  - generic greeting (generic_greeting, "generic greeting"): ...for personal information, and an unsolicited offer of inheritance. The sender also uses a generic greeting and provides an email address that looks suspicious.
  - generic greeting (generic_greeting, "generic greeting"): ... security update requires an immediate password reset. It contains suspicious typos and a generic greeting. The link is not from a trusted source and is likely malicious.
- Known limitations of the heuristic, to be stated in Section 4.8 rather than corrected: a "lack of X, the Y,
  and the Z" list leaks the negation onto Y and Z; "without verifying the attachment" negates an attachment
  that exists; descriptive mentions of an authority ("signed by the CEO") count as authority cues whether or
  not impersonation is alleged (hence the separate sub-pattern authority_figure). Open reporting choices
  (asserted vs any mention, denominator, sub-pattern placement) are in QUESTIONS.md item 16 with defaults.
- Wording for Section 4.3 (cue analysis): "Chain-of-thought rationales were analysed with a fixed cue lexicon
  of eight categories (urgency; link or URL; sender or domain mismatch; credential or payment request; grammar
  or spelling, including the character-level anomalies of the obfuscated condition; impersonation or
  authority; attachment; generic greeting), each defined by named regular expressions. The lexicon was
  written from the rationales of the six detectors on the development partition (4,956 rationales: 796
  development items per model and the smoke tests) and frozen, with its SHA-256 hash recorded, before any
  evaluation rationale was read. A rationale is the model output before its final verdict line. A category
  counts as asserted when one of its patterns matches outside the scope of a negation; the scope of a negation
  marker (no, not, without, lacks, free of and similar) extends to the end of its clause unless a conjunction
  followed by an asserting verb intervenes. Mentions inside such a scope are counted separately as negated,
  because on the development rationales most cue mentions in legitimate verdicts were denials (30% of the
  link mentions). Cue frequency is reported per model and condition as the share of non-empty rationales that
  assert the category, and the change in cue presence between an original and its variant is split by the
  four prediction outcomes."
- Step 3 (the first and only computation of the scores) has not started; it waits for the author's go-ahead
  and the answers to item 16.

## Step 07 step 3: scores computed, the first and only computation (2026-11-01, v0.7.1-scored)

Computed once under QUESTIONS.md item 12 (refinements 1 to 7) and the decisions of items 15 and 16, from
results/scores/items.parquet (hash-verified) by scripts/07_score.py, 07_secondary.py and 07_tables_figures.py
(scripts/scoring/stats.py, score.py, ensemble.py, output.py; tests/test_scoring.py, 10 tests, whole suite 71 OK).
Runtime: scoring 48 s, secondary analyses 12 s, tables and figures a few seconds (laptop CPU).
Re-runs of 07_score.py --check and 07_secondary.py --check reproduce every CSV byte for byte (the test suite
runs the scoring check). Outputs: results/scores/metrics_long.csv (1147 rows), deltas_long.csv
(310), contrasts.csv (88), ensemble_predictions.csv, ensemble_votes.csv, cues_frequency.csv, cues_change.csv,
cues_pairs.csv, hardcore_items.csv, hardcore_summary.csv, frontier.csv; results/tables/tab_t1 to t11 and a1
(.tex, booktabs, no caption); figures/ch04_f1 to f7_eng.png (300 dpi); reports/scoring_report.json,
secondary_report.json, tables_figures_report.json, hardcore_sample.csv. Families: {'F-RQ2': 8, 'F-RQ3': 36, 'F-RQ4': 30, 'S-baselines': 15, 'S-cot': 30, 'S-ensemble': 20, 'S-few_shot': 30, 'S-role': 30}.
Power note (Section 4.8, a priori): exact McNemar, 334 pairs, 10% discordant, 5-point drop, alpha 0.05:
power 0.80. Observed discordance of the 30 F-RQ4 tests (post hoc, descriptive): median 0.19, range 0.003 to 0.78.

**Headline numbers (primary analysis, invalid = incorrect).**

T1, capability on the 1,670 core originals (zero-shot for the models):

  | detector | acc | bal. acc | F1 phish | sens (334) | spec core (1,002) | spec modern (334) |
  |---|---|---|---|---|---|---|
  | Llama-3.1-8B | 0.707 | 0.525 | 0.233 | 0.222 | 0.772 | 0.997 |
  | Mistral-7B | 0.651 | 0.630 | 0.409 | 0.596 | 0.554 | 0.997 |
  | Gemma-2-9B | 0.778 | 0.833 | 0.626 | 0.925 | 0.660 | 0.985 |
  | Qwen2.5-7B | 0.799 | 0.594 | 0.334 | 0.251 | 0.915 | 1.000 |
  | Qwen2.5-14B | 0.851 | 0.692 | 0.534 | 0.425 | 0.945 | 0.997 |
  | Gemma-2-27B | 0.841 | 0.893 | 0.712 | 0.979 | 0.754 | 0.964 |
  | ensemble | 0.742 | 0.629 | 0.467 | 0.440 | 0.757 | 0.997 |
  | TF-IDF+LR | 0.835 | 0.889 | 0.703 | 0.979 | 0.880 | 0.554 |
  | TF-IDF+SVM | 0.859 | 0.721 | 0.583 | 0.491 | 0.984 | 0.853 |
  | DistilBERT | 0.843 | 0.771 | 0.624 | 0.650 | 0.946 | 0.728 |

T2, sensitivity by condition, zero-shot (and the control specificity on the 210 paraphrased legitimate e-mails):

  | model | original | para_low | para_high | obf_low | obf_high | spec para_high_ctrl |
  |---|---|---|---|---|---|---|
  | Llama-3.1-8B | 0.222 | 0.365 | 0.449 | 0.913 | 1.000 | 0.638 |
  | Mistral-7B | 0.596 | 0.731 | 0.815 | 0.814 | 0.898 | 0.390 |
  | Gemma-2-9B | 0.925 | 0.964 | 0.972 | 1.000 | 1.000 | 0.462 |
  | Qwen2.5-7B | 0.251 | 0.356 | 0.403 | 0.497 | 0.572 | 0.867 |
  | Qwen2.5-14B | 0.425 | 0.545 | 0.622 | 0.979 | 1.000 | 0.833 |
  | Gemma-2-27B | 0.979 | 0.982 | 0.985 | 1.000 | 1.000 | 0.624 |

T3, family F-RQ4 (30 tests, Holm within the family); delta = rate(original) minus rate(variant), so a negative
delta means the variant is detected more often than its original:

  | model | condition | pairs | delta [95% CI] | b/c | McNemar p | Holm p |
  |---|---|---|---|---|---|---|
  | Llama-3.1-8B | para_low | 334 | -0.144 [-0.189, -0.102] | 8/56 | 5.6e-10 | 1e-08 |
  | Llama-3.1-8B | para_high | 325 | -0.222 [-0.274, -0.169] | 11/83 | 8e-15 | 1.7e-13 |
  | Llama-3.1-8B | obf_low | 334 | -0.692 [-0.737, -0.641] | 0/231 | 5.8e-70 | 1.7e-68 |
  | Llama-3.1-8B | obf_high | 334 | -0.778 [-0.823, -0.731] | 0/260 | 1.1e-78 | 3.2e-77 |
  | Llama-3.1-8B | para_high_ctrl | 210 | +0.171 [+0.119, +0.219] | 38/2 | 1.5e-09 | 2.2e-08 |
  | Mistral-7B | para_low | 334 | -0.135 [-0.177, -0.093] | 6/51 | 5.7e-10 | 1e-08 |
  | Mistral-7B | para_high | 325 | -0.212 [-0.262, -0.166] | 3/72 | 3.7e-18 | 8.2e-17 |
  | Mistral-7B | obf_low | 334 | -0.219 [-0.263, -0.174] | 1/74 | 4e-21 | 9.3e-20 |
  | Mistral-7B | obf_high | 334 | -0.302 [-0.350, -0.254] | 0/101 | 7.9e-31 | 2e-29 |
  | Mistral-7B | para_high_ctrl | 210 | +0.190 [+0.133, +0.252] | 45/5 | 4.2e-09 | 5.9e-08 |
  | Gemma-2-9B | para_low | 334 | -0.039 [-0.063, -0.018] | 1/14 | 0.00098 | 0.0049 |
  | Gemma-2-9B | para_high | 325 | -0.046 [-0.071, -0.025] | 1/16 | 0.00027 | 0.0016 |
  | Gemma-2-9B | obf_low | 334 | -0.075 [-0.105, -0.048] | 0/25 | 6e-08 | 7.2e-07 |
  | Gemma-2-9B | obf_high | 334 | -0.075 [-0.102, -0.048] | 0/25 | 6e-08 | 7.2e-07 |
  | Gemma-2-9B | para_high_ctrl | 210 | +0.238 [+0.176, +0.300] | 52/2 | 1.6e-13 | 3.3e-12 |
  | Qwen2.5-7B | para_low | 334 | -0.105 [-0.147, -0.060] | 11/46 | 3.3e-06 | 2.6e-05 |
  | Qwen2.5-7B | para_high | 325 | -0.145 [-0.194, -0.095] | 12/59 | 1.3e-08 | 1.8e-07 |
  | Qwen2.5-7B | obf_low | 334 | -0.246 [-0.290, -0.201] | 0/82 | 4.1e-25 | 9.9e-24 |
  | Qwen2.5-7B | obf_high | 334 | -0.320 [-0.371, -0.269] | 1/108 | 3.4e-31 | 8.8e-30 |
  | Qwen2.5-7B | para_high_ctrl | 210 | +0.076 [+0.043, +0.114] | 16/0 | 3.1e-05 | 0.00021 |
  | Qwen2.5-14B | para_low | 334 | -0.120 [-0.165, -0.072] | 13/53 | 7.2e-07 | 6.5e-06 |
  | Qwen2.5-14B | para_high | 325 | -0.191 [-0.237, -0.142] | 8/70 | 1.7e-13 | 3.3e-12 |
  | Qwen2.5-14B | obf_low | 334 | -0.554 [-0.605, -0.500] | 0/185 | 4.1e-56 | 1.1e-54 |
  | Qwen2.5-14B | obf_high | 334 | -0.575 [-0.629, -0.524] | 0/192 | 3.2e-58 | 8.9e-57 |
  | Qwen2.5-14B | para_high_ctrl | 210 | +0.110 [+0.071, +0.152] | 23/0 | 2.4e-07 | 2.4e-06 |
  | Gemma-2-27B | para_low | 334 | -0.003 [-0.009, +0.000] | 0/1 | 1 | 1 |
  | Gemma-2-27B | para_high | 325 | -0.006 [-0.018, +0.006] | 1/3 | 0.62 | 1 |
  | Gemma-2-27B | obf_low | 334 | -0.021 [-0.036, -0.009] | 0/7 | 0.016 | 0.062 |
  | Gemma-2-27B | obf_high | 334 | -0.021 [-0.039, -0.009] | 0/7 | 0.016 | 0.062 |
  | Gemma-2-27B | para_high_ctrl | 210 | +0.167 [+0.114, +0.219] | 36/1 | 5.5e-10 | 1e-08 |

  26 of 30 tests have Holm p < 0.05. All 24 phishing deltas are at or below zero (24 negative, range -0.778 to
  -0.003); all 6 control deltas are positive (+0.076 to +0.238): paraphrasing legitimate mail costs
  specificity in every model.

T5, F-RQ2 size contrasts (difference = delta(larger) minus delta(smaller); 6 of 8 Holm p < 0.05):

  | contrast | condition | delta smaller | delta larger | difference [95% CI] | bootstrap p | Holm p |
  |---|---|---|---|---|---|---|
  | qwen25-14b vs qwen25-7b | para_low | -0.105 | -0.120 | -0.015 [-0.069, +0.042] | 0.653 | 0.653 |
  | qwen25-14b vs qwen25-7b | para_high | -0.145 | -0.191 | -0.046 [-0.111, +0.015] | 0.16 | 0.32 |
  | qwen25-14b vs qwen25-7b | obf_low | -0.246 | -0.554 | -0.308 [-0.377, -0.239] | 0.0005 | 0.004 |
  | qwen25-14b vs qwen25-7b | obf_high | -0.320 | -0.575 | -0.254 [-0.329, -0.180] | 0.0005 | 0.004 |
  | gemma2-27b vs gemma2-9b | para_low | -0.039 | -0.003 | +0.036 [+0.015, +0.060] | 0.001 | 0.004 |
  | gemma2-27b vs gemma2-9b | para_high | -0.046 | -0.006 | +0.040 [+0.012, +0.068] | 0.011 | 0.033 |
  | gemma2-27b vs gemma2-9b | obf_low | -0.075 | -0.021 | +0.054 [+0.033, +0.081] | 0.0005 | 0.004 |
  | gemma2-27b vs gemma2-9b | obf_high | -0.075 | -0.021 | +0.054 [+0.033, +0.078] | 0.0005 | 0.004 |

T6, F-RQ3 strategy contrasts (difference = delta(strategy) minus delta(zero-shot)); 13 of 36 have Holm p < 0.05:

  | model | contrast | condition | delta zero-shot | delta strategy | difference [95% CI] | Holm p |
  |---|---|---|---|---|---|---|
  | Llama-3.1-8B | few_shot vs zero_shot | para_high | -0.222 | -0.003 | +0.218 [+0.163, +0.271] | 0.018 |
  | Llama-3.1-8B | few_shot vs zero_shot | obf_high | -0.778 | -0.003 | +0.775 [+0.731, +0.817] | 0.018 |
  | Llama-3.1-8B | role vs zero_shot | obf_high | -0.778 | -0.530 | +0.249 [+0.204, +0.293] | 0.018 |
  | Gemma-2-9B | few_shot vs zero_shot | para_high | -0.046 | -0.175 | -0.129 [-0.172, -0.086] | 0.018 |
  | Gemma-2-9B | few_shot vs zero_shot | obf_high | -0.075 | -0.246 | -0.171 [-0.213, -0.132] | 0.018 |
  | Gemma-2-9B | cot vs zero_shot | obf_high | -0.075 | -0.174 | -0.099 [-0.132, -0.069] | 0.018 |
  | Gemma-2-9B | role vs zero_shot | obf_high | -0.075 | -0.036 | +0.039 [+0.018, +0.060] | 0.018 |
  | Qwen2.5-7B | cot vs zero_shot | para_high | -0.145 | -0.018 | +0.126 [+0.046, +0.197] | 0.025 |
  | Qwen2.5-14B | few_shot vs zero_shot | obf_high | -0.575 | -0.329 | +0.246 [+0.198, +0.296] | 0.018 |
  | Qwen2.5-14B | cot vs zero_shot | obf_high | -0.575 | -0.243 | +0.332 [+0.278, +0.386] | 0.018 |
  | Qwen2.5-14B | role vs zero_shot | obf_high | -0.575 | -0.527 | +0.048 [+0.018, +0.081] | 0.025 |
  | Gemma-2-27B | few_shot vs zero_shot | obf_high | -0.021 | +0.000 | +0.021 [+0.006, +0.039] | 0.018 |
  | Gemma-2-27B | cot vs zero_shot | obf_high | -0.021 | -0.099 | -0.078 [-0.105, -0.048] | 0.018 |

  Few-shot Llama-3.1-8B reaches sensitivity 0.997 with specificity 0.549 on core legitimate and 0.728 on modern
  legitimate mail: its "robustness" under few-shot is a collapse to the phishing label, not detection. Best
  strategy per model by balanced accuracy on core originals: Llama-3.1-8B few_shot, Mistral-7B cot, Gemma-2-9B zero_shot, Qwen2.5-7B cot, Qwen2.5-14B cot, Gemma-2-27B zero_shot.

T8, generalisation set (E-PhishLLM, 1,000 + 1,000; zero-shot / supervised), reported apart from the core set:

  | detector | gen sens | gen spec |
  |---|---|---|
  | Llama-3.1-8B | 0.646 | 0.998 |
  | Mistral-7B | 0.767 | 0.995 |
  | Gemma-2-9B | 0.887 | 0.976 |
  | Qwen2.5-7B | 0.558 | 1.000 |
  | Qwen2.5-14B | 0.663 | 0.999 |
  | Gemma-2-27B | 0.960 | 0.954 |
  | TF-IDF+LR | 0.660 | 0.587 |
  | TF-IDF+SVM | 0.434 | 0.829 |
  | DistilBERT | 0.465 | 0.701 |

T9, ensemble (majority of six, invalid = abstention; tie or < 4 valid votes = invalid):

  | strategy | unanimous items | ensemble invalid | sens original | spec core |
  |---|---|---|---|---|
  | cot | 2939 | 253 (4.9%) | 0.704 | 0.835 |
  | few_shot | 2156 | 317 (6.1%) | 0.734 | 0.750 |
  | role | 3058 | 428 (8.2%) | 0.578 | 0.615 |
  | zero_shot | 2952 | 416 (8.0%) | 0.440 | 0.757 |

T10, cue analysis (CoT rationales, six models pooled, share of non-empty rationales asserting the cue, %;
qwen25-7b wrote no rationale for 908 of its 5,207 outputs, the other models for none or almost none):

  | category | phish original | para_high | obf_high | legit core | legit para ctrl | gen phish |
  |---|---|---|---|---|---|---|
  | urgency | 29.5 | 35.1 | 43.3 | 5.1 | 5.5 | 58.2 |
  | link_url | 80.9 | 88.4 | 89.0 | 22.3 | 24.6 | 53.7 |
  | sender_mismatch | 3.1 | 3.3 | 3.9 | 8.4 | 9.8 | 6.6 |
  | credential_payment | 10.9 | 13.4 | 13.5 | 14.9 | 16.5 | 49.4 |
  | grammar_spelling | 0.1 | 1.4 | 87.6 | 1.9 | 5.6 | 0.2 |
  | impersonation_authority | 21.2 | 17.8 | 12.1 | 5.1 | 5.8 | 20.2 |
  | attachment | 3.2 | 5.6 | 4.6 | 6.5 | 8.4 | 25.2 |
  | generic_greeting | 9.5 | 12.8 | 25.1 | 1.4 | 2.2 | 15.3 |

  Cue change by outcome (pairs with a rationale on both sides; excluded for an empty rationale: 260 of
  9222): para_high 1166 stayed correct, 86 flipped to incorrect, 385 stayed incorrect,
  297 flipped to correct; obf_high 1237 / 13 / 84 / 605. Under obfuscation the grammar/spelling
  cue is asserted in 87.6% of rationales against 0.1% on the originals, and it is gained in the
  flipped-to-correct pairs; under paraphrase the pairs that flipped to incorrect lost the link/URL cue most often
  (figure F6, table T10).

T11, hard core (zero-shot, six models): 102 items missed by all six, 2850 by none, 2255 by some.
All-six failures by group: {'gen_phish': 39, 'legit_core_neg': 34, 'legit_ctrl_para': 14, 'phish_original': 7, 'phish_para_low': 5, 'phish_para_high': 3}. Only 8 lie in the pre-registered strata, so
reports/hardcore_sample.csv has 8 rows (QUESTIONS.md item 17; coding guide docs/HARDCORE_CODING_GUIDE.md).

**Reading for the research questions (three sentences each, Section 4.7).**

- RQ4 (robustness, the headline): the pre-registered expectation of a sensitivity loss under paraphrase and
  obfuscation is not what the data show; every zero-shot phishing delta is at or below zero, and 26 of the 30
  F-RQ4 tests are significant after Holm, almost all in the direction of the variant being easier to detect
  (Llama-3.1-8B 0.22 on originals against 1.00 under high obfuscation; Qwen2.5-14B 0.43 against
  1.00). The two Gemma models are the only detectors near the ceiling on the originals (0.93 and
  0.98) and show the smallest deltas. The control delta is positive for every model (+0.08 to +0.24
  specificity lost on paraphrased legitimate mail), so the paraphraser itself reads as a phishing signal.
- RQ2 (comparison): capability on the originals splits the field, Gemma-2-27B (balanced accuracy 0.89, F1 0.71)
  and Gemma-2-9B (0.83) against Llama-3.1-8B (0.53) and Qwen2.5-7B (0.59), which miss most spear-phishing
  originals. The TF-IDF + logistic-regression baseline trained on traditional phishing matches the best model on
  sensitivity (0.98) but pays on modern legitimate mail (specificity 0.55); DistilBERT sits in the middle
  (balanced accuracy 0.77). Size helps within a family (6 of 8 size contrasts significant), but family matters more
  than size: Gemma-2-9B beats Qwen2.5-14B on every phishing condition.
- RQ3 (prompting): 13 of 36 strategy contrasts are significant after Holm, but the direction and size depend on the
  model: chain-of-thought lifts the weak zero-shot models (Qwen2.5-7B sensitivity 0.25 to 0.64 on originals, Qwen2.5-14B
  0.43 to 0.76) and costs Gemma-2-27B (0.98 to 0.90). Few-shot turns Llama-3.1-8B into a constant
  phishing label (sensitivity 1.00, specificity 0.55), which the contrasts read as perfect robustness; the
  balanced-accuracy column of T1/T4 is the safeguard against that reading. No strategy is best for every model.
- RQ1 (effectiveness): as direct zero-shot detectors of AI-generated spear-phishing, the six open models range
  from balanced accuracy 0.53 to 0.89 on the core originals, with invalid-output rates below 0.2% in
  every cell. On the E-PhishLLM generalisation set the ranking holds (Gemma-2-27B sensitivity 0.96, specificity
  0.95; Llama-3.1-8B 0.65 / 1.00). The majority ensemble does not beat its best member (sensitivity
  0.44 on originals, 8.0% invalid from ties and abstentions).

**Wording for Section 4.3 (statistics; replaces the draft of 2026-11-01):** "Every rate is reported with a 95%
percentile cluster-bootstrap confidence interval (B = 2,000, seed 2026, one random stream per table derived from
the table name), clusters being the source e-mails so that an original and its variants are resampled together.
The primary outcome for RQ4 is the paired change in sensitivity, rate(original) minus rate(variant), on the
originals that have an accepted variant in that condition, tested with the exact McNemar test on the discordant
pairs; the control outcome is the paired change in specificity on the 210 legitimate e-mails with an accepted
paraphrase. The headline family F-RQ4 holds the 30 zero-shot tests (24 phishing, 6 control); the size contrasts
(F-RQ2, 8) and the strategy contrasts (F-RQ3, 36) are differences of paired deltas tested by the same cluster
bootstrap with a two-sided percentile p floored at 1/B; Holm's correction is applied within each family and the
uncorrected p is shown as well. Invalid outputs count as incorrect; a sensitivity analysis drops the invalid items
and, for paired tests, the pairs with an invalid member (Appendix Table A1). An a priori power note: with 334
pairs, 10% discordance and a five-point paired drop, the exact McNemar test has power 0.80 at alpha 0.05; the
observed discordance of the zero-shot tests (median 0.19) is reported as a post hoc descriptive check."

**Wording for Section 4.5 (results, opening paragraph):** "Table T2 and Figure F1 carry the main result. Under the
zero-shot prompt the six models detect between 22% and 98% of the 334 AI-generated spear-phishing
originals, and none of them detects fewer of the paraphrased or obfuscated variants than of the originals: all
24 paired deltas are at or below zero and 26 of the 30 pre-registered tests are significant after Holm's
correction. Obfuscation is the clearest case, with four models at a sensitivity of 1.00 on the high-intensity
variants; the chain-of-thought rationales show why, as the grammar-and-spelling cue is asserted in 87.6% of them
against 0.1% for the originals (Table T10). The control condition shows the other face of the same effect:
paraphrased legitimate e-mails lose between 8 and 24 points of specificity in every model."

## Step 07: hard-core sample, pre-registered 8 plus post hoc 30 (item 17; 2026-11-01)

**What changed.** QUESTIONS.md item 17 is closed. The pre-registered hard-core sample (item 12c, refinement 4: all
six language models wrong under zero_shot, strata = the four phishing variant conditions) stays as computed with
its 8 eligible items (para_low 5, para_high 3, obf_low 0, obf_high 0) and is reported as such. A post hoc
extension for the qualitative coding only, logged in item 12 as a deviation with the reason "only 8 items met
the pre-registered criterion", adds 30 phishing items (originals and variants) misclassified by at least 4 of
the 6 models under zero_shot, five strata (original plus the four conditions), the pre-registered items
excluded, proportional allocation with a minimum of 5 per stratum where available, seed 2026. No computed metric
changes; the hard-core tables (T11, hardcore_items.csv, hardcore_summary.csv) are byte-identical.

**Counts before sampling (phishing originals and variants, zero_shot, missed by at least 4 of 6):**

| stratum | items | missed by at least 4 of 6 | of which by all six | eligible for the post hoc draw | drawn |
|---|---|---|---|---|---|
| original | 334 | 119 | 7 | 119 | 16 |
| para_low | 334 | 70 | 5 | 65 | 8 |
| para_high | 325 | 47 | 3 | 44 | 6 |
| obf_low | 334 | 3 | 0 | 3 | 0 |
| obf_high | 334 | 0 | 0 | 0 | 0 |
| total | 1,661 | 239 | 15 | 231 | 30 |

The 7 originals missed by all six stay in the post hoc pool because the pre-registered strata are the variant
conditions only; the 8 pre-registered variants are removed from it.

The three obf_low items get no slot under the allocation rule (fewer than the minimum of 5 available, and a
proportional share of 0.39 rounds to zero); the rule was applied as written, not adjusted after seeing the
counts. The eight all-six failures among the phishing variants are the pre-registered rows (sample_id 1 to 8,
`set` = preregistered); the 30 post hoc rows follow (sample_id 9 to 38, `set` = posthoc). Both are in
reports/hardcore_sample.csv with the empty coding columns failure_type and note; the texts (subject, scored body,
original body) are in data/processed/hardcore_sample_text.jsonl (data, not in git). The coding guide
(docs/HARDCORE_CODING_GUIDE.md) now asks, for an original, "why does this spear-phishing e-mail look
legitimate?" and, for a variant, "what changed relative to the original?", with one code list per question.

**Wording for Section 4.5 (hard core, replaces "has 8 rows" above):** "Under the zero-shot prompt 102 of the
5,207 items are misclassified by all six models, but only 8 of them are phishing variants (5 low and 3 high
paraphrase, none obfuscated), so the pre-registered 30-item sample could not be filled; the 8 items are coded
as the pre-registered sample. Because near-unanimous misses on variants are rare, a post hoc extension, declared
as such, codes 30 further phishing e-mails that at least four of the six models missed (16 originals, 8 low and
6 high paraphrases; the 3 obfuscated candidates received no slot under the pre-specified allocation rule). The
extension is descriptive and informs no test."

**Wording for Section 4.8 (threats to validity):** "The qualitative hard-core sample departs from the
pre-registration in one respect: the criterion of all six models failing yielded 8 phishing variants rather
than 30, so a post hoc extension with a looser criterion (at least four of six) was added after the quantitative
results were fixed. It is labelled as post hoc throughout and no quantitative claim rests on it."

