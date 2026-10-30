"""FW20 hypothesis families. Usage: python scripts/h_fw20.py <VARIANT> [<VARIANT>...] [--no-screen]

Definitions live in quant.strategies.catalog (pre-specified grids + rationale); every run is logged in
hypotheses_log.csv by quant.research.evaluate.
"""
from __future__ import annotations

import sys

from quant import research
from quant.strategies import catalog

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
LOG_SCREEN = "--no-screen" not in sys.argv


def main(variant: str):
    daily, events = research.fw20_events()
    sp = catalog.build(variant, daily, events)
    ev = research.evaluate(sp.family, sp.name, sp.events, sp.fn, sp.grid, notes=sp.notes, log_screen=LOG_SCREEN)
    print(ev.line())
    print(research.fmt_eval_md(ev))
    return ev


if __name__ == "__main__":
    for v in ARGS:
        main(v)
