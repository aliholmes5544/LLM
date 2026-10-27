#!/usr/bin/env python3
"""
06_select_fewshot.py — draw the fixed few-shot examples (TASK_06 section 2; Section 3.5).

Four labelled examples (2 phishing, 2 legitimate) are drawn once from `fewshot_pool` with the project
seed and used unchanged for every model and every item. Candidates are visited in a seeded random order
(one RNG stream per class, derived as in step 05) and a candidate is accepted only if
  (a) its body has between few_shot.min_words and few_shot.max_words words (context budget: four
      examples plus a 600-word item must fit n_ctx with room for the answer),
  (b) it shares no PERSON or ORG entity token with any Nahmias spear-phishing original (core_pos), using
      the spaCy model of step 05 (persona/organisation rule: the examples must not teach a detector the
      SafeSecurity cast), and
  (c) it has no near-duplicate (word-trigram Jaccard >= threshold) among the evaluation items (the step 04
      leakage rule, re-applied to the chosen examples), and
  (d) its word-level Jaccard similarity to an example of the same label accepted before it is below
      few_shot.max_same_label_jaccard, so the two examples of a label are not near-copies of each other.
Rules (a) and (d) were set by the author on 2026-10-27 (QUESTIONS.md item 10; first draw: 20-word minimum,
no rule (d)); the earlier ids are logged in docs/CHANGES_FOR_THESIS.md.
The pool is train = traditional phishing + Enron ham only (never spear, never E-PhishLLM; step 04).

Output: prompts/few_shot_examples.json (slot order, ids, labels and sha256 of subject and body; no text,
so no data enters git; 06_run_detection.py renders the texts from records.jsonl and verifies the hashes)
and reports/fewshot_selection.json (every candidate examined and why it was rejected).
Usage: python scripts/06_select_fewshot.py
"""
import hashlib
import json
import re
import sys
from collections import Counter

import spacy

from common import ROOT, load_config, open_utf8, write_json, trigrams, norm_key
from variants.rng import derive_rng

CFG = load_config()
DCFG = load_config("detection.yaml")
FS = DCFG["few_shot"]
SEED = CFG["seed"]
PROC = ROOT / "data" / "processed"
WORD_RE = re.compile(r"[a-z]+")
# entity tokens that name no person or organisation on their own
STOP = {"inc", "ltd", "llc", "corp", "corporation", "company", "co", "team", "the", "and", "of", "for",
        "group", "department", "dept", "university", "mr", "mrs", "ms", "dr", "it", "hr", "re", "fw", "fwd"}


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def word_jaccard(a: str, b: str) -> float:
    """Jaccard similarity of the normalised word sets of two bodies."""
    wa, wb = set(norm_key(a).split()), set(norm_key(b).split())
    return len(wa & wb) / len(wa | wb) if wa | wb else 0.0


def entity_tokens(text: str, nlp, labels: set, min_chars: int) -> set:
    """Lower-cased alphabetic tokens of every PERSON/ORG entity in `text`."""
    out = set()
    for ent in nlp(text).ents:
        if ent.label_ in labels:
            out.update(t for t in WORD_RE.findall(ent.text.lower()) if len(t) >= min_chars and t not in STOP)
    return out


