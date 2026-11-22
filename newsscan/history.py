"""Local run history (SQLite) so you only get pinged when something actually changes.

The database lives in ./data/ by default, which is git-ignored — your scan history never
ends up in the repo.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .scoring import Signal

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    symbol TEXT NOT NULL,
    score REAL NOT NULL,
    label TEXT NOT NULL,
    confidence REAL NOT NULL,
    n_articles INTEGER NOT NULL,
    catalysts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sym_time ON signals(symbol, run_at);
CREATE TABLE IF NOT EXISTS seen_articles (
    symbol TEXT NOT NULL,
    key TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    PRIMARY KEY (symbol, key)
);
"""


def article_key(title: str) -> str:
    return hashlib.sha1(" ".join(title.lower().split()).encode()).hexdigest()[:16]


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
        cols = [r[1] for r in self.db.execute("PRAGMA table_info(signals)")]
        if cols and "id" not in cols:  # v2.0 database without an id column: migrate in place
            self.db.executescript("ALTER TABLE signals RENAME TO signals_old;")
            self.db.executescript(SCHEMA)
            self.db.execute("INSERT INTO signals (run_at, symbol, score, label, confidence, n_articles, catalysts) "
                            "SELECT * FROM signals_old")
            self.db.executescript("DROP TABLE signals_old;")
        self.db.executescript(SCHEMA)

    def last(self, symbol: str) -> tuple | None:
        return self.db.execute(
            "SELECT score, label, catalysts FROM signals WHERE symbol=? ORDER BY run_at DESC, id DESC LIMIT 1",
            (symbol,),
        ).fetchone()

    def save(self, signals: list[Signal], run_at: datetime | None = None) -> None:
        ts = (run_at or datetime.now(timezone.utc)).isoformat()
        self.db.executemany(
            "INSERT INTO signals (run_at, symbol, score, label, confidence, n_articles, catalysts) "
            "VALUES (?,?,?,?,?,?,?)",
            [(ts, s.symbol, s.score, s.label, s.confidence, s.n_articles, ",".join(s.top_catalysts))
             for s in signals],
        )
        self.db.commit()

    def mark_seen(self, signal: Signal) -> int:
        """Record this signal's headlines; return how many were never seen before."""
        ts = datetime.now(timezone.utc).isoformat()
        new = 0
        for it in signal.items:
            cur = self.db.execute("INSERT OR IGNORE INTO seen_articles VALUES (?,?,?)",
                                  (signal.symbol, article_key(it.article.title), ts))
            new += cur.rowcount
        self.db.commit()
        return new

    def prune(self, keep_days: int = 90) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).isoformat()
        self.db.execute("DELETE FROM signals WHERE run_at < ?", (cutoff,))
        self.db.execute("DELETE FROM seen_articles WHERE first_seen < ?", (cutoff,))
        self.db.commit()

    def trend(self, symbol: str, limit: int = 10) -> list[tuple[str, float]]:
        rows = self.db.execute(
            "SELECT run_at, score FROM signals WHERE symbol=? ORDER BY run_at DESC, id DESC LIMIT ?", (symbol, limit)
        ).fetchall()
        return list(reversed(rows))

    def close(self) -> None:
        self.db.close()


def diff(prev: tuple | None, sig: Signal, jump: float = 0.3, new_articles: int | None = None) -> list[Change]:
    """Compare a new signal with the previous run's.

    If ``new_articles`` is 0 (every headline was already seen in an earlier run), nothing is
    reported: a score can drift as headlines age, but that isn't new information.
    """
    if sig.n_articles == 0 or new_articles == 0:
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
