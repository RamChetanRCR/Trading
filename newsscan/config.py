"""Watchlist config loading.

Your real watchlist goes in ``config/watchlist.yaml`` (git-ignored). The committed
``config/watchlist.example.yaml`` is only a template.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_PATHS = [Path("config/watchlist.yaml"), Path("config/watchlist.example.yaml")]


@dataclass
class Symbol:
    symbol: str
    queries: list[str]


@dataclass
class Config:
    symbols: list[Symbol]
    region: str = "IN"
    window: str = "2d"
    per_query: int = 15
    half_life_hours: float = 24.0
    model: str = "vader"
    alerts: dict = field(default_factory=dict)


def load(path: str | Path | None = None) -> Config:
    if path is None:
        path = next((p for p in DEFAULT_PATHS if p.exists()), None)
        if path is None:
            raise FileNotFoundError("No config found. Copy config/watchlist.example.yaml to config/watchlist.yaml")
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    syms = []
    for item in raw.get("watchlist", []):
        if isinstance(item, str):
            syms.append(Symbol(item, [f"{item} share"]))
        else:
            name = item["symbol"]
            syms.append(Symbol(name, item.get("queries") or [f"{name} share"]))
    s = raw.get("settings", {})
    return Config(
        symbols=syms,
        region=s.get("region", "IN"),
        window=s.get("window", "2d"),
        per_query=int(s.get("per_query", 15)),
        half_life_hours=float(s.get("half_life_hours", 24)),
        model=s.get("model", "vader"),
        alerts=raw.get("alerts", {}),
    )
