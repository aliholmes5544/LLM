"""
cues.py — the CoT cue lexicon (TASK_07 section 4b, QUESTIONS.md item 12b; Chapter 4 Sections 4.3 and 4.5).

A cue lexicon is a frozen YAML file (configs/cue_lexicon.yaml) with eight categories (urgency, link/URL,
sender/domain mismatch, credential/payment request, grammar/spelling, impersonation/authority, attachment,
generic greeting). Each category holds named regular expressions. A rationale "mentions" a category when any
of its patterns matches; each match is additionally classified as asserted or negated by a clause-scope
heuristic (a negation marker such as "no", "not", "without", "lacks" earlier in the same clause, not followed
by a conjunction plus an asserting verb), so that "does not contain any suspicious links" counts as a negated
link mention and "lacks personalization and uses a generic greeting" counts as an asserted greeting mention.

The lexicon was written by hand from the dev-partition CoT rationales only (scripts/07_freeze_lexicon.py) and
is identified by the sha256 of the YAML file. Nothing here reads results or compares a prediction with its
label; the eval rationales are first touched by scripts/07_secondary.py (TASK_07 step 3).
"""
import hashlib
import re

import yaml

from common import cot_rationale

CATEGORIES = ("urgency", "link_url", "sender_mismatch", "credential_payment", "grammar_spelling",
              "impersonation_authority", "attachment", "generic_greeting")


def lexicon_sha256(path) -> str:
    """Identity of the frozen lexicon: sha256 of the YAML file bytes."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class Lexicon:
    """Compiled cue lexicon. `spec` is the parsed YAML."""

    def __init__(self, spec: dict):
        self.spec = spec
        flags = re.IGNORECASE
        cats = spec["categories"]
        if tuple(cats) != CATEGORIES:
            raise ValueError(f"lexicon categories {tuple(cats)} differ from the pre-registered set {CATEGORIES}")
        self.patterns = {}
        for cat, block in cats.items():
            names = [p["name"] for p in block["patterns"]]
            if len(set(names)) != len(names) or not names:
                raise ValueError(f"{cat}: pattern names must be unique and non-empty")
            self.patterns[cat] = [(p["name"], re.compile(p["regex"], flags)) for p in block["patterns"]]
        neg = spec["negation"]
        self.neg_marker = re.compile(neg["markers"], flags)
        self.clause_break = re.compile(neg["clause_breaks"], flags)
        self.scope_break = re.compile(neg["scope_breaks"], flags)

    def is_negated(self, text: str, start: int) -> bool:
        """Negation marker in the same clause before `start`, with no scope break between marker and match."""
        win = text[:start]
        cut = max((m.end() for m in self.clause_break.finditer(win)), default=0)
        win = win[cut:]
        last = None
        for m in self.neg_marker.finditer(win):
            last = m
        if last is None:
            return False
        return self.scope_break.search(win, last.end()) is None

    def matches(self, text: str) -> list:
        """Every (category, pattern) match with its span, text and polarity, in text order."""
        out = []
        for cat, pats in self.patterns.items():
            for name, rx in pats:
                for m in rx.finditer(text):
                    out.append({"category": cat, "pattern": name, "start": m.start(), "end": m.end(),
                                "text": m.group(0), "negated": self.is_negated(text, m.start())})
        out.sort(key=lambda d: (d["start"], d["end"], d["category"], d["pattern"]))
        return out

    def cue_flags(self, text: str) -> dict:
        """Per category: mentioned (any match), asserted (any non-negated match), negated (mentioned, none asserted)."""
        flags = {cat: {"mentioned": False, "asserted": False, "negated": False} for cat in CATEGORIES}
        for m in self.matches(text):
            f = flags[m["category"]]
            f["mentioned"] = True
            if not m["negated"]:
                f["asserted"] = True
        for f in flags.values():
            f["negated"] = f["mentioned"] and not f["asserted"]
        return flags

    def rationale_flags(self, raw_output: str) -> dict:
        """cue_flags of the CoT rationale (text before the last FINAL marker, the same split as extract_label)."""
        return self.cue_flags(cot_rationale(raw_output))


def load_lexicon(path) -> Lexicon:
    with open(path, encoding="utf-8") as f:
        return Lexicon(yaml.safe_load(f))
