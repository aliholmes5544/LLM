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
