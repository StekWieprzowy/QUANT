"""One-shot holdout guard.

`claim_holdout(spec)` succeeds exactly once per repository: it writes holdout/LOCK containing the frozen
candidate specification (and its hash). Any later call raises, whatever the candidate. The lock file is
committed to git so the single use is auditable.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from quant import config

LOCK = config.HOLDOUT_DIR / "LOCK"
RESULT = config.HOLDOUT_DIR / "holdout_result.json"


class HoldoutAlreadyUsed(RuntimeError):
    pass


def spec_hash(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True, default=str).encode()).hexdigest()[:16]


def is_used() -> bool:
    return LOCK.exists()


def claim_holdout(spec: dict) -> str:
    if LOCK.exists():
        raise HoldoutAlreadyUsed(f"holdout already used: {LOCK.read_text()}")
    h = spec_hash(spec)
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(json.dumps({"claimed_at": datetime.now(timezone.utc).isoformat(), "spec_hash": h,
                                "spec": spec}, indent=2, default=str))
    return h


def write_result(result: dict) -> None:
    RESULT.write_text(json.dumps(result, indent=2, default=str))
