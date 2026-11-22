"""Command-line interface: `newsscan scan | cues | query | size`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, config, cues, fetch, history, notify, report, scoring, sizing
from .sentiment import get_scorer


def _signal_for(symbol: str, queries: list[str], scorer, *, region, window, per_query, half_life) -> scoring.Signal:
    arts = []
    for q in queries:
        arts.extend(fetch.fetch_news(q, limit=per_query, region=region, window=window))
    scored = scoring.score_articles(fetch.dedupe(arts), scorer, half_life_hours=half_life)
    return scoring.aggregate(symbol, scored)


def cmd_scan(a) -> int:
    cfg = config.load(a.config)
    scorer = get_scorer(a.model or cfg.model)
    signals = []
    with report.console.status("Fetching news...") as st:
        for s in cfg.symbols:
            st.update(f"Scanning {s.symbol}...")
            signals.append(_signal_for(s.symbol, s.queries, scorer, region=cfg.region, window=cfg.window,
                                       per_query=cfg.per_query, half_life=cfg.half_life_hours))
    report.print_signals(signals, show_headlines=a.headlines)

    changes = []
    if not a.no_history:
        h = history.History(a.db)
        for sig in signals:
            changes += history.diff(h.last(sig.symbol), sig, jump=cfg.alerts.get("jump", 0.3))
        h.save(signals)
        h.close()
        report.console.print()
        report.print_changes(changes)

    if a.markdown:
        Path(a.markdown).parent.mkdir(parents=True, exist_ok=True)
        Path(a.markdown).write_text(report.to_markdown(signals, changes), encoding="utf-8")
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(report.to_json(signals), encoding="utf-8")

    alertable = [c for c in changes if c.kind != "new"]
    if a.notify and alertable:
        body = "\n".join(f"{c.symbol}: {c.kind} — {c.detail}" for c in alertable)
        sent = notify.send("Watchlist sentiment changed", body)
        report.console.print(f"[dim]Alert sent via: {', '.join(sent) or 'nothing configured'}[/]")
    return 0


def cmd_cues(a) -> int:
    scorer = get_scorer(a.model)
    readings = []
    with report.console.status("Reading global cues..."):
        for c in cues.DEFAULT_CUES:
            sig = _signal_for(c.name, [c.query], scorer, region="US" if c.name == "US markets" else "IN",
                              window="1d", per_query=12, half_life=8)
            readings.append(cues.CueReading(c, sig.score, sig.confidence, sig.n_articles, sig.headline))
    bias, tone = cues.opening_bias(readings)
    report.print_cues(readings, bias, tone)
    if a.notify:
        notify.send("Pre-market opening bias", f"{bias:+.2f} — {tone}")
    return 0


def cmd_query(a) -> int:
    scorer = get_scorer(a.model)
    sig = _signal_for(a.name or a.query[0], a.query, scorer, region=a.region, window=a.window,
                      per_query=a.limit, half_life=24)
    report.print_signals([sig], show_headlines=a.headlines)
    return 0


def cmd_size(a) -> int:
    p = sizing.size_position(a.capital, a.entry, a.stop, a.risk, a.target, a.max_pct)
    c = report.console
    c.print(f"[bold]Quantity:[/] {p.qty}")
    c.print(f"Capital used: ₹{p.capital_used:,.2f} ({p.pct_of_capital}% of account)")
    c.print(f"Max loss at stop: ₹{p.risk_amount:,.2f}  (₹{p.risk_per_share} per share)")
    if p.reward_risk is not None:
        c.print(f"Reward:risk = {p.reward_risk}")
    for w in p.warnings:
        c.print(f"[yellow]⚠ {w}[/]")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="newsscan", description="News sentiment, catalysts and global cues for traders.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="Scan every symbol in your watchlist config")
    s.add_argument("-c", "--config", help="Path to watchlist YAML (default: config/watchlist.yaml)")
    s.add_argument("-m", "--model", choices=["vader", "finbert", "ensemble"])
    s.add_argument("--headlines", type=int, default=2, help="Headlines to show per symbol (0 to hide)")
    s.add_argument("--markdown", help="Write a Markdown report to this path")
    s.add_argument("--json", help="Write JSON output to this path")
    s.add_argument("--db", default="data/history.db", help="SQLite history file")
    s.add_argument("--no-history", action="store_true", help="Don't read or write run history")
    s.add_argument("--notify", action="store_true", help="Push alerts when signals change (see README)")
    s.set_defaults(func=cmd_scan)

    c = sub.add_parser("cues", help="Pre-market: global cues → expected Indian opening bias")
    c.add_argument("-m", "--model", default="vader", choices=["vader", "finbert", "ensemble"])
    c.add_argument("--notify", action="store_true")
    c.set_defaults(func=cmd_cues)

    q = sub.add_parser("query", help="One-off scan for any search terms (e.g. 'gold price')")
    q.add_argument("query", nargs="+")
    q.add_argument("--name", help="Label for the output")
    q.add_argument("-m", "--model", default="vader", choices=["vader", "finbert", "ensemble"])
    q.add_argument("--region", default="IN")
    q.add_argument("--window", default="2d", help="Lookback, e.g. 1d, 7d")
    q.add_argument("--limit", type=int, default=15)
    q.add_argument("--headlines", type=int, default=5)
    q.set_defaults(func=cmd_query)

    z = sub.add_parser("size", help="Risk-based position size from entry and stop")
    z.add_argument("--capital", type=float, required=True)
    z.add_argument("--entry", type=float, required=True)
    z.add_argument("--stop", type=float, required=True)
    z.add_argument("--target", type=float)
    z.add_argument("--risk", type=float, default=1.0, help="Percent of capital to risk (default 1)")
    z.add_argument("--max-pct", type=float, default=25.0, help="Max position as %% of capital")
    z.set_defaults(func=cmd_size)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError) as e:
        report.console.print(f"[red]Error:[/] {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
