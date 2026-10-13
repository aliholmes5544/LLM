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
