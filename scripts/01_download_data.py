#!/usr/bin/env python3
"""
01_download_data.py — fetch source datasets at pinned commits.

Datasets are NOT redistributed with this code. This script downloads each
source repository at the exact commit recorded in configs/data.yaml, so the
composition reported in Section 3.2 can be reproduced.

Usage:  python scripts/01_download_data.py
Output: data/raw/<name>/ and data/raw/provenance.json
"""
import hashlib
import io
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from common import ROOT, load_config, write_json

CFG = load_config()
RAW = ROOT / "data" / "raw"


def fetch_zip(repo: str, commit: str, dest: Path) -> dict:
    """Download a repo at a specific commit; return provenance record."""
    url = f"https://codeload.github.com/{repo}/zip/{commit}"
    print(f"  fetching {repo} @ {commit[:10]}")
    with urllib.request.urlopen(url, timeout=180) as r:
        blob = r.read()
    digest = hashlib.sha256(blob).hexdigest()
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        root_dir = z.namelist()[0].split("/")[0]
        z.extractall(dest.parent)
    extracted = dest.parent / root_dir
    if dest.exists():
        import shutil
        shutil.rmtree(dest)
    extracted.rename(dest)
    n_files = sum(1 for _ in dest.rglob("*") if _.is_file())
    print(f"    -> {dest.relative_to(ROOT)}  ({n_files} files, zip sha256 {digest[:16]}...)")
    return {"repo": repo, "commit": commit, "zip_sha256": digest, "files": n_files}


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    prov = {"fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sources": {}}
    for name, s in CFG["sources"].items():
        try:
            rec = fetch_zip(s["repo"], s["commit"], RAW / name)
        except Exception as exc:                      # network, 404, bad commit
            print(f"  FAILED {name}: {exc}", file=sys.stderr)
            return 1
        rec["license"] = s.get("license", "unspecified")
        prov["sources"][name] = rec

    # presence checks: fail loudly rather than silently producing empty data
    nah = RAW / "nahmias" / CFG["sources"]["nahmias"]["subdir"]
    eph = RAW / "ephishllm" / CFG["sources"]["ephishllm"]["file"]
    missing = [str(p) for p in (nah, eph) if not p.exists()]
    if missing:
        print(f"  FAILED: expected paths missing: {missing}", file=sys.stderr)
        return 1

    write_json(RAW / "provenance.json", prov)
    print(f"\nprovenance written to {(RAW / 'provenance.json').relative_to(ROOT)}")
    print("NOTE: source data are not redistributed; licenses are recorded in provenance.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
