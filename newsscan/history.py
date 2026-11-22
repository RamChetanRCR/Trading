"""Local run history (SQLite) so you only get pinged when something actually changes.

The database lives in ./data/ by default, which is git-ignored — your scan history never
ends up in the repo.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .scoring import Signal

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    run_at TEXT NOT NULL,
    symbol TEXT NOT NULL,
    score REAL NOT NULL,
    label TEXT NOT NULL,
    confidence REAL NOT NULL,
    n_articles INTEGER NOT NULL,
    catalysts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sym_time ON signals(symbol, run_at);
"""


@dataclass
class Change:
    symbol: str
    kind: str  # "flip" | "jump" | "new_catalyst" | "new"
    detail: str


class History:
    def __init__(self, path: str | Path = "data/history.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.executescript(SCHEMA)

    def last(self, symbol: str) -> tuple | None:
        return self.db.execute(
            "SELECT score, label, catalysts FROM signals WHERE symbol=? ORDER BY run_at DESC LIMIT 1",
            (symbol,),
        ).fetchone()

    def save(self, signals: list[Signal], run_at: datetime | None = None) -> None:
        ts = (run_at or datetime.now(timezone.utc)).isoformat()
        self.db.executemany(
            "INSERT INTO signals VALUES (?,?,?,?,?,?,?)",
            [(ts, s.symbol, s.score, s.label, s.confidence, s.n_articles, ",".join(s.top_catalysts))
             for s in signals],
        )
        self.db.commit()

    def trend(self, symbol: str, limit: int = 10) -> list[tuple[str, float]]:
        rows = self.db.execute(
            "SELECT run_at, score FROM signals WHERE symbol=? ORDER BY run_at DESC LIMIT ?", (symbol, limit)
        ).fetchall()
        return list(reversed(rows))

    def close(self) -> None:
        self.db.close()


def diff(prev: tuple | None, sig: Signal, jump: float = 0.3) -> list[Change]:
    """Compare a new signal with the previous run's."""
    if sig.n_articles == 0:
        return []
    if prev is None:
        return [Change(sig.symbol, "new", f"first reading: {sig.label} ({sig.score:+.2f})")]
    p_score, p_label, p_cats = prev
    out = []
    if p_label != sig.label and "Neutral" not in (p_label, sig.label) and p_label != "No news":
        out.append(Change(sig.symbol, "flip", f"{p_label} → {sig.label}"))
    elif abs(sig.score - p_score) >= jump:
        out.append(Change(sig.symbol, "jump", f"{p_score:+.2f} → {sig.score:+.2f}"))
    new_cats = set(sig.top_catalysts) - set(filter(None, (p_cats or "").split(",")))
    if new_cats:
        out.append(Change(sig.symbol, "new_catalyst", ", ".join(sorted(new_cats))))
    return out
