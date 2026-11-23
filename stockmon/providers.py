"""Quote data providers.

A provider turns a list of ticker symbols into ``Quote`` objects. Two are
included: ``YahooProvider`` (live data, stdlib only) and ``SimulatedProvider``
(random-walk prices for offline use, demos and tests).
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    previous_close: float
    currency: str = "USD"
    timestamp: float = 0.0

    @property
    def change(self) -> float:
        return self.price - self.previous_close

    @property
    def change_pct(self) -> float:
        if not self.previous_close:
            return 0.0
        return self.change / self.previous_close * 100.0


class ProviderError(RuntimeError):
    pass


class Provider:
    name = "base"

    def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        raise NotImplementedError


class YahooProvider(Provider):
    """Fetches quotes from Yahoo Finance's public chart endpoint."""

    name = "yahoo"
    URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1m"
    HEADERS = {"User-Agent": "Mozilla/5.0 (stockmon)"}

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def _fetch(self, symbol: str) -> Quote:
        url = self.URL.format(symbol=urllib.parse.quote(symbol))
        req = urllib.request.Request(url, headers=self.HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.load(resp)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise ProviderError(f"{symbol}: {exc}") from exc
        return self.parse(symbol, data)

    @staticmethod
    def parse(symbol: str, data: dict) -> Quote:
        try:
            result = data["chart"]["result"][0]
            meta = result["meta"]
            price = float(meta["regularMarketPrice"])
            prev = float(meta.get("chartPreviousClose") or meta.get("previousClose") or price)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            err = (data.get("chart") or {}).get("error") if isinstance(data, dict) else None
            raise ProviderError(f"{symbol}: unexpected response ({err or exc})") from exc
        return Quote(
            symbol=symbol.upper(),
            price=price,
            previous_close=prev,
            currency=meta.get("currency", "USD"),
            timestamp=float(meta.get("regularMarketTime", time.time())),
        )

    def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        quotes: dict[str, Quote] = {}
        errors: list[str] = []
        for sym in symbols:
            try:
                quotes[sym.upper()] = self._fetch(sym)
            except ProviderError as exc:
                errors.append(str(exc))
        if errors and not quotes:
            raise ProviderError("; ".join(errors))
        return quotes


class SimulatedProvider(Provider):
    """Random-walk prices. Deterministic when given a seed."""

    name = "simulated"

    def __init__(self, seed: int | None = None, volatility: float = 0.01):
        self.rng = random.Random(seed)
        self.volatility = volatility
        self._state: dict[str, tuple[float, float]] = {}  # symbol -> (prev_close, price)

    def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        out: dict[str, Quote] = {}
        for sym in symbols:
            sym = sym.upper()
            if sym not in self._state:
                base = self.rng.uniform(20, 500)
                self._state[sym] = (base, base)
            prev, price = self._state[sym]
            price = max(0.01, price * (1 + self.rng.gauss(0, self.volatility)))
            self._state[sym] = (prev, price)
            out[sym] = Quote(sym, round(price, 2), round(prev, 2), timestamp=time.time())
        return out


PROVIDERS = {"yahoo": YahooProvider, "simulated": SimulatedProvider}


def make_provider(name: str, **kwargs) -> Provider:
    try:
        return PROVIDERS[name](**kwargs)
    except KeyError:
        raise ValueError(f"unknown provider {name!r}; choose from {sorted(PROVIDERS)}") from None
