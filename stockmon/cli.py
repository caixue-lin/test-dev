"""Command-line entry point: ``python -m stockmon``."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from . import __version__
from .alerts import Alert, evaluate
from .display import render_table
from .providers import ProviderError, make_provider

CLEAR = "\033[2J\033[H"


def load_config(path: str | None) -> dict:
    if not path:
        return {}
    return json.loads(Path(path).read_text())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stockmon",
        description="Monitor stock prices in the terminal and raise alerts.",
        epilog="Example: python -m stockmon AAPL MSFT -a 'AAPL>200' -a 'MSFT%3' -i 30",
    )
    p.add_argument("symbols", nargs="*", help="ticker symbols to watch")
    p.add_argument("-c", "--config", help="JSON config file (symbols, alerts, interval, provider)")
    p.add_argument("-a", "--alert", action="append", default=[], metavar="RULE",
                   help="alert rule, e.g. AAPL>200, AAPL<150, TSLA%%5 (repeatable)")
    p.add_argument("-i", "--interval", type=float, help="seconds between refreshes (default 60)")
    p.add_argument("-p", "--provider", choices=["yahoo", "simulated"], help="data source (default yahoo)")
    p.add_argument("--once", action="store_true", help="fetch once, print, and exit")
    p.add_argument("-n", "--iterations", type=int, help="stop after N refreshes")
    p.add_argument("--log", help="append alerts to this file")
    p.add_argument("--csv", help="append every quote to this CSV file")
    p.add_argument("--no-color", action="store_true", help="disable ANSI colours")
    p.add_argument("--no-clear", action="store_true", help="don't clear the screen between refreshes")
    p.add_argument("--seed", type=int, help="random seed for the simulated provider")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)

    symbols = [s.upper() for s in (args.symbols or cfg.get("symbols", []))]
    try:
        alerts = [Alert.parse(r) for r in (args.alert or cfg.get("alerts", []))]
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for a in alerts:  # alerting on a symbol implies watching it
        if a.symbol not in symbols:
            symbols.append(a.symbol)
    if not symbols:
        print("error: no symbols given (pass tickers or use --config)", file=sys.stderr)
        return 2

    interval = args.interval or cfg.get("interval", 60)
    provider_name = args.provider or cfg.get("provider", "yahoo")
    kwargs = {"seed": args.seed} if provider_name == "simulated" else {}
    provider = make_provider(provider_name, **kwargs)
    color = False if args.no_color else None
    iterations = 1 if args.once else args.iterations
    history: dict[str, list[float]] = defaultdict(list)

    count = 0
    try:
        while True:
            try:
                quotes = provider.get_quotes(symbols)
            except ProviderError as exc:
                print(f"[{time.strftime('%H:%M:%S')}] fetch failed: {exc}", file=sys.stderr)
                quotes = {}
            for sym, q in quotes.items():
                history[sym].append(q.price)
            if args.csv and quotes:
                write_csv(args.csv, quotes)

            out = render_table(quotes, symbols, history, color=color)
            if not (args.no_clear or iterations == 1) and sys.stdout.isatty():
                out = CLEAR + out
            print(out)

            for msg in evaluate(alerts, quotes):
                notify(msg, args.log)

            count += 1
            if iterations and count >= iterations:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


def notify(msg: str, log_path: str | None) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ALERT: {msg}"
    print(f"\a{line}")  # \a rings the terminal bell
    if log_path:
        with open(log_path, "a") as fh:
            fh.write(line + "\n")


def write_csv(path: str, quotes) -> None:
    new = not Path(path).exists()
    with open(path, "a") as fh:
        if new:
            fh.write("timestamp,symbol,price,previous_close,change_pct\n")
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        for q in quotes.values():
            fh.write(f"{now},{q.symbol},{q.price},{q.previous_close},{q.change_pct:.4f}\n")


if __name__ == "__main__":
    sys.exit(main())
