#!/usr/bin/env python3
"""
demo_detect.py — SpearShift demo: classify ONE e-mail with one of the study's detector models on the laptop.

Outside the evaluation pipeline: nothing is written to results/ or reports/, no partition is read, and the
output is not an evaluation result. It uses exactly the study's components: the model entry of
configs/models.yaml (GGUF verified by sha256), the prompt file of configs/detection.yaml for the chosen strategy
(few_shot renders the four frozen examples from data/processed/records.jsonl), the frozen decoding settings
(greedy, seed from configs/data.yaml), the context-fitting rule, the system-text delivery rule of the model
(system_role) and scripts/common.py extract_label. Detectors see subject and body only.

Usage: python scripts/demo_detect.py --subject "..." --body "..."  [--model gemma2-9b] [--strategy zero_shot]
       python scripts/demo_detect.py --file mail.txt                [--tier laptop] [--show-prompt]
  --file: a UTF-8 text file; a first line "Subject: ..." is taken as the subject, the rest (after a blank line)
          as the body. --subject overrides it.
  The model must be present in models/ (python scripts/06_download_models.py --models <key>); gemma2-9b on a
  16-thread CPU answers in about 10 to 30 s after a load of about 20 s.
"""
import argparse
import sys
import time

from common import ROOT, load_config, extract_label
from detect.backend import Detector, resolve_backend
from detect.prompts import load_prompt, load_fewshot, messages, render

DEFAULT_MODEL, DEFAULT_STRATEGY = "gemma2-9b", "zero_shot"


def read_file(path: str) -> tuple:
    text = open(path, encoding="utf-8").read()
    subject, body = "", text
    lines = text.splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        rest = lines[1:]
        while rest and not rest[0].strip():
            rest = rest[1:]
        body = "\n".join(rest)
    return subject, body.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="Classify one e-mail with a study detector (demo, not an evaluation).")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="key in configs/models.yaml (default gemma2-9b)")
    ap.add_argument("--strategy", default=DEFAULT_STRATEGY, help="zero_shot (default), few_shot, cot or role")
    ap.add_argument("--subject", default=None)
    ap.add_argument("--body", default=None)
    ap.add_argument("--file", default=None, help="text file: optional 'Subject: ...' first line, then the body")
    ap.add_argument("--tier", default="laptop", help="runtime settings (speed only); default laptop")
    ap.add_argument("--show-prompt", action="store_true", help="print the rendered system and user text")
    a = ap.parse_args()

    mcfg, dcfg, seed = load_config("models.yaml"), load_config("detection.yaml"), load_config("data.yaml")["seed"]
    if a.model not in mcfg["models"]:
        raise SystemExit(f"unknown model {a.model}; keys: {list(mcfg['models'])}")
    if a.strategy not in dcfg["prompts"]["strategies"]:
        raise SystemExit(f"unknown strategy {a.strategy}; keys: {list(dcfg['prompts']['strategies'])}")
    if a.tier not in mcfg["tiers"]:
        raise SystemExit(f"unknown tier {a.tier}; keys: {list(mcfg['tiers'])}")
    if a.file is None and (a.subject is None or a.body is None):
        raise SystemExit("give --subject and --body, or --file")
    subject, body = read_file(a.file) if a.file else ("", "")
    subject = a.subject if a.subject is not None else subject
    body = a.body if a.body is not None else body
    if not body.strip():
        raise SystemExit("the body is empty")

    entry = mcfg["models"][a.model]
    tier = load_config(mcfg["tiers"][a.tier]["runtime"])
    backend = resolve_backend("auto", tier, a.tier, mcfg["tiers"])
    prompt = load_prompt(dcfg, a.strategy)
    examples, prompt_hash = None, prompt["sha256"]
    if a.strategy == "few_shot":
        from detect.items import load_records
        try:
            fewshot = load_fewshot(dcfg, load_records())
        except FileNotFoundError as e:
            raise SystemExit(f"few_shot needs data/processed/records.jsonl for the four frozen examples ({e}); "
                             f"run scripts/01_download_data.py to 04_partition.py, or use another strategy")
        examples, prompt_hash = fewshot["examples"], prompt["sha256"] + ":" + fewshot["sha256"]
    max_tokens = dcfg["decoding"]["max_tokens"][a.strategy]

    print(f"SpearShift demo (not an evaluation result): {a.model} ({entry['name']}), strategy {a.strategy}, "
          f"tier {a.tier}, backend {backend}", flush=True)
    t0 = time.perf_counter()
    try:
        det = Detector(a.model, mcfg, dcfg, tier, seed)
    except FileNotFoundError as e:
        raise SystemExit(f"{e}\n  python scripts/06_download_models.py --models {a.model}")
    print(f"model loaded in {det.load_s} s; sha256 {det.model_hash[:16]} (verified against configs/models.yaml); "
          f"prompt sha256 {prompt_hash[:16]}; system text {'as system turn' if entry['system_role'] else 'prepended to the user turn'}",
          flush=True)
    fitted, truncated = det.fit_body(lambda b: render(prompt, subject, b, examples), body, max_tokens)
    system, user = render(prompt, subject, fitted, examples)
    if a.show_prompt:
        print("\n--- system ---\n" + system + "\n--- user ---\n" + user + "\n--- end ---")
    out = det.complete(messages(system, user, entry["system_role"]), max_tokens)
    det.close()
    label = extract_label(out["raw_output"], a.strategy)
    print(f"\nraw output ({out['n_output_tokens']} tokens, finish {out['finish_reason']}, {out['latency_s']} s"
          f"{', body truncated to fit the context' if truncated else ''}):")
    print(out["raw_output"].strip() or "(empty)")
    print(f"\nextracted label: {label.upper()}" + ("  (no single valid answer word; counted as incorrect in the study)" if label == "invalid" else ""))
    print(f"total {time.perf_counter() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
