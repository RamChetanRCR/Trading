"""Console, Markdown and JSON output."""

from __future__ import annotations

import json
from datetime import datetime

from rich.console import Console
from rich.table import Table

from .cues import CueReading
from .history import Change
from .scoring import Signal

console = Console()

_COLOR = {"Positive": "green", "Negative": "red", "Neutral": "yellow", "No news": "dim"}


def _bar(score: float, width: int = 10) -> str:
    n = round(abs(score) * width)
    return ("▲" if score > 0 else "▼" if score < 0 else "·") * max(n, 1)


def print_signals(signals: list[Signal], show_headlines: int = 2) -> None:
    t = Table(title="News sentiment — watchlist", header_style="bold")
    for col in ("Symbol", "Signal", "Score", "Conf.", "News (+/-/0)", "Catalysts", "Top headline"):
        t.add_column(col, overflow="fold")
    for s in sorted(signals, key=lambda s: s.score, reverse=True):
        c = _COLOR.get(s.label, "white")
        t.add_row(s.symbol, f"[{c}]{s.label} {_bar(s.score)}[/]", f"{s.score:+.2f}", f"{s.confidence:.2f}",
                  f"{s.n_articles} ({s.positive}/{s.negative}/{s.neutral})", ", ".join(s.top_catalysts) or "—",
                  s.headline[:90])
    console.print(t)
    if show_headlines:
        for s in signals:
            if not s.items:
                continue
            console.print(f"\n[bold]{s.symbol}[/]")
            for it in s.items[:show_headlines]:
                tags = f" [cyan][{', '.join(it.article.tags)}][/]" if it.article.tags else ""
                console.print(f"  {it.adjusted:+.2f}  {it.article.title}{tags}  [dim]{it.article.source}[/]")


def print_cues(readings: list[CueReading], bias: float, tone: str) -> None:
    t = Table(title="Global cues → Indian market open", header_style="bold")
    for col in ("Cue", "Reading", "Impact on India", "Weight", "Top headline"):
        t.add_column(col, overflow="fold")
    for r in readings:
        c = "green" if r.impact > 0.05 else "red" if r.impact < -0.05 else "yellow"
        reading = (("▲ up" if r.score > 0 else "▼ down" if r.score < 0 else "· flat") + f" {r.score:+.2f}"
                   if r.cue.mode == "direction" else f"tone {r.score:+.2f}")
        t.add_row(r.cue.name, reading, f"[{c}]{r.impact:+.2f}[/]", f"{r.cue.weight:g}", r.headline[:90])
    console.print(t)
    c = "green" if bias > 0.08 else "red" if bias < -0.08 else "yellow"
    console.print(f"\n[bold]Opening backdrop:[/] [{c}]{bias:+.2f} — {tone}[/]")
    console.print("[dim]Heuristic from headlines, not a gap forecast. Confirm with live GIFT Nifty before acting.[/]")


def print_changes(changes: list[Change]) -> None:
    if not changes:
        console.print("[dim]No changes since last run.[/]")
        return
    console.print("[bold]Changes since last run[/]")
    for ch in changes:
        console.print(f"  • {ch.symbol}: {ch.kind} — {ch.detail}")


def _md(text: str) -> str:
    """Escape characters that break Markdown tables/links."""
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("[", "\\[").replace("]", "\\]").replace("\n", " ")


def to_markdown(signals: list[Signal], changes: list[Change] | None = None) -> str:
    lines = [f"# Watchlist sentiment — {datetime.now():%Y-%m-%d %H:%M}", "",
             "| Symbol | Signal | Score | Confidence | Articles | Catalysts |",
             "|---|---|---:|---:|---:|---|"]
    for s in sorted(signals, key=lambda s: s.score, reverse=True):
        lines.append(f"| {_md(s.symbol)} | {s.label} | {s.score:+.2f} | {s.confidence:.2f} | {s.n_articles} | "
                     f"{', '.join(s.top_catalysts) or '—'} |")
    if changes:
        lines += ["", "## Changes since last run", ""] + [f"- **{c.symbol}** {c.kind}: {c.detail}" for c in changes]
    for s in signals:
        if s.items:
            lines += ["", f"## {s.symbol}", ""]
            lines += [f"- {it.adjusted:+.2f} [{_md(it.article.title)}](<{it.article.link}>)" for it in s.items[:5]]
    return "\n".join(lines) + "\n"


def to_json(signals: list[Signal]) -> str:
    return json.dumps([
        {"symbol": s.symbol, "label": s.label, "score": s.score, "confidence": s.confidence,
         "articles": s.n_articles, "catalysts": s.top_catalysts,
         "headlines": [{"title": i.article.title, "source": i.article.source, "link": i.article.link,
                        "polarity": round(i.polarity, 3), "adjusted": round(i.adjusted, 3), "tags": i.article.tags}
                       for i in s.items[:10]]}
        for s in signals], indent=2)
