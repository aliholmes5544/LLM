"""
backend.py — llama.cpp inference for the detection stage (TASK_06 sections 1 and 2; Section 3.7).

One Detector wraps one GGUF from configs/models.yaml: the file's sha256 is verified against the recorded
value, the chat template embedded in the GGUF is applied by llama-cpp-python, decoding follows
configs/detection.yaml (greedy, fixed seed, per-strategy max_tokens) and is identical on every tier; the
tier file (configs/local.yaml or cloud.yaml) sets threads, batch and GPU layers only. A prompt that would
not fit n_ctx together with the answer has its body truncated at a sentence boundary and the item is
flagged truncated_input. The backend ("cpu" or "cuda") is resolved from the tier and the installed build
and recorded in every result row (QUESTIONS.md item 11: all evaluation inference runs on cuda).
"""
import gc
import re
import subprocess
import time

from common import ROOT
from detect.prompts import sha256_file

TEMPLATE_MARGIN = 64                      # tokens the chat template adds around system + user text
SENTENCE_END_RE = re.compile(r"[.!?][\"')\]]*\s")
BACKENDS = ("cpu", "cuda")


def gpu_name() -> str:
    """Name of the first NVIDIA GPU, or "" when nvidia-smi is absent."""
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=20)
        return r.stdout.strip().splitlines()[0].strip() if r.returncode == 0 and r.stdout.strip() else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def build_supports_gpu() -> bool:
    import llama_cpp
    return bool(llama_cpp.llama_supports_gpu_offload())


def resolve_backend(requested: str, tier: dict, tier_name: str, tiers: dict) -> str:
    """cpu when the tier offloads no layers, cuda otherwise; checks the request and the installed build."""
    want = "cpu" if tier["n_gpu_layers"] == 0 else "cuda"
    declared = tiers[tier_name]["backend"]
    if declared != want:
        raise SystemExit(f"tier {tier_name} declares backend {declared} but its runtime file implies {want}")
    if requested not in ("auto", want):
        raise SystemExit(f"--backend {requested} contradicts tier {tier_name} (backend {want})")
    if want == "cuda" and not build_supports_gpu():
        raise SystemExit("this llama-cpp-python build has no GPU offload; install the CUDA wheel "
                         "(notebooks/cloud_run.ipynb) or use a cpu tier")
    return want


class Detector:
    def __init__(self, key: str, mcfg: dict, dcfg: dict, tier: dict, seed: int, verify_sha: bool = True):
        from llama_cpp import Llama                        # imported here so the tests need no backend
        self.key, self.entry, self.dcfg, self.seed = key, mcfg["models"][key], dcfg, seed
        self.path = ROOT / mcfg["local_dir"] / self.entry["gguf_file"]
        if not self.path.exists():
            raise FileNotFoundError(f"{self.path} missing; run scripts/06_download_models.py")
        self.model_hash = sha256_file(self.path)
        if verify_sha and self.entry.get("sha256") and self.model_hash != self.entry["sha256"]:
            raise ValueError(f"{self.path.name}: sha256 {self.model_hash} differs from configs/models.yaml")
        self.n_ctx = dcfg["context"]["n_ctx"]
        self.backend = "cpu" if tier["n_gpu_layers"] == 0 else "cuda"
        t0 = time.perf_counter()
        self.llm = Llama(model_path=str(self.path), n_ctx=self.n_ctx, n_threads=tier["n_threads"],
                         n_batch=tier["n_batch"], n_gpu_layers=tier["n_gpu_layers"], seed=seed, verbose=False)
        self.load_s = round(time.perf_counter() - t0, 1)

    # ---- context budget ------------------------------------------------------------------------------
    def n_tokens(self, text: str) -> int:
        return len(self.llm.tokenize(text.encode("utf-8"), add_bos=False, special=False))

    def fit_body(self, render_fn, body: str, max_tokens: int) -> tuple:
        """Return (body, truncated) such that system + user text fits n_ctx with room for the answer."""
        budget = self.n_ctx - max_tokens - TEMPLATE_MARGIN
        truncated = False
        while True:
            system, user = render_fn(body)
            if self.n_tokens(system) + self.n_tokens(user) <= budget:
                return body, truncated
            cut = int(len(body) * 0.9)
            ends = [m.end() for m in SENTENCE_END_RE.finditer(body[:cut])]
            body = body[:ends[-1]].rstrip() if ends else body[:cut].rstrip()
            truncated = True
            if not body:
                raise ValueError("prompt does not fit the context even with an empty body")

    # ---- generation ----------------------------------------------------------------------------------
    def complete(self, msgs: list, max_tokens: int) -> dict:
        d = self.dcfg["decoding"]
        t0 = time.perf_counter()
        r = self.llm.create_chat_completion(messages=msgs, temperature=d["temperature"], top_p=d["top_p"],
                                            repeat_penalty=d["repeat_penalty"], max_tokens=max_tokens,
                                            seed=self.seed, stop=d["stop"] or None)
        latency = time.perf_counter() - t0
        choice = r["choices"][0]
        return {"raw_output": choice["message"].get("content") or "", "finish_reason": choice.get("finish_reason"),
                "n_prompt_tokens": r["usage"]["prompt_tokens"], "n_output_tokens": r["usage"]["completion_tokens"],
                "latency_s": round(latency, 3)}

    def close(self) -> None:
        self.llm.close() if hasattr(self.llm, "close") else None
        del self.llm
        gc.collect()
