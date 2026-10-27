#!/usr/bin/env python3
"""
06_download_models.py — download and pin the detector GGUF files (TASK_06 sections 1 and 5; Section 3.7).

For every selected model in configs/models.yaml: check the exclusion rule (configs/variants.yaml
excluded_from_detectors must not match the model name), download gguf_file from gguf_repo into models/
(gitignored; HF_TOKEN from .env when present), compute sha256, verify it against the recorded value or,
when the value is still null, write it into configs/models.yaml (text edit that keeps the comments), and
record size, licence string and time in reports/models_download_report.json (merged per model).

Usage: python scripts/06_download_models.py [--tier laptop|colab_t4|colab_l4|all] [--models k1,k2] [--dry-run]
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

import huggingface_hub

from common import ROOT, load_config, read_text, write_json, write_text
from detect.prompts import sha256_file

REPORT = ROOT / "reports" / "models_download_report.json"


def hf_token() -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in read_text(env).splitlines():
            if line.startswith("HF_TOKEN=") and line.split("=", 1)[1].strip():
                return line.split("=", 1)[1].strip()
    return os.environ.get("HF_TOKEN") or None


def excluded_family(name: str, families: list) -> str:
    low = name.lower()
    return next((f for f in families if f.lower() in low), "")


def pin_sha(key: str, sha: str) -> None:
    """Replace `sha256: null` inside the block of model `key` in configs/models.yaml, keeping everything else."""
    path = ROOT / "configs" / "models.yaml"
    lines = read_text(path).split("\n")
    start = next(i for i, l in enumerate(lines) if re.match(rf"^  {re.escape(key)}:\s*$", l))
    for i in range(start + 1, len(lines)):
        if re.match(r"^  \S", lines[i]):
            break
        if re.match(r"^    sha256:\s*null\s*$", lines[i]):
            lines[i] = f"    sha256: {sha}"
            write_text(path, "\n".join(lines))
            return
    raise SystemExit(f"configs/models.yaml: no `sha256: null` line in the block of {key}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="laptop")
    ap.add_argument("--models", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    mcfg = load_config("models.yaml")
    families = load_config("variants.yaml").get("excluded_from_detectors", [])
    keys = [k for k in mcfg["models"] if a.tier == "all" or mcfg["models"][k]["tier"] == a.tier]
    if a.models:
        keys = [k for k in a.models.split(",") if k in mcfg["models"]]
    local = ROOT / mcfg["local_dir"]
    local.mkdir(exist_ok=True)
    report = json.loads(read_text(REPORT)) if REPORT.exists() else {}
    token = hf_token()
    print(f"models: {keys}; token: {'present' if token else 'none'}; dir: {local}")

    for key in keys:
        e = mcfg["models"][key]
        fam = excluded_family(e["name"], families)
        if fam:
            raise SystemExit(f"{key} ({e['name']}) belongs to the excluded paraphrase family '{fam}'")
        dest = local / e["gguf_file"]
        print(f"[{key}] {e['gguf_repo']}/{e['gguf_file']} ({e['gguf_bytes'] / 1e9:.2f} GB) -> {dest.name}", flush=True)
        if a.dry_run:
            continue
        if not (dest.exists() and dest.stat().st_size == e["gguf_bytes"]):
            t0 = dt.datetime.now(dt.timezone.utc)
            huggingface_hub.hf_hub_download(repo_id=e["gguf_repo"], filename=e["gguf_file"],
                                            local_dir=str(local), token=token)
            print(f"[{key}] downloaded in {(dt.datetime.now(dt.timezone.utc) - t0).total_seconds():.0f} s", flush=True)
        size = dest.stat().st_size
        sha = sha256_file(dest)
        status = "verified"
        if e.get("sha256"):
            if sha != e["sha256"]:
                raise SystemExit(f"{key}: sha256 {sha} differs from configs/models.yaml ({e['sha256']})")
        else:
            pin_sha(key, sha)
            status = "pinned"
        if size != e["gguf_bytes"]:
            print(f"[{key}] WARNING size {size} differs from gguf_bytes {e['gguf_bytes']}")
        report[key] = {"name": e["name"], "gguf_repo": e["gguf_repo"], "gguf_file": e["gguf_file"], "bytes": size,
                       "sha256": sha, "status": status, "license": e["license"], "license_class": e["license_class"],
                       "quantization": mcfg["quantization"], "tier": e["tier"],
                       "checked_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "huggingface_hub": huggingface_hub.__version__}
        write_json(REPORT, report)
        print(f"[{key}] sha256 {sha} ({status}); {size:,} bytes", flush=True)
    if not a.dry_run:
        print(f"-> {REPORT.relative_to(ROOT)}; configs/models.yaml updated where sha256 was null")
    return 0


if __name__ == "__main__":
    sys.exit(main())
