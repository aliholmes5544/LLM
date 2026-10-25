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
