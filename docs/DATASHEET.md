# Datasheet: the SpearShift variant dataset

Datasheet in the format of Gebru et al. (2021), "Datasheets for Datasets", for the evaluation dataset of
SpearShift, the reproducible evaluation framework of the Master's thesis *LLM vs. LLM: Evaluating the
Effectiveness of Open-Source Language Models in Detecting AI-Generated Spear-Phishing Emails* (Bakhit Ali
Mashan, 2026). Every number below is read from a file under `reports/` or `configs/` of this repository; the
file is named in brackets. Dates are the dates recorded in those reports. Written 2026-11-01 at tag
v1.0.0-thesis.

## 1. Motivation

**For what purpose was the dataset created?** To measure how well open-weight language models, prompted as
direct detectors, classify AI-generated spear-phishing e-mail, and how far that performance holds when the
e-mails are paraphrased or obfuscated (research questions RQ1 to RQ4 of the thesis). No public dataset combined
LLM-generated spear-phishing with controlled paraphrased and obfuscated rewritings of the same messages, so the
rewritings were derived here from published records by defined transformations. No phishing text was generated
for this study (CLAUDE.md, hard rule "No generation of phishing content").

**Who created the dataset and on behalf of whom?** The thesis author, as part of a Master's thesis in cyber
defence; no funding body. The derivation code was implemented with an AI coding assistant under the author's
specifications (docs/REPRODUCE.md, "AI assistance").

**Who funded the creation?** No external funding. Compute: the author's laptop (CPU) for derivation and the
author's Colab Pro subscription for detector inference (86.9 compute units in total, about USD 8.70,
reports/detection_run_report.json and docs/CHANGES_FOR_THESIS.md).

## 2. Composition

**What do the instances represent?** E-mails, each reduced to a subject line and a body text. There are two
kinds of instance: *originals*, taken from published corpora after normalisation, and *variants*, derived from
an original by one of four transformations. Detectors see subject and body only; sender, headers, URLs and
attachments are never part of an instance (hard rule "Text only").

**How many instances are there?** The processed record file holds 16,408 originals after cleaning and
duplicate removal (spear_llm 334, traditional 2,654, enron_ham 1,610, hard_ham 308, ephish_phish 5,996,
ephish_legit 5,506; reports/preprocess_report.json). The evaluation set that every detector sees has 5,207
items (reports/items_build_report.json):

| item group | partition | condition | n | label |
|---|---|---|---|---|
| spear-phishing originals | core_pos | original | 334 | phish |
| paraphrased, low | core_pos | para_low | 334 | phish |
| paraphrased, high | core_pos | para_high | 325 | phish |
| obfuscated, low | core_pos | obf_low | 334 | phish |
| obfuscated, high | core_pos | obf_high | 334 | phish |
| legitimate, core | core_neg | original | 1,002 | legit |
| legitimate, modern (E-PhishLLM) | ctrl_modern_legit | original | 334 | legit |
| legitimate, paraphrased control | ctrl_para_legit | para_high | 210 | legit |
| generalisation phishing (E-PhishLLM) | gen_phish | original | 1,000 | phish |
| generalisation legitimate (E-PhishLLM) | gen_legit | original | 1,000 | legit |

Outside the evaluation set: dev 400 (100 traditional phishing, 100 Enron ham, 100 E-PhishLLM personalised
phishing, 100 E-PhishLLM legitimate) with 396 accepted dev variants derived from the 100 E-PhishLLM phishing
items (para_low 100, para_high 96, obf_low 100, obf_high 100); train 3,033 (traditional 2,299, enron_ham 734);
valid 337; the few-shot pool equals train (reports/partition_report.json, reports/variants_dev_report.json).

