"""
resume.py — the resume / skip / refuse decision of scripts/06_run_detection.py (TASK_06 section 5:
"resumable, never overwrites a finished eval file"). Pure function, no model and no data, so it is unit-tested
in tests/test_resume.py. Found necessary on the first Colab resume (2026-10-29): the notebook loops over
every cell, so a complete cell must be skipped with exit code 0, not refused.
"""

SKIP, RUN, FORCE = "skip", "run", "force"


def hashes_match(rows: list, prompt_hash: str, model_sha256) -> bool:
    """Every existing row carries the current prompt hash and (when the model hash is pinned) model hash."""
    return all(r["prompt_hash"] == prompt_hash and (model_sha256 is None or r["model_hash"] == model_sha256)
               for r in rows)


def decide(rows: list, expected: list, prompt_hash: str, model_sha256, force: bool, reason: str) -> str:
    """What to do with an existing results file.

    - no rows                                  -> RUN (fresh cell)
    - --force                                  -> FORCE (archive the file and rerun); refused without --reason
    - rows with a different prompt/model hash  -> refused (SystemExit): artefacts changed, use --force --reason
    - every expected item present              -> SKIP (already complete; the file is not touched)
    - otherwise                                -> RUN (resume at the missing items)
    """
    if force:
        if not (reason or "").strip():
            raise SystemExit("--force requires --reason")
        return FORCE if rows else RUN
    if not rows:
        return RUN
    if not hashes_match(rows, prompt_hash, model_sha256):
        raise SystemExit("existing rows carry prompt/model hashes that differ from the current ones; the cell "
                         "cannot be resumed with changed artefacts (use --force --reason \"...\" to archive and rerun)")
    have = {r["item_id"] for r in rows}
    return SKIP if set(expected) <= have else RUN
