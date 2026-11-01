# Hard-core sample: coding guide (TASK_07 section 4c, QUESTIONS.md items 12c and 17)

**What the sample is.** Under the zero-shot prompt, an item is a "hard-core failure" when all six language
models misclassify it (an invalid output counts as a misclassification; baselines are not consulted).
`reports/hardcore_sample.csv` holds two sets, told apart by the column `set`:

- `preregistered` (sample_id 1 to 8): every all-six failure among the phishing variants (the pre-registered
  rule: strata = the four variant conditions, seed 2026, 30 items requested; only 8 existed, para_low 5 and
  para_high 3, QUESTIONS.md item 17).
- `posthoc` (sample_id 9 to 38): a clearly labelled post hoc extension, decided after the scores were computed
  and logged in item 12 as a deviation: phishing e-mails (originals and variants) misclassified by at least 4 of
  the 6 models, five strata (original plus the four variant conditions), the pre-registered items excluded,
  proportional allocation with a minimum of 5 per stratum where at least 5 were available, seed 2026, 30 items
  (original 16, para_low 8, para_high 6, obf_low 0, obf_high 0). The counts per stratum before sampling are in
  `reports/secondary_report.json` (`hardcore.sample`) and in QUESTIONS.md item 17.

The texts are in `data/processed/hardcore_sample_text.jsonl` (subject, the scored body, and the original body;
data, not in git). The analysis is descriptive: it produces a taxonomy of what the detectors miss, not a metric,
and the post hoc set informs no test.

**How to code.** Read the subject and the scored body of each sampled item (for a variant, read the original body
as well), then fill two columns of `reports/hardcore_sample.csv`:

- `failure_type`: exactly one code from the list that matches the row's `condition` (below). Use `other` only
  with a note.
- `note`: one sentence of evidence from the text (quote a phrase), no personal data.

Do not change any other column. Do not look up the models' rationales or the scores while coding; the
`pred_<model>` columns show only which models answered "legitimate" or produced an invalid output (in the post
hoc set up to two models may have answered "phishing"). Code the two sets in the same pass; they are separated
only in the reporting.

**Question for an original (`condition` = original): why does this spear-phishing e-mail look legitimate?**

| code | use when |
|---|---|
| `plausible_business` | the message reads as routine work e-mail: a specific, reasonable request between colleagues or partners, with context that fits (project, meeting, document review) and no explicit lure |
| `no_call_to_action` | there is no request to click, open, pay, log in or reply with information; the phishing intent is implicit or deferred |
| `benign_request` | the request exists but is low-stakes and ordinary (review a document, confirm a meeting, send a file) and carries no credential, payment or link cue |
| `personalised_pretext` | the spear-phishing personalisation itself makes it convincing: correct names, roles, shared history or company detail |
| `placeholder_artifact` | the neutralised link or placeholder token (for example `<<link>>` or a bare "the link below") removes the cue a reader would otherwise notice |
| `truncated_or_short` | the body is too short or cut to carry a cue |
| `label_noise` | you doubt that the item is phishing at all (record why) |
| `other` | anything else; the note is mandatory |

**Question for a variant (`condition` = para_low, para_high, obf_low, obf_high): what changed relative to the
original?** Compare the scored body with the original body and code the change that, in your judgement, best
explains why a reader would hesitate where the original would (or would not) have been caught.

| code | use when |
|---|---|
| `paraphrase_softened` | (para_* only) the paraphrase removed or weakened the urgency, threat or request wording that the original had |
| `paraphrase_cue_dropped` | (para_* only) a concrete cue of the original (link reference, attachment, credential or payment request, sender claim) is absent or reworded beyond recognition in the variant |
| `paraphrase_neutral` | (para_* only) the paraphrase preserved the cues; the variant looks legitimate for the same reason as the original (give that reason in the note using a code from the original list) |
| `obfuscation_unnoticed` | (obf_* only) the character-level changes are too sparse or too subtle to be read as suspicious |
| `obfuscation_neutral` | (obf_* only) the obfuscation is visible but the e-mail looks legitimate for the same reason as the original (give that reason in the note) |
| `meaning_shifted` | the variant no longer says what the original said (a meaning-check miss; record the shift) |
| `truncated_or_short` | the variant body is too short or cut to carry a cue |
| `label_noise` | you doubt that the original is phishing at all (record why) |
| `other` | anything else; the note is mandatory |

**Reporting.** Chapter 4 reports the code frequencies per set and per condition (the pre-registered 8 and the
post hoc 30 in separate columns, never pooled with the quantitative results) and two or three anonymised quoted
phrases per frequent code, with the statement that the coding was done by one author after the quantitative
results were fixed and that the post hoc set was added because only 8 items met the pre-registered criterion.
The sample sizes are 8 and 30, so the frequencies are indicative only.