**What does each instance consist of?** An original record has `id, source, subclass, class, subject, body,
n_words, salutation, truncated` (data/processed/records.jsonl). A variant record has `variant_id` (the source
id plus `#condition`), `source_id, condition, subject, body, status` (pass, regenerated, excluded) and a
`checks` object with every meaning-check score (cosine similarity, length ratio, protected spans found,
per-sentence NLI entailment, attempts, reverted sentences, achieved fraction, failed tests). Obfuscation
variants carry an exact edit log (position, original character, replacement, operation) in
data/processed/obfuscation_log_eval.jsonl, from which the variant is replayed and verified.

**Is there a label?** Yes: `class` is phish or legit, inherited from the source corpus; a variant inherits the
label of its source record. E-PhishLLM phishing also carries a salutation class (named 599, generic 330, none 71
in gen_phish) as a proxy for how targeted the message is.

**Is any information missing?** The subject is missing in 1 hard_ham and 39 traditional phishing source files
(reports/audit_raw.json); bodies longer than 600 words were truncated at a sentence boundary (traditional 455,
enron_ham 195, hard_ham 96) and flagged `truncated`. Nothing else is missing by design: HTML was stripped and
E-PhishLLM placeholder tokens were replaced (section 4).

**Are relationships between instances made explicit?** Yes. A variant points to its source by `source_id`;
all instances of one source e-mail form a *cluster*, which the statistics resample together
(results/scores/pairs.csv lists every original-to-variant pair: 334 + 325 + 334 + 334 phishing pairs and 210
control pairs).

**Are there recommended data splits?** Yes, and they are fixed (seed 2026, reports/partition_report.json):
the evaluation groups above; dev for any development; train and valid for the supervised baselines. No
evaluation item has a near-duplicate (word-trigram Jaccard at or above 0.80) in train, valid, dev or the few-shot
pool (step 04 leakage check, no leakage found).

**Are there errors, noise or redundancies?** Known residual error of the meaning checks, estimated on the
development set by three human raters: 2 of 36 accepted paraphrases judged not meaning-preserving (5.6%,
Wilson 95% interval 1.5 to 18.1%), 0 of 20 obfuscations, 2 of 56 overall (3.6%, 1.0 to 12.1%)
(reports/ratings_merge_dev.json, reports/variants_calibration.json). Duplicates were removed before
partitioning (section 4). The core spear-phishing collection is homogeneous (section 7).

**Is the dataset self-contained?** No. Originals are not redistributed; they are re-created by
`scripts/01_download_data.py` to `04_partition.py` from the pinned upstream commits. The derived variants and
the paraphrase cache are the fixed artefacts of the study and are archived with their hashes (section 6).

**Does the dataset contain confidential data or data that might be offensive?** The spear-phishing e-mails
are machine-generated and set in a fictional company with fictional personas; E-PhishLLM is synthetic. The
Enron e-mails are real messages of former Enron employees, public since 2003 through the Federal Energy
Regulatory Commission and widely redistributed for research; the SpamAssassin "hard ham" messages are real
legitimate e-mails collected for the public SpamAssassin corpus. No instance was annotated with personal
attributes, and no attempt was made to identify any person.

**Does the dataset relate to people?** Only indirectly, through the Enron and SpamAssassin legitimate mail
described above. Names in the spear-phishing collection are fictional.

## 3. Collection process

**How was the data acquired?** Downloaded by `scripts/01_download_data.py` from two public GitHub
repositories at pinned commits, with the archive hashes recorded (data/raw/provenance.json,
reports/audit_raw.json):

| source | repository and commit | content used | licence as published |
|---|---|---|---|
| Nahmias et al. (2024) | `nahmiasd/Prompted-Contextual-Vectors-for-Spear-Phishing-Detection`, commit `1c5ecbdd`, zip sha256 `4804c493...` | spear_phishing 334 (LLM-generated, HTML bodies), traditional_phishing 3,332, enron_ham 3,000, hard_ham 490 (1 unparseable) | CC BY-NC-SA 4.0 |
| E-PhishLLM, Pajola et al. (2025) | `pajola/e-phishGen`, commit `3ff53fb2`, zip sha256 `edc5c585...`, file `ephishLLM.json` | English part: 5,996 phishing, 5,506 legitimate of 16,616 messages in ten languages | no licence file ("unspecified"); not redistributed |

