"""Run the empirical look-ahead detector over catalog variants (research data). Usage:
python scripts/check_lookahead.py C1 T1 L1 ...   (default: all non-ML variants)"""
from __future__ import annotations

import sys

from quant import lookahead, research
from quant.strategies import catalog

DEFAULT = ["C1", "C2", "T1", "T2", "M1", "M2", "L1", "L2", "L3", "F1", "O1"]


def main(variants):
    daily, events = research.fw20_events()
    bad = []
    for v in variants:
        grid = catalog.build(v, daily, events).grid
        for p in {0: grid[0], 1: grid[-1]}.values():
            probs = lookahead.check(v, daily, p)
            bad += probs
            print(f"{v} {p}: {'OK' if not probs else probs}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT)
