# NewsSentimentScanner

News-driven signals for short-term traders in Indian markets. It pulls the latest headlines
for your watchlist from Google News, scores their sentiment, tags **why** a stock might move
(order wins, upgrades, results, lock-in expiry, SEBI action…), and tells you what changed
since your last run. A pre-market mode reads overnight global cues (GIFT Nifty, Wall Street,
Asia, crude, dollar, FII flows) and estimates the opening tone.

> **Not investment advice.** Headlines are a noisy, lagging signal. Use this to decide *what to
> look at*, then check price action, volume and the actual filings before trading.

## Features

| Command | What it does |
|---|---|
| `newsscan scan` | Scans every symbol in your watchlist → signal, score, confidence, catalysts, top headlines |
| `newsscan cues` | Pre-market: global cues → weighted **opening bias** (gap-up / flat / gap-down) |
| `newsscan query "gold price"` | One-off scan for any search terms (the original gold scanner) |
| `newsscan size` | Risk-based position sizing from entry, stop and target |

**How a signal is built**

1. **Fetch** — Google News RSS per query, last 2 days by default, India edition.
2. **De-duplicate** — the same story syndicated by five outlets counts once (newest copy kept).
3. **Score** — VADER with a finance lexicon added (`surge`, `downgrade`, `selloff`, `fraud`…),
   or FinBERT, or an ensemble of both.
4. **Tag catalysts** — 13 rule-based tags; bullish/bearish ones nudge the headline score by ±0.15.
5. **Weight by recency** — exponential decay, 24h half-life: yesterday's news counts half.
6. **Aggregate** — one score in [-1, 1] plus a **confidence** that combines how much the
   headlines agree and how many there are. Three headlines that all agree are still low-confidence.
7. **Diff** — compares with the previous run (local SQLite) and reports **flips**
   (Positive → Negative), **jumps** (score moved ≥ 0.3) and **new catalysts**. Optionally
   pushes only those changes to your phone.

**Catalyst tags:** `results`, `order_win`, `rating_up`, `rating_down`, `block_deal`, `lock_in`,
`ipo`, `corporate_action`, `m_and_a`, `regulatory`, `management`, `capex`, `pledge`.

## Quick start

```bash
git clone https://github.com/RamChetanRCR/Trading.git && cd Trading
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # add -r requirements-finbert.txt for FinBERT

cp config/watchlist.example.yaml config/watchlist.yaml   # then edit your symbols
python -m newsscan scan
```

Or install it as a command: `pip install -e .` → `newsscan scan`.

### Examples

```bash
# Watchlist scan, write a Markdown report, push alerts only if something changed
newsscan scan --markdown reports/today.md --notify

# Before 9:15 — how is the market likely to open?
newsscan cues

# Any topic, any lookback
newsscan query "gold price" "gold forecast" --name GOLD --window 7d

# FinBERT instead of VADER
newsscan scan --model finbert

# Size a long: ₹1L account, risk 1%, entry 500, stop 480, target 560
newsscan size --capital 100000 --entry 500 --stop 480 --target 560
# → Quantity: 50 · Max loss at stop ₹1,000 · Reward:risk 3.0
```

The sizer caps any single position at 25% of capital (`--max-pct`) and warns when
reward:risk is below 1.5, the stop is more than 8% away, or the target is on the wrong side.

## Configuration

`config/watchlist.yaml` (git-ignored — your list never gets committed):

```yaml
settings:
  window: 2d
  half_life_hours: 24
  model: vader        # vader | finbert | ensemble
alerts:
  jump: 0.3
watchlist:
  - INFY                                   # searches "INFY share"
  - symbol: RELIANCE
    queries: ["Reliance Industries share", "RIL stock"]
```

### Phone alerts (optional)

Set environment variables — credentials are never read from the config file:

| Channel | Variables |
|---|---|
| [ntfy](https://ntfy.sh) (free, easiest) | `NEWSSCAN_NTFY_TOPIC` (+ optional `NEWSSCAN_NTFY_SERVER`) |
| Telegram bot | `NEWSSCAN_TELEGRAM_TOKEN`, `NEWSSCAN_TELEGRAM_CHAT_ID` |

### Run it on a schedule

```cron
# Mon–Fri: global cues at 8:30, watchlist at 8:45 and every 2 hours during market
30 8 * * 1-5   cd ~/Trading && .venv/bin/python -m newsscan cues --notify
45 8 * * 1-5   cd ~/Trading && .venv/bin/python -m newsscan scan --notify
35 10-14/2 * * 1-5 cd ~/Trading && .venv/bin/python -m newsscan scan --notify
```

## Your data stays local

- `config/watchlist.yaml`, `data/` (run history), `reports/`, `.env`, CSV/XLSX files are all in `.gitignore`.
- The repo only contains a generic example watchlist and synthetic test headlines for a
  fictional company.
- No broker login, API key or account data is needed or stored.

## Project layout

```
newsscan/
  fetch.py       Google News RSS, publisher split, de-duplication
  sentiment.py   VADER (+finance lexicon), FinBERT (lazy), ensemble
  catalysts.py   rule-based catalyst tags with directional bias
  scoring.py     recency weighting, aggregation, confidence
  cues.py        global cues → opening bias
  history.py     SQLite run history and change detection
  sizing.py      risk-based position sizing
  notify.py      ntfy / Telegram alerts
  report.py      terminal tables, Markdown, JSON
  cli.py         command-line entry point
config/watchlist.example.yaml
tests/           offline tests (no network needed)
notebooks/       VADER playground
```

## Development

```bash
pip install -r requirements-dev.txt
pytest -q
```

CI runs the test suite on Python 3.10 and 3.12 for every push and pull request.

## Limitations

- Headline-only scoring: sarcasm, "falls less than expected", and mixed headlines can be misread.
- The opening bias is built from news, not live prices — confirm against actual GIFT Nifty.
- Google News results vary by region and time; scores are relative, not absolute.
- `sentiment_analysis.py` is kept for backwards compatibility and runs the original gold scan.
