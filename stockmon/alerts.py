"""Alert rules and evaluation.

Rule syntax (as used on the command line and in config files)::

    AAPL>200        price rises above 200
    AAPL<150        price falls below 150
    TSLA%5          daily move of at least +/-5%
    TSLA%+5 / %-5   daily move of at least +5% / at most -5%

An alert fires once when its condition becomes true and re-arms when it
becomes false again, so a price hovering above a threshold does not spam.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .providers import Quote

_RULE_RE = re.compile(r"^\s*([A-Za-z0-9.\-^=]+)\s*(>|<|%)\s*([+-]?\d+(?:\.\d+)?)\s*$")


@dataclass
class Alert:
    symbol: str
    op: str  # ">", "<", "%"
    value: float
    signed: bool = False  # for "%": whether the user gave an explicit sign
    _active: bool = field(default=False, repr=False, compare=False)

    @classmethod
    def parse(cls, text: str) -> "Alert":
        m = _RULE_RE.match(text)
        if not m:
            raise ValueError(f"invalid alert rule {text!r} (examples: AAPL>200, MSFT<300, TSLA%5)")
        sym, op, raw = m.groups()
        signed = op == "%" and raw[0] in "+-"
        return cls(sym.upper(), op, float(raw), signed)

    def condition(self, q: Quote) -> bool:
        if self.op == ">":
            return q.price > self.value
        if self.op == "<":
            return q.price < self.value
        if self.signed:
            return q.change_pct >= self.value if self.value >= 0 else q.change_pct <= self.value
        return abs(q.change_pct) >= abs(self.value)

    def check(self, q: Quote) -> str | None:
        """Return a message if the alert newly triggers, else None."""
        hit = self.condition(q)
        fired = hit and not self._active
        self._active = hit
        if not fired:
            return None
        if self.op == "%":
            return f"{self.symbol} moved {q.change_pct:+.2f}% today (now {q.price:.2f}) [rule {self}]"
        word = "above" if self.op == ">" else "below"
        return f"{self.symbol} is {word} {self.value:g}: now {q.price:.2f} [rule {self}]"

    def __str__(self) -> str:
        v = f"{self.value:+g}" if self.signed else f"{self.value:g}"
        return f"{self.symbol}{self.op}{v}"


def evaluate(alerts: list[Alert], quotes: dict[str, Quote]) -> list[str]:
    messages = []
    for a in alerts:
        q = quotes.get(a.symbol)
        if q is not None and (msg := a.check(q)):
            messages.append(msg)
    return messages
