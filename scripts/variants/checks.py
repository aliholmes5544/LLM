"""
checks.py — automatic meaning checks for paraphrased variants (Section 3.2.3).

  sim_cos    sentence-embedding cosine between whole original and whole variant body
  len_ratio  variant words / original words (words = str.split(), as in step 03)
  spans_ok   every protected span present in the variant
  nli_ok     each rewritten sentence mutually entails its source (both directions)
Model objects are created lazily so the paraphrase model can be released first.
"""
from .spans import spans_present


class Checkers:
    def __init__(self, embedding_model: str, nli_model: str):
        self.embedding_model, self.nli_model = embedding_model, nli_model
        self._emb = self._nli = None
        self.entail_idx = None

    def load(self):
        from sentence_transformers import SentenceTransformer, CrossEncoder
        self._emb = SentenceTransformer(self.embedding_model, device="cpu")
        self._nli = CrossEncoder(self.nli_model, device="cpu")
        id2label = {int(k): v.lower() for k, v in self._nli.model.config.id2label.items()}
        assert set(id2label.values()) == {"contradiction", "entailment", "neutral"}, id2label
        self.entail_idx = next(k for k, v in id2label.items() if v == "entailment")

    def close(self):
        self._emb = self._nli = None

    def cosine(self, a: str, b: str) -> float:
        from sentence_transformers import util
        e = self._emb.encode([a, b], convert_to_tensor=True, normalize_embeddings=True)
        return float(util.cos_sim(e[0], e[1]).item())

    def entailment_both(self, a: str, b: str) -> tuple:
        probs = self._nli.predict([(a, b), (b, a)], apply_softmax=True)
        return float(probs[0][self.entail_idx]), float(probs[1][self.entail_idx])


def len_ratio(orig: str, var: str) -> float:
    n = len(orig.split())
    return len(var.split()) / n if n else 0.0


def run_checks(orig_body: str, var_body: str, sentence_pairs: list, spans: list, thr: dict, ck: Checkers) -> dict:
    """All four checks; `sentence_pairs` = [(original_sentence, rewritten_sentence)] for rewritten segments only."""
    sim = ck.cosine(orig_body, var_body)
    ratio = len_ratio(orig_body, var_body)
    ok_spans, missing = spans_present(var_body, spans)
    nli = [min(ck.entailment_both(a, b)) for a, b in sentence_pairs]
    nli_min = min(nli) if nli else 1.0
    out = {
        "sim_cos": round(sim, 4), "len_ratio": round(ratio, 4), "spans_ok": ok_spans,
        "spans_missing": missing, "nli_min": round(nli_min, 4),
        "nli_per_sentence": [round(x, 4) for x in nli],
        "sim_ok": sim >= thr["thr_cos"],
        "len_ok": thr["len_ratio_min"] <= ratio <= thr["len_ratio_max"],
        "nli_ok": nli_min >= thr["thr_nli"],
    }
    out["passed"] = out["sim_ok"] and out["len_ok"] and out["spans_ok"] and out["nli_ok"]
    return out