The Enron corpus (Klimt and Yang, 2004) and the SpamAssassin hard ham were taken as redistributed inside the
Nahmias et al. repository, so that the legitimate class is the one the most closely related study used.

**Who was involved and how were they compensated?** Only the author (download, code) and three volunteer
raters for the meaning-check calibration (section 4), not compensated.

**Over what time frame was the data collected?** Downloads on 2026-10-11; variants derived on the development
set 2026-10-12 to 2026-10-25 and on the evaluation set 2026-10-26 (re-derived from the cache 2026-10-27 after the
"unchanged" rule); detector outputs 2026-10-28 to 2026-11-01. The upstream e-mails date from the Enron era
(1999 to 2002), the SpamAssassin corpus (2002 to 2003) and the two generation studies (2024 and 2025).

**Were any ethical review processes conducted?** No institutional review was required: the study uses
published datasets, generates no phishing content and contacts no person. The threat model and the ethical
considerations are in the thesis (Sections 1.2.1 and 3.9 of the original chapter plan).

## 4. Preprocessing, cleaning and labelling

**What preprocessing was done?** `scripts/03_preprocess.py` with the settings of configs/data.yaml
(reports/preprocess_report.json):

- one schema for all collections; language English (E-PhishLLM filtered to `Language = en`);
- HTML stripped identically in every collection (all 334 spear-phishing bodies and 14 Enron, 36 hard ham and
  1 traditional body were HTML in the source);
- E-PhishLLM placeholder tokens neutralised: `<<link>>` became "the link", `<<attachment>>` "the attachment",
  `<<email>>` "the address", any other token "the link" (3,673 replacements). Reason: the tokens appeared in
  60.2% of the English phishing and in 0% of the legitimate messages, a class leak;
- bodies shorter than 5 words dropped (traditional 2, enron_ham 78, hard_ham 3); bodies longer than 600 words
  truncated at a sentence boundary and flagged;
- exact duplicate bodies removed (hard_ham 138, enron_ham 1,188, traditional 103), then near-duplicates by
  MinHash (128 permutations) and word-trigram Jaccard at or above 0.80, verified pairwise (1,653 pairs;
  removed hard_ham 40, enron_ham 124, traditional 573), across all collections together. No cross-collection
  near-duplicate was found.

**How were the variants derived?** `scripts/05_derive_variants.py` with configs/variants.yaml
(reports/variants_eval_report.json). Four conditions:

| condition | family | rate | operation |
|---|---|---|---|
| para_low | paraphrase | 0.5 of eligible sentences | each selected sentence rewritten by Phi-3.5-mini-instruct (GGUF Q4_K_M, llama.cpp 0.3.36, temperature 0.7, top_p 0.9, prompt `prompts/paraphrase_v1.txt`) |
| para_high | paraphrase | 1.0 of eligible sentences | same |
| obf_low | obfuscation | 0.1 of eligible tokens (4 characters or longer) | per token one operation: Cyrillic homoglyph (a e o c p x i), digit substitution (o→0 l→1 e→3 a→4 s→5), separator insertion (- or .), zero-width space |
| obf_high | obfuscation | 0.3 of eligible tokens | same |

A segment is eligible for rewriting only if it reads as a sentence (at least 3 alphabetic words outside
protected spans and either sentence punctuation or at least 8 words); greeting lines, titles, signatures and
link labels are copied verbatim. Protected spans (names, organisations, dates, times, money and numbers found
by spaCy `en_core_web_sm`, plus the placeholder phrases) must survive every rewrite. Every random choice
derives from seed 2026 through a per-record stream, so adding or reordering records cannot change another
record's variant.

