# Hard-core sample: coding guide (TASK_07 section 4c, QUESTIONS.md item 12c)

**What the sample is.** Under the zero-shot prompt, an item is a "hard-core failure" when all six language
models misclassify it (an invalid output counts as a misclassification; baselines are not consulted).
`reports/hardcore_sample.csv` holds a seeded (2026) stratified random sample of 30 such failures among the
phishing variants, strata = the four phishing conditions (para_low, para_high, obf_low, obf_high), allocation
proportional to the number of failures per condition with a minimum of 5 per condition where available. The
allocation actually used is in `reports/secondary_report.json` (`hardcore.sample_allocation`). The texts are
in `data/processed/hardcore_sample_text.jsonl` (subject, the scored body, and the original body; data, not in
git). The analysis is descriptive: it produces a taxonomy of what the detectors miss, not a metric.

**How to code.** Read the subject and the scored body of each sampled item (and the original body for
context), then fill two columns of `reports/hardcore_sample.csv`:

- `failure_type`: exactly one code from the list below (the dominant reason, in your judgement, why a
  reader would also hesitate to call this e-mail phishing). Use `other` only with a note.
- `note`: one sentence of evidence from the text (quote a phrase), no personal data.

Do not change any other column. Do not look up the models' rationales or the scores while coding; the
`pred_<model>` columns show only that every model answered "legitimate" or produced an invalid output.

**Codes for `failure_type`.**

| code | use when |
|---|---|
| `plausible_business` | the message reads as routine work e-mail: a specific, reasonable request between colleagues or partners, with context that fits (project, meeting, document review) and no explicit lure |
| `no_call_to_action` | there is no request to click, open, pay, log in or reply with information; the phishing intent is implicit or deferred |
| `benign_request` | the request exists but is low-stakes and ordinary (review a document, confirm a meeting, send a file) and carries no credential, payment or link cue |
| `personalised_pretext` | the spear-phishing personalisation itself makes it convincing: correct names, roles, shared history or company detail |
| `placeholder_artifact` | the neutralised link or placeholder token (for example `<<link>>` or a bare "the link below") removes the cue a reader would otherwise notice |
| `paraphrase_softened` | (para_* only) the paraphrase removed or weakened the urgency, threat or request wording that the original had |
| `obfuscation_unnoticed` | (obf_* only) the character-level changes are too sparse or too subtle to be read as suspicious |
| `truncated_or_short` | the body is too short or cut to carry a cue |
| `label_noise` | you doubt that the item is phishing at all (record why) |
| `other` | anything else; the note is mandatory |

**Reporting.** Chapter 4 reports the code frequencies per condition (counts of 30) and two or three
anonymised quoted phrases per frequent code, with the statement that the coding was done by one author
after the quantitative results were fixed. The sample size is 30, so the frequencies are indicative only.
