# test-dev
This repository is for test and dev purpose

## stockmon — a terminal stock monitor

A small, dependency-free (Python 3.10+, stdlib only) tool that watches stock
prices, shows a live colour-coded table with sparkline trends, and raises
alerts when price rules are hit.

### Usage

```bash
# Live table of a few tickers, refreshing every 30 s (Ctrl-C to stop)
python -m stockmon AAPL MSFT NVDA -i 30

# Alerts: price above / below a level, or a daily move of ±N%
python -m stockmon AAPL MSFT -a 'AAPL>250' -a 'MSFT<350' -a 'NVDA%5'

# One-shot snapshot
python -m stockmon AAPL --once

# Use a config file, log alerts, and record every quote to CSV
python -m stockmon -c watchlist.example.json --log alerts.log --csv quotes.csv

# Offline demo with simulated random-walk prices
python -m stockmon AAPL TSLA -p simulated -i 1
```

### Alert rules

| Rule        | Fires when                              |
|-------------|-----------------------------------------|
| `AAPL>200`  | price rises above 200                   |
| `AAPL<150`  | price falls below 150                   |
| `TSLA%5`    | daily change is at least ±5%            |
| `TSLA%+5`   | daily change is at least +5%            |
| `TSLA%-5`   | daily change is at most −5%             |

An alert fires once when its condition becomes true (terminal bell + message,
optionally appended to `--log`) and re-arms once the condition is false again.
Symbols referenced in alerts are added to the watchlist automatically.

### Config file

See `watchlist.example.json`: `symbols`, `alerts`, `interval` (seconds) and
`provider` (`yahoo` or `simulated`). Command-line flags override the file.

### Data providers

- `yahoo` (default) — Yahoo Finance's public chart endpoint. Unofficial, may
  be rate-limited or change; quotes may be delayed.
- `simulated` — random-walk prices for demos and tests (`--seed` for
  reproducibility).

New providers can be added by subclassing `Provider` in
`stockmon/providers.py` and registering them in `PROVIDERS`.

### Tests

```bash
python -m unittest discover -s tests -v
```
