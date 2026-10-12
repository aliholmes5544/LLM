"""
common.py — helpers shared by the numbered pipeline scripts.

Centralizes repo paths, config loading and UTF-8 file I/O so that every
script reads and writes the same way on every machine (Section 3.8:
same input, same config, same seed -> byte-identical outputs). Also holds
the text helpers that were duplicated across scripts 02-04.
"""
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


# ---- config ----------------------------------------------------------------
def load_config(name: str = "data.yaml") -> dict:
    """Load configs/<name> (UTF-8)."""
    return yaml.safe_load(read_text(ROOT / "configs" / name))


# ---- UTF-8 file I/O --------------------------------------------------------
def read_text(path: Path, errors: str = "strict") -> str:
    """Read a text file as UTF-8 regardless of the platform default encoding."""
    return path.read_text(encoding="utf-8", errors=errors)


def write_text(path: Path, text: str) -> None:
    """Write UTF-8 with LF line endings regardless of platform."""
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, obj, indent: int = 2) -> None:
    """json.dumps(obj, indent) -> UTF-8/LF file (no trailing newline, as before)."""
    write_text(path, json.dumps(obj, indent=indent))


def open_utf8(path: Path, mode: str = "r"):
    """Open a text file as UTF-8; writers use LF line endings."""
    return path.open(mode, encoding="utf-8", newline="\n" if "w" in mode else None)


# ---- text helpers (Section 3.2.2) ------------------------------------------
GREETING_RE = re.compile(
    r"^\s*(?:Dear|Hi|Hello|Hey|Good\s+(?:morning|afternoon|evening))\s+([^,\n:!]+)", re.I)
GENERIC = {
    "user", "users", "customer", "customers", "valued customer", "valued user",
    "valued member", "valued partner", "account holder", "sir", "madam",
    "sir/madam", "sir or madam", "team", "team member", "all", "colleague",
    "colleagues", "member", "subscriber", "client", "employee", "recipient",
    "there", "esteemed customer", "friend",
}


def norm_key(body: str) -> str:
    """Normalized body used for exact-duplicate detection."""
    return re.sub(r"\W+", " ", body.lower()).strip()


def trigrams(body: str) -> set:
    """Word-trigram set used for near-duplicate Jaccard (threshold in config)."""
    w = norm_key(body).split()
    return {" ".join(w[i:i + 3]) for i in range(len(w) - 2)}


def salutation_class(body: str) -> str:
    """Salutation proxy: named / generic / none (Section 3.2.1). Expects plain text."""
    m = GREETING_RE.match(body)
    if not m:
        return "none"
    name = m.group(1).strip().lower()
    return "generic" if any(name == g or name.startswith(g + " ") for g in GENERIC) else "named"
