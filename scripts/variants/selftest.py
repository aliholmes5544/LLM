"""
selftest.py — synthetic round-trip tests for the pure variant helpers (no models, no network).

Run via `python scripts/05_derive_variants.py --selftest`. Exercises obfuscation integrity
replay, span masking/restoration, segment splitting/reassembly and the eligibility rule
on strings that contain the awkward cases found in the dev data: non-ASCII letters and
punctuation, digits, intra-word "-" and ".", email-like strings and the placeholder phrases.
"""
import random

from . import obfuscate as ob
from . import paraphrase as pp
from . import spans as sp

OBF_CFG = {"min_token_len": 4,
           "homoglyph": {"a": "а", "e": "е", "o": "о", "c": "с", "p": "р", "x": "х", "i": "і"},
           "digit": {"o": "0", "l": "1", "e": "3", "a": "4", "s": "5"},
           "separators": ["-", "."], "zero_width": "​"}
PHRASES = ["the link", "the attachment", "the address"]

SAMPLES = [
    "Hi Evelyn,\n\nPlease process the transfer of funds for our latest venture. It's crucial that these "
    "resources are available immediately. Use the attached account details.\n\nRegards,\nMark Spencer\nCEO, Maple Leaf Organic Farms",
    "Dear Bayou Biodiesel Team Member,\n\nClick the link before 5 p.m. on March 3, 2025 to confirm. Contact "
    "it-support@example.com or pay €1,200.50 via the address.\n\nThanks — Müller & Söhne",
    "Short.\nA\nxyz q.\n\nTotally-fine words with intra.word dots and hyphen-ated things!",
    "No punctuation at all just words words words words",
]


def _fake_spans(body: str) -> list:
    """Regex spans plus a pretend NER span, to stand in for spaCy."""
    spans = sp._regex_spans(body, PHRASES)
    i = body.find("Mark Spencer")
    if i >= 0:
        spans.append({"start": i, "end": i + 12, "text": "Mark Spencer", "label": "PERSON", "source": "ner"})
    return sp.merge_spans(spans)


def run() -> int:
    failures = 0

    def check(cond: bool, msg: str):
        nonlocal failures
        print(("  ok   " if cond else "  FAIL ") + msg)
        failures += 0 if cond else 1

    print("obfuscation integrity replay")
    for n, body in enumerate(SAMPLES):
        spans = _fake_spans(body)
        for rate in (0.1, 0.3, 1.0):
            for seed in range(5):
                variant, edits, stats = ob.obfuscate(body, spans, rate, random.Random(seed), OBF_CFG)
                check(ob.replay_reverse(variant, edits) == body, f"sample {n} rate {rate} seed {seed}: replay == original")
                check(len(edits) == stats["n_selected"], f"sample {n} rate {rate} seed {seed}: one edit per selected token")
                check(all(s["text"] in variant for s in spans), f"sample {n} rate {rate} seed {seed}: spans untouched")
                if rate == 1.0:
                    check(variant != body or stats["n_eligible"] == 0, f"sample {n} seed {seed}: rate 1.0 changes the body")
    body = SAMPLES[0]
    a = ob.obfuscate(body, _fake_spans(body), 0.3, random.Random(7), OBF_CFG)
    b = ob.obfuscate(body, _fake_spans(body), 0.3, random.Random(7), OBF_CFG)
    check(a == b, "same seed -> identical variant, edits and stats")

    print("span mask / restore")
    for n, body in enumerate(SAMPLES):
        spans = _fake_spans(body)
        masked, mapping = sp.mask(body, spans)
        check(sp.restore(masked, mapping) == body, f"sample {n}: restore(mask(body)) == body")
        check(all(s["text"] not in masked for s in spans if len(s["text"]) > 2), f"sample {n}: span texts absent from masked body")
        check(sp.spans_present(body, spans)[0], f"sample {n}: spans_present on the original")
        if spans:
            check(not sp.spans_present(body.replace(spans[0]["text"], ""), spans)[0], f"sample {n}: spans_present detects a removed span")

    print("segment split / reassemble / eligibility")
    for n, body in enumerate(SAMPLES):
        masked, _ = sp.mask(body, _fake_spans(body))
        segs = pp.split_segments(masked)
        check(pp.reassemble(segs, {}) == masked, f"sample {n}: reassemble(split(masked)) == masked")
    segs = pp.split_segments(sp.mask(SAMPLES[0], _fake_spans(SAMPLES[0]))[0])
    texts = [s["text"] for s in segs]
    check(not pp.is_eligible(texts[0], 3, 8), f"greeting line ineligible: {texts[0]!r}")
    check(pp.is_eligible(texts[1], 3, 8), f"full sentence eligible: {texts[1]!r}")
    check(not pp.is_eligible("[[S1]]", 3, 8) and not pp.is_eligible("Regards,", 3, 8), "masked-only / sign-off ineligible")
    check(not pp.is_eligible("Senior Operations Analyst", 3, 8) and not pp.is_eligible("CEO, [[S2]]", 3, 8),
          "title / signature line ineligible")
    check(pp.is_eligible("Access the shared drive and review every item before the meeting tomorrow", 3, 8),
          "long unpunctuated line eligible")
    check(pp.is_eligible("Please confirm by Friday:", 3, 8) and pp.is_eligible('He said "go now."', 3, 8),
          "colon / quoted period count as sentence ends")
    check(pp.select_indices([0, 1, 2, 3], 0.5, random.Random(1)) == pp.select_indices([0, 1, 2, 3], 0.5, random.Random(1)),
          "selection deterministic")
    check(len(pp.select_indices([0, 1, 2], 0.5, random.Random(1))) == 2, "ceil(0.5 * 3) == 2 segments selected")
    check(pp.clean_output('Rewritten sentence: "Hello [[S1]]."') == "Hello [[S1]].", "output cleanup strips label and quotes")

    print(f"\nselftest: {'PASS' if failures == 0 else f'{failures} FAILURE(S)'}")
    return 0 if failures == 0 else 1
