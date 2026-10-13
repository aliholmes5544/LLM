"""
paraphrase.py — sentence segmentation, selection and the llama.cpp rewriter (Section 3.2.3).

Segmentation is deterministic: the (masked) body is cut after sentence punctuation
followed by spaces, and at every line break; separators are kept so the pieces
re-join to the exact input. A segment is eligible for rewriting only if it still has
at least `min_alpha_words` alphabetic words once [[S#]] tokens are ignored, so greeting
and sign-off lines are copied verbatim. Rewrites go through a JSONL cache keyed by
(model sha256, prompt hash, seed, sentence), which is what makes reruns byte-identical.
"""
import hashlib
import json
import math
import random
import re
from pathlib import Path

from common import GREETING_RE

SEP_RE = re.compile(r"((?<=[.!?])[ \t]+|\n+)")
WORD_RE = re.compile(r"[^\W\d_]+")
MASK_TOKEN_RE = re.compile(r"\[\[S\d+\]\]")
SENTENCE_END_RE = re.compile(r"[.!?:;][\"'”’)\]]*\s*$")
PREFIX_RE = re.compile(r"^\s*(?:rewritten sentence|rewrite|sentence|output)\s*:\s*", re.I)
MASK_INSTRUCTION = "Keep any token of the form [[S#]] exactly as written."
PROMPT_FORMAT = "chat-v2:system=instruction,user=sentence"   # part of the cache key; bump when the layout changes


def split_segments(text: str) -> list:
    """[{text, sep}] such that ''.join(text + sep) == input."""
    parts = SEP_RE.split(text)
    segs = []
    for i in range(0, len(parts), 2):
        segs.append({"text": parts[i], "sep": parts[i + 1] if i + 1 < len(parts) else ""})
    return segs


def reassemble(segs: list, rewrites: dict) -> str:
    """Join segments in order, substituting rewritten text where given."""
    return "".join(rewrites.get(i, s["text"]) + s["sep"] for i, s in enumerate(segs))


def is_eligible(seg_text: str, min_alpha_words: int, long_segment_words: int) -> bool:
    """Rewritable iff the segment reads as a sentence: >= min_alpha_words alphabetic words outside
    spans, not a greeting line, and either ends with sentence punctuation or is long
    (>= long_segment_words). Titles, signature lines and link labels are copied verbatim."""
    plain = MASK_TOKEN_RE.sub(" ", seg_text)
    if GREETING_RE.match(plain):
        return False
    n = sum(1 for w in WORD_RE.findall(plain) if w.isalpha())
    return n >= min_alpha_words and (bool(SENTENCE_END_RE.search(seg_text)) or n >= long_segment_words)


def select_indices(eligible: list, rate: float, rng: random.Random) -> list:
    """Seeded choice of ceil(rate * n) eligible segment indices, returned sorted."""
    if rate >= 1.0:
        return list(eligible)
    k = math.ceil(rate * len(eligible))
    return sorted(rng.sample(eligible, k)) if k else []


def clean_output(raw: str) -> str:
    """Strip label prefixes and wrapping quotes the model sometimes adds; first line only."""
    out = raw.strip().split("\n")[0].strip()
    out = PREFIX_RE.sub("", out)
    if len(out) >= 2 and out[0] == out[-1] and out[0] in "\"'“”":
        out = out[1:-1].strip()
    return out


class Paraphraser:
    """Sentence rewriter over llama-cpp-python with a persistent generation cache."""

    def __init__(self, model_path: Path, model_sha256: str, prompt_text: str, llama_cfg: dict, cache_path: Path):
        self.model_path, self.model_sha256 = model_path, model_sha256
        self.prompt_text, self.cfg = prompt_text, llama_cfg
        self.prompt_hash = hashlib.sha256(f"{PROMPT_FORMAT}|{prompt_text}|{MASK_INSTRUCTION}".encode("utf-8")).hexdigest()
        self.cache_path, self.cache = cache_path, {}
        self.hits = self.misses = self.truncations = 0
        self._llm = None
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        if cache_path.exists():
            with cache_path.open(encoding="utf-8") as fh:
                for line in fh:
                    row = json.loads(line)
                    self.cache[row["key"]] = row

    # -- model -------------------------------------------------------------
    def _load(self):
        if self._llm is None:
            from llama_cpp import Llama
            self._llm = Llama(model_path=str(self.model_path), n_ctx=self.cfg["n_ctx"], n_batch=self.cfg["n_batch"],
                              n_threads=self.cfg["n_threads"], verbose=False)
        return self._llm

    def close(self):
        if self._llm is not None:
            self._llm.close()
            self._llm = None

    @property
    def loaded(self) -> bool:
        return self._llm is not None

    # -- generation ----------------------------------------------------------
    def _key(self, sentence: str, seed: int) -> str:
        return hashlib.sha256(f"{self.model_sha256}|{self.prompt_hash}|{seed}|{sentence}".encode("utf-8")).hexdigest()

    def rewrite(self, sentence: str, seed: int) -> dict:
        """Return {text, raw, finish_reason, cached} for one masked sentence."""
        key = self._key(sentence, seed)
        row = self.cache.get(key)
        if row is None:
            self.misses += 1
            row = self._generate(sentence, seed, key)
            self.cache[key] = row
            with self.cache_path.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            cached = False
        else:
            self.hits += 1
            cached = True
        if row["finish_reason"] == "length":
            self.truncations += 1
        return {"text": clean_output(row["raw"]), "raw": row["raw"], "finish_reason": row["finish_reason"], "cached": cached}

    def _generate(self, sentence: str, seed: int, key: str) -> dict:
        llm = self._load()
        n_in = len(llm.tokenize(sentence.encode("utf-8"), add_bos=False))
        system = self.prompt_text + (f" {MASK_INSTRUCTION}" if MASK_TOKEN_RE.search(sentence) else "")
        res = llm.create_chat_completion(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": sentence}],
            temperature=self.cfg["temperature"], top_p=self.cfg["top_p"],
            max_tokens=max(16, self.cfg["max_tokens_factor"] * n_in), seed=seed)
        choice = res["choices"][0]
        return {"key": key, "model_sha256": self.model_sha256, "prompt_hash": self.prompt_hash, "seed": seed,
                "sentence_in": sentence, "raw": choice["message"]["content"], "finish_reason": choice.get("finish_reason")}
