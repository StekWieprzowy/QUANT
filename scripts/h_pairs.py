"""Family P: pairs trading on WIG20 stocks (z-score mean reversion of dollar-neutral log spreads)."""
from __future__ import annotations

import sys

from quant import research
from quant.config import BASE_STOCK_COSTS
from quant.strategies import pairs
from quant.validation import param_grid

VARIANT = sys.argv[1] if len(sys.argv) > 1 else "P1"


def main():
    if VARIANT == "P1":
        book, spreads = pairs.build_book(pairs.PAIRS, BASE_STOCK_COSTS)
        fn = pairs.decision_fn_factory(book, spreads)
        grid = param_grid({"lookback": [20, 60], "z_in": [1.5, 2.0]})
        ev = research.evaluate("pairs", "P1 z-score pairs book (8 econ. pairs, 1:1)", book, fn, grid,
                               notes="stocks 0.39%/side/leg + 3% borrow; dollar-neutral daily rebal approx",
                               log_screen="--no-screen" not in sys.argv)
        print(ev.line())
        print(research.fmt_eval_md(ev))
    if VARIANT == "P2":  # P1 had gross SR 1.3 but costs ate it -> fewer, larger dislocations
        book, spreads = pairs.build_book(pairs.PAIRS, BASE_STOCK_COSTS)
        fn = pairs.decision_fn_factory(book, spreads)
        grid = param_grid({"lookback": [60, 120], "z_in": [2.5, 3.0]})
        ev = research.evaluate("pairs", "P2 z-score pairs book, high threshold", book, fn, grid,
                               notes="same as P1 but wider entry bands to cut turnover")
        print(ev.line())
        print(research.fmt_eval_md(ev))


if __name__ == "__main__":
    main()
