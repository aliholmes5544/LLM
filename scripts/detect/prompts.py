"""
prompts.py — prompt loading, rendering and hashing for the detection stage (TASK_06 section 2; Section 3.5).

A prompt file has a "### system" section and a "### user" section (markers in configs/detection.yaml).
Placeholders: {subject} and {body}; few_shot additionally {exN_subject}, {exN_body}, {exN_label} for
N = 1..4, filled from records.jsonl through prompts/few_shot_examples.json (ids and sha256 only; the
hashes are verified at load time so the examples cannot drift). Rendering uses str.replace, never
str.format, because email text may contain braces. Models whose chat template has no system role
receive the system text prepended to the user message (QUESTIONS.md item 9).
"""
import hashlib
import json
from pathlib import Path

from common import ROOT, read_text


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_prompt(dcfg: dict, strategy: str) -> dict:
    """{"strategy", "file", "sha256", "system", "user"} for one strategy."""
    pc = dcfg["prompts"]
    path = ROOT / pc["dir"] / pc["strategies"][strategy]
    text = read_text(path)
    sys_m, usr_m = pc["section_markers"]["system"], pc["section_markers"]["user"]
    i, j = text.index(sys_m), text.index(usr_m)
    if not 0 <= i < j:
        raise ValueError(f"{path}: expected '{sys_m}' before '{usr_m}'")
    system = text[i + len(sys_m):j].strip()
    user = text[j + len(usr_m):].strip()
    return {"strategy": strategy, "file": str(path.relative_to(ROOT)), "sha256": sha256_text(text),
            "system": system, "user": user}


def load_fewshot(dcfg: dict, recs: dict) -> dict:
    """Few-shot examples in slot order with their texts; verifies every recorded hash."""
    path = ROOT / dcfg["few_shot"]["examples_file"]
    spec = json.loads(read_text(path))
    examples = []
    for s in spec["examples"]:
        r = recs[s["id"]]
        if sha256_text(r["subject"]) != s["subject_sha256"] or sha256_text(r["body"]) != s["body_sha256"]:
            raise ValueError(f"few-shot example {s['id']} differs from the recorded hashes")
        examples.append({"id": s["id"], "subject": r["subject"], "body": r["body"], "label": s["label"]})
    return {"file": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "examples": examples}


def render(prompt: dict, subject: str, body: str, examples: list = None) -> tuple:
    """(system, user) with every placeholder filled; raises if a placeholder is left."""
    user = prompt["user"]
    for n, ex in enumerate(examples or [], start=1):
        user = (user.replace(f"{{ex{n}_subject}}", ex["subject"]).replace(f"{{ex{n}_body}}", ex["body"])
                .replace(f"{{ex{n}_label}}", ex["label"]))
    if "{ex" in user:
        raise ValueError(f"{prompt['file']}: unfilled example placeholder")
    user = user.replace("{subject}", subject).replace("{body}", body)
    return prompt["system"], user


def messages(system: str, user: str, system_role: bool) -> list:
    """Chat messages; without a system role the system text is prepended to the user turn."""
    if system_role:
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return [{"role": "user", "content": system + "\n\n" + user}]
