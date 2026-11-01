"""
output.py — byte-stable CSV output and hashing for the step 07 tables (TASK_07 section 9: every re-run must
reproduce every CSV byte for byte). Floats are written with six significant digits, rows in the order the
producing function fixed, LF line endings.
"""
import hashlib
from pathlib import Path

import pandas as pd

FLOAT_FORMAT = "%.6g"


def write_csv(df: pd.DataFrame, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, float_format=FLOAT_FORMAT, lineterminator="\n", encoding="utf-8")
    return sha256_file(path)


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def compare_outputs(fresh: dict, disk_dir: Path) -> dict:
    """{name: 'identical' | 'differs' | 'missing'} for every freshly written file against disk_dir."""
    out = {}
    for name, sha in fresh.items():
        p = disk_dir / name
        out[name] = "missing" if not p.exists() else ("identical" if sha256_file(p) == sha else "differs")
    return out
