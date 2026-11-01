"""
hardcore_codes.py — the two code lists of docs/HARDCORE_CODING_GUIDE.md (TASK_07 section 4c, QUESTIONS.md items 12c
and 17), shared by the coding sheet builder (07_coding_sheet.py) and the importer (07_import_coding.py).
tests/test_coding_sheet.py checks that these lists equal the backticked codes of the guide's two tables.
"""
ORIGINAL_CODES = {   # condition original: why does this spear-phishing e-mail look legitimate?
    "plausible_business": "routine work e-mail: specific, reasonable request between colleagues or partners, fitting context, no explicit lure",
    "no_call_to_action": "no request to click, open, pay, log in or reply with information; intent implicit or deferred",
    "benign_request": "a low-stakes, ordinary request (review a document, confirm a meeting, send a file) without credential, payment or link cue",
    "personalised_pretext": "the personalisation itself convinces: correct names, roles, shared history or company detail",
    "placeholder_artifact": "the neutralised link or placeholder token removes the cue a reader would otherwise notice",
    "truncated_or_short": "the body is too short or cut to carry a cue",
    "label_noise": "you doubt that the item is phishing at all (record why)",
    "other": "anything else; the note is mandatory",
}
VARIANT_CODES = {    # condition para_* / obf_*: what changed relative to the original?
    "paraphrase_softened": "(para_*) the paraphrase removed or weakened the urgency, threat or request wording of the original",
    "paraphrase_cue_dropped": "(para_*) a concrete cue of the original (link, attachment, credential or payment request, sender claim) is absent or reworded beyond recognition",
    "paraphrase_neutral": "(para_*) cues preserved; the variant looks legitimate for the same reason as the original (give that reason in the note)",
    "obfuscation_unnoticed": "(obf_*) the character-level changes are too sparse or too subtle to read as suspicious",
    "obfuscation_neutral": "(obf_*) the obfuscation is visible but the e-mail looks legitimate for the same reason as the original (give that reason in the note)",
    "meaning_shifted": "the variant no longer says what the original said (a meaning-check miss; record the shift)",
    "truncated_or_short": "the variant body is too short or cut to carry a cue",
    "label_noise": "you doubt that the original is phishing at all (record why)",
    "other": "anything else; the note is mandatory",
}
NOTE_REQUIRED = ("other",)


def codes_for(condition: str) -> dict:
    return ORIGINAL_CODES if condition == "original" else VARIANT_CODES


def row_type(condition: str) -> str:
    return "original" if condition == "original" else "variant"
