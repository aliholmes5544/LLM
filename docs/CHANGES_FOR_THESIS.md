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
