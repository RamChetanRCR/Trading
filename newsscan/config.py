"""Watchlist config loading.

Your real watchlist goes in ``config/watchlist.yaml`` (git-ignored). The committed
``config/watchlist.example.yaml`` is only a template.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_PATHS = [Path("config/watchlist.yaml"), Path("config/watchlist.example.yaml")]


@dataclass
class Symbol:
    symbol: str
    queries: list[str]
    match: list[str] = field(default_factory=list)  # headline must contain one of these, if set


@dataclass
class Config:
    symbols: list[Symbol]
    region: str = "IN"
    window: str = "2d"
    per_query: int = 15
    half_life_hours: float = 24.0
    model: str = "vader"
    alerts: dict = field(default_factory=dict)


class ConfigError(ValueError):
    pass


def _str_list(v, where: str) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
        raise ConfigError(f"{where} must be a list of non-empty strings")
    return [x.strip() for x in v]


def load(path: str | Path | None = None) -> Config:
    if path is None:
        path = next((p for p in DEFAULT_PATHS if p.exists()), None)
        if path is None:
            raise FileNotFoundError("No config found. Copy config/watchlist.example.yaml to config/watchlist.yaml")
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: invalid YAML ({e})") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top level must be a mapping with a 'watchlist' key")

    items = raw.get("watchlist")
    if not items or not isinstance(items, list):
        raise ConfigError(f"{path}: 'watchlist' must be a non-empty list")
    syms, seen = [], set()
    for n, item in enumerate(items, 1):
        where = f"{path}: watchlist item {n}"
        if isinstance(item, str):
            name, queries, match = item.strip(), [], []
        elif isinstance(item, dict):
            name = str(item.get("symbol", "")).strip()
            queries = _str_list(item.get("queries"), f"{where} 'queries'")
            match = _str_list(item.get("match"), f"{where} 'match'")
        else:
            raise ConfigError(f"{where}: must be a symbol string or a mapping with 'symbol'")
        if not name:
            raise ConfigError(f"{where}: missing 'symbol'")
        if name.upper() in seen:
            raise ConfigError(f"{where}: duplicate symbol '{name}'")
        seen.add(name.upper())
        syms.append(Symbol(name, queries or [f"{name} share"], match))

    s = raw.get("settings") or {}
    model = str(s.get("model", "vader")).lower()
    if model not in ("vader", "finbert", "ensemble"):
        raise ConfigError(f"settings.model must be vader, finbert or ensemble (got '{model}')")
    try:
        per_query = int(s.get("per_query", 15))
        half_life = float(s.get("half_life_hours", 24))
    except (TypeError, ValueError) as e:
        raise ConfigError(f"settings: per_query must be an integer and half_life_hours a number ({e})") from e
    if not 1 <= per_query <= 100:
        raise ConfigError("settings.per_query must be between 1 and 100")
    if half_life <= 0:
        raise ConfigError("settings.half_life_hours must be > 0")
    window = str(s.get("window", "2d"))
    if not re.fullmatch(r"\d+[hdm]", window):
        raise ConfigError(f"settings.window must look like 12h, 2d or 1m (got '{window}')")
    region = str(s.get("region", "IN")).upper()
    if not re.fullmatch(r"[A-Z]{2}", region):
        raise ConfigError(f"settings.region must be a 2-letter country code (got '{region}')")
    alerts = raw.get("alerts") or {}
    if not isinstance(alerts, dict):
        raise ConfigError("alerts must be a mapping")

    return Config(symbols=syms, region=region, window=window, per_query=per_query,
                  half_life_hours=half_life, model=model, alerts=alerts)