def main() -> int:
    recs = {}
    for line in open_utf8(PROC / "records.jsonl"):
        r = json.loads(line)
        recs[r["id"]] = r
    part = json.loads(open_utf8(PROC / "partitions.json").read())
    pool = part[FS["pool"]]
    pc = FS["persona_check"]
    nlp = spacy.load(pc["spacy_model"], disable=["lemmatizer"])
    labels, min_chars = set(pc["ner_labels"]), pc["min_token_chars"]

    protected = set()                               # entity tokens of every Nahmias spear-phishing original
    for i in part[pc["against_partition"]]:
        protected |= entity_tokens(recs[i]["subject"] + "\n" + recs[i]["body"], nlp, labels, min_chars)
    print(f"persona check: {len(protected)} distinct PERSON/ORG tokens in {pc['against_partition']} "
          f"({len(part[pc['against_partition']])} records)")

    eval_ids = [i for n in DCFG["items"]["originals"] + DCFG["items"]["generalization"] for i in part[n]]
    eval_grams = {i: trigrams(recs[i]["body"]) for i in eval_ids}
    thr = CFG["preprocess"]["near_dup_jaccard"]

    def near_dup(body: str):
        g = trigrams(body)
        for j, c in eval_grams.items():
            if g and c and len(g & c) / len(g | c) >= thr:
                return j
        return None

    chosen, examined, rejected = {}, [], Counter()
    for cls, n_wanted in FS["n_per_class"].items():
        sub = FS["subclass"][cls]
        cands = sorted(i for i in pool if recs[i]["subclass"] == sub and recs[i]["class"] == cls)
        rng = derive_rng(SEED, "few_shot", cls)
        rng.shuffle(cands)
        chosen[cls] = []
        for i in cands:
            if len(chosen[cls]) == n_wanted:
                break
            r = recs[i]
            entry = {"id": i, "class": cls, "subclass": sub, "n_words": r["n_words"]}
            if not FS["min_words"] <= r["n_words"] <= FS["max_words"]:
                entry["rejected"] = "length"
            else:
                shared = sorted(entity_tokens(r["subject"] + "\n" + r["body"], nlp, labels, min_chars) & protected)
                if shared:
                    entry["rejected"] = "persona"
                    entry["shared_tokens"] = shared
                else:
                    dup = near_dup(r["body"])
                    if dup:
                        entry["rejected"] = "near_dup"
                        entry["near_dup_of"] = dup
                    else:
                        for prev in chosen[cls]:
                            jac = word_jaccard(r["body"], recs[prev]["body"])
                            if jac >= FS["max_same_label_jaccard"]:
                                entry["rejected"] = "similar"
                                entry["similar_to"] = prev
                                entry["word_jaccard"] = round(jac, 3)
                                break
            examined.append(entry)
            if "rejected" in entry:
                rejected[(cls, entry["rejected"])] += 1
            else:
                chosen[cls].append(i)
        if len(chosen[cls]) < n_wanted:
            raise SystemExit(f"only {len(chosen[cls])} acceptable {cls} examples found")

    words = DCFG["labels"]["answer_words"]
    slots, taken = [], {c: 0 for c in chosen}
    for slot, cls in enumerate(FS["order"], start=1):
        i = chosen[cls][taken[cls]]
        taken[cls] += 1
        r = recs[i]
        same = [recs[s["id"]]["body"] for s in slots if s["class"] == cls]
        slots.append({"slot": slot, "id": i, "class": cls, "label": words[cls], "subclass": r["subclass"],
                      "word_jaccard_to_same_label": round(word_jaccard(r["body"], same[0]), 3) if same else None,
                      "source": r["source"], "n_words": r["n_words"],
                      "subject_sha256": sha256(r["subject"]), "body_sha256": sha256(r["body"])})

    out = {"seed": SEED, "pool": FS["pool"], "pool_size": len(pool),
           "rules": {"min_words": FS["min_words"], "max_words": FS["max_words"],
                     "max_same_label_jaccard": FS["max_same_label_jaccard"],
                     "persona_check": pc, "near_dup_jaccard": thr, "order": FS["order"]},
           "examples": slots}
    write_json(ROOT / FS["examples_file"], out)
    report = {"seed": SEED, "examined": len(examined),
              "rejected": {f"{c}:{why}": n for (c, why), n in sorted(rejected.items())},
              "protected_tokens": len(protected), "chosen": [s["id"] for s in slots], "candidates": examined}
    write_json(ROOT / "reports" / "fewshot_selection.json", report)

    for s in slots:
        print(f"slot {s['slot']}  {s['label']:10s} {s['id']}  ({s['n_words']} words)")
    print(f"examined {len(examined)} candidates; rejected {dict(report['rejected']) or 'none'}")
    print(f"-> {FS['examples_file']}, reports/fewshot_selection.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