**Filtering rules for paraphrases (frozen 2026-10-25).** A paraphrased body is accepted when (i) the cosine
similarity between the original and the variant body (sentence-transformers `all-mpnet-base-v2`) is at least
`thr_cos = 0.68`; (ii) every rewritten sentence is entailed by its original with probability at least
`thr_nli = 0.70` (cross-encoder `nli-deberta-v3-base`), a sentence that fails being retried once with a
different sampler seed and otherwise reverted to the original; (iii) the retained rewrites cover at least 0.4
(para_low) or 0.8 (para_high) of the selected sentences; (iv) the length ratio lies in 0.70 to 1.40 and all
protected spans are present; (v) the variant text differs from the original (the "unchanged" rule, applied
2026-10-27 in every condition; QUESTIONS.md item 7). A whole body that fails is regenerated once; a second
failure excludes the record from that condition (status `excluded`, reasons logged). Obfuscation variants are
verified by replaying the edit log (integrity 100%).

**Calibration by three raters (development set only).** The cosine threshold was calibrated on a stratified
development sample rated for meaning preservation by three volunteer raters (60 rows: 57 plus 3 whose accepted
text changed; majority label; no split row). Pairwise agreement 86.7%, 95.0% and 91.7% (prevalence-adjusted
kappa 0.73, 0.90, 0.83; Fleiss' kappa 0.16 under 55 of 60 preserved). `thr_cos = 0.68` is the highest grid
value at which at least 95% of the paraphrases labelled preserved by the majority pass (97.1%); the NLI
threshold could not be calibrated because the sentence fallback reverts every sentence below 0.70 before any
score is recorded, so it stays at its pre-specified value (reports/variants_calibration.json). Readability of
20 obfuscated items: all were judged readable by the majority, and the obfuscation is noticeable to a careful
reader (reports/readability_dev.xlsx). The evaluation items were never rated or inspected by hand (hard rule
"Evaluation items are read-only").

**Resulting counts on the evaluation set** (reports/variants_eval_report.json): core_pos para_low 334 of
334 accepted (219 first attempt, 115 regenerated), para_high 325 of 334 (129 and 196; 9 excluded for the
achieved fraction), obf_low and obf_high 334 each; ctrl_para_legit para_high 210 of 334 accepted (60 and 150;
124 excluded: 113 for the achieved fraction, 18 unchanged, 6 cosine, 3 length, with overlaps). The control
exclusions concentrate in short Enron messages (median 88 words; enron_ham 101 of 124), a property of the
data, not of the method (reports/control_exclusion_diagnosis.json, QUESTIONS.md item 7). Development set:
para_low 81 pass, 19 regenerated, 0 excluded; para_high 76, 20, 4 (1 cosine, 3 fraction); obfuscation 100 and
100.

**Was the raw data saved?** Yes, locally (`data/raw/`, not in git) with archive hashes in
data/raw/provenance.json; anyone can re-download the same commits.

**Is the preprocessing software available?** Yes, in this repository (`scripts/01_*.py` to `05_*.py`,
`configs/data.yaml`, `configs/variants.yaml`, `prompts/paraphrase_v1.txt`), pinned versions in
requirements.txt.

## 5. Uses

**Has the dataset been used for any tasks already?** Yes: the thesis evaluation of six open-weight detectors
(Llama-3.1-8B, Mistral-7B-v0.3, gemma-2-9b, Qwen2.5-7B, Qwen2.5-14B, gemma-2-27b; GGUF Q4_K_M) under four
prompting strategies and three supervised baselines (TF-IDF with logistic regression and with a linear SVM,
fine-tuned DistilBERT), scored once under a pre-registered plan (docs/QUESTIONS.md item 12,
results/scores/, results/tables/, figures/).

**What other tasks could it be used for?** Evaluating other detectors under the same conditions (`make
evaluate MODEL=<key>`), studying how paraphrase and character obfuscation change detector cues, and
calibrating meaning-check thresholds for e-mail rewriting. Results on the generalisation set (E-PhishLLM) are
to be reported apart from the core set, because that collection is of mixed specificity (about 61% named
salutation, 32% generic, 7% none) and was produced by a different pipeline.

**Is there anything about the composition that might affect future uses?** Three things. The spear-phishing
core comes from one generator and one fictional organisation (section 7), so a detector developed against it
would learn its personas and topics; this is why no prompt, example or threshold was developed on it here. The
main finding of the thesis is that paraphrase and obfuscation made the phishing e-mails easier to detect for
every model studied, and paraphrase made legitimate e-mails look more suspicious; the variants therefore
represent *rewritten* spear-phishing, not *evasive* rewriting optimised against a detector. The control set of
210 paraphrased legitimate e-mails is skewed towards longer messages by the exclusion rule.

**Are there tasks for which the dataset should not be used?** Yes. It must not be used to train, fine-tune,
prompt or evaluate systems that generate phishing or spear-phishing e-mail, to build or improve evasion
against deployed detectors, to send any of the messages, or to identify, profile or contact the people whose
legitimate e-mails appear in the Enron and SpamAssassin collections. The CC BY-NC-SA 4.0 licence of the
derived variants excludes commercial use.

## 6. Distribution

**Will the dataset be distributed to third parties?** In three parts, according to what each source licence
allows:

| part | content | licence and reading | where |
|---|---|---|---|
| code, configuration, prompts, reports, result tables, figures | this repository | MIT (the author's own work) | GitHub, tag v1.0.0-thesis; Zenodo deposit |
| derived variants and paraphrase cache: `data/processed/variants_eval.jsonl` (1,670 rows, sha256 `d898cece5d0f5d399a036bdeab8d63c9246b4eb91fd8298c299285b354d46389`), `data/interim/paraphrase_cache_eval.jsonl` (8,228 rows, `694cd11b27045dfd6d7256b6f2bfae366e77d6c9d1be6fb02b9e6b0aac6297d7`), `data/processed/obfuscation_log_eval.jsonl` | rewritings of Nahmias et al. (2024) spear-phishing e-mails and of Enron and hard ham e-mails from the same repository | CC BY-NC-SA 4.0: the Nahmias et al. licence permits sharing and adapting with attribution, for non-commercial purposes, under the same licence; the variants are adaptations and are released under the same licence with attribution | Zenodo deposit at submission (reports/variants_eval_fixed_artifacts.json, `archived_at_submission: true`); not in git |
| originals: Nahmias et al. collections, E-PhishLLM, the processed record file, partitions, the development variants (derived from E-PhishLLM) | re-created by `scripts/01_download_data.py` to `05_derive_variants.py` | Nahmias et al.: redistribution would be permitted under CC BY-NC-SA 4.0 but is unnecessary, the pinned commit is public; E-PhishLLM: no licence file, so no redistribution right can be assumed, and nothing derived from it (records, dev variants, the few-shot texts, the hard-core sample texts) is distributed | download script with pinned commits and hashes |

**When and how?** With the thesis submission, as a Zenodo deposit linked to the GitHub tag, with the DOI
entered in CITATION.cff. The Zenodo record will carry the item list of docs/REPRODUCE.md.

**Will the dataset be distributed under a copyright or other licence?** As above: MIT for code, CC BY-NC-SA
4.0 for the derived variants. Users of the derived variants must attribute Nahmias et al. (2024) and this
work, use them non-commercially and release adaptations under the same licence.

**Have any third parties imposed restrictions?** The Nahmias et al. licence (non-commercial, share-alike) and
the absence of an E-PhishLLM licence, as read above. The detector models carry their own licences, recorded
verbatim in configs/models.yaml (Apache-2.0 for Mistral and Qwen; the Llama 3.1 Community License and the
Gemma Terms of Use for the open-weight models); no model weights are distributed.

**Do any export controls or regulatory restrictions apply?** None known.

## 7. Maintenance

**Who maintains the dataset?** The author, through the GitHub repository (issues) until the thesis defence
and for the tagged release afterwards. Contact: the repository issue tracker.

**Is there an erratum?** Errors found after the release will be recorded in docs/CHANGES_FOR_THESIS.md with
their date, and material deviations from the pre-registered plan in docs/QUESTIONS.md, as during the study
(items 7, 8, 13, 17 record the deviations that occurred).

**Will the dataset be updated?** The evaluation set is frozen at tag v1.0.0-thesis so that the thesis results
stay reproducible; any later derivation would be a new version with a new tag and new artefact hashes. New
detector results are added without touching the frozen set (`make evaluate`).

**Are there limits on data retention?** No limit applies to the synthetic and the derived material; the Enron
and SpamAssassin messages are retained as the upstream corpora retain them.

**Will older versions be supported?** Tags stay available in the repository; the Zenodo deposit is permanent.

**How can others extend or contribute?** By adding a detector (one YAML block, `make evaluate`), by proposing
a new condition as a pull request that keeps the evaluation items read-only and the derivation seeded, or by
re-running the calibration with their own raters on the development set.

## 8. Known limitations (summary)

1. **Generator-specific style.** The 334 spear-phishing e-mails come from one automated generator, are set in
   one fictional company with a recurring cast, and centre on security work and conferences; findings are
   about this collection, with E-PhishLLM as a separate check of transfer.
2. **One paraphraser.** All paraphrases come from Phi-3.5-mini-instruct with one prompt; another rewriter
   would produce different cues. The paraphraser's family is excluded from the detector set.
3. **Obfuscation is visible.** The character substitutions are noticeable to a careful reader; the conditions
   test robustness to visible noise, not to imperceptible perturbation.
4. **Variants were easier, not harder, to detect** for every detector studied, so the dataset does not
   represent an adaptive attacker.
5. **Control exclusions.** 37.1% of the legitimate controls could not be paraphrased to the required fraction;
   the 210 remaining skew to longer messages.
6. **Residual meaning error.** About 3.6% of accepted variants (95% interval 1.0 to 12.1%) may not preserve the
   original meaning, estimated on the development set only.
7. **CPU non-reproducibility of generation.** Paraphrase generation is seeded but not bit-reproducible on the
   CPU backend (8 of 179 spot-checked sentences differed by one to three words on regeneration); the released
   variants file and cache are the fixed artefacts, identified by sha256, and everything downstream of them
   is byte-reproducible (reports/variants_eval_fixed_artifacts.json, reports/variants_eval_spot_check.json).

## References

Gebru, T., Morgenstern, J., Vecchione, B., Vaughan, J. W., Wallach, H., Daumé III, H., & Crawford, K. (2021).
Datasheets for datasets. *Communications of the ACM, 64*(12), 86 to 92. https://doi.org/10.1145/3458723

Klimt, B., & Yang, Y. (2004). The Enron corpus: A new dataset for email classification research. In
*Machine Learning: ECML 2004* (pp. 217 to 226). Springer.

Nahmias, D., Engelberg, G., Klein, D., & Shabtai, A. (2024). Prompted contextual vectors for spear-phishing
detection. Repository `nahmiasd/Prompted-Contextual-Vectors-for-Spear-Phishing-Detection`, CC BY-NC-SA 4.0.

Pajola, L., Caripoti, E., Banzer, S., Pizzi, S., Conti, M., & Apruzzese, G. (2025). E-PhishGEN: Unlocking novel
research in phishing email detection. In *Proceedings of the 18th ACM Workshop on Artificial Intelligence and
Security (AISec '25)* (pp. 64 to 76). https://doi.org/10.1145/3733799.3762967
