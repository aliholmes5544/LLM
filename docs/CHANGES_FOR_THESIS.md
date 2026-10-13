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
