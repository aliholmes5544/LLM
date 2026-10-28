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
  panel is authoritative. Pay-as-you-go: 100 units = USD 9.99. Sessions are limited in length and can
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
