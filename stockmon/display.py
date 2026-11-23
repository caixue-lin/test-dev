"""Terminal rendering of quote tables."""

from __future__ import annotations

import sys
import time

from .providers import Quote

GREEN, RED, BOLD, RESET = "\033[32m", "\033[31m", "\033[1m", "\033[0m"
SPARK = "▁▂▃▄▅▆▇█"


def sparkline(values: list[float]) -> str:
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = hi - lo or 1.0
    return "".join(SPARK[int((v - lo) / span * (len(SPARK) - 1))] for v in values)


def render_table(
    quotes: dict[str, Quote],
    symbols: list[str],
    history: dict[str, list[float]] | None = None,
    color: bool | None = None,
) -> str:
    if color is None:
        color = sys.stdout.isatty()
    history = history or {}
    header = f"{'SYMBOL':<8}{'PRICE':>12}{'CHANGE':>11}{'CHG %':>9}  TREND"
    lines = [f"{BOLD}{header}{RESET}" if color else header, "-" * len(header)]
    for sym in symbols:
        q = quotes.get(sym.upper())
        if q is None:
            lines.append(f"{sym.upper():<8}{'n/a':>12}")
            continue
        row = (
            f"{q.symbol:<8}{q.price:>12,.2f}{q.change:>+11,.2f}{q.change_pct:>+8.2f}%"
            f"  {sparkline(history.get(q.symbol, [])[-20:])}"
        )
        if color and q.change:
            row = f"{GREEN if q.change > 0 else RED}{row}{RESET}"
        lines.append(row)
    lines.append(time.strftime("Updated %Y-%m-%d %H:%M:%S"))
    return "\n".join(lines)
