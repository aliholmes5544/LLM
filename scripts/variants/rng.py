"""
rng.py — deterministic random streams for variant derivation (Section 3.2.3).

Every random choice descends from `seed` in configs/data.yaml. Streams are keyed by
(condition, record id) through CRC32, never Python's salted hash(), so that adding or
reordering records cannot shift the draws made for any other record.
"""
import random
import zlib


def _crc(text: str) -> int:
    return zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF


def derive_rng(seed: int, condition: str, record_id: str) -> random.Random:
    """One independent RNG per (condition, record); same inputs -> same stream."""
    return random.Random(seed * 1_000_003 + _crc(f"{condition}:{record_id}"))


def llama_seed(seed: int, record_id: str, sent_idx: int, attempt: int) -> int:
    """Sampler seed for one paraphrase call; attempt 1 is the 'seed+1' regeneration."""
    return (seed * 1_000_003 + _crc(f"{record_id}:{sent_idx}:{attempt}")) & 0x7FFFFFFF
