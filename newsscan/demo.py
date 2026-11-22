"""Offline demo data: fictional companies and made-up headlines.

Used by `newsscan demo` so anyone can try the tool without internet, and to record the
README animation reproducibly. None of this is real news or anyone's real watchlist.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .cues import DEFAULT_CUES
from .fetch import Article

# (hours ago, headline, publisher)
_SYMBOLS: dict[str, list[tuple[float, str, str]]] = {
    "ALPHAINFRA": [
        (2, "Alpha Infra bags Rs 1,200 crore metro rail order", "Demo Times"),
        (5, "Broker upgrades Alpha Infra to buy, raises target price", "Demo Markets"),
        (9, "Alpha Infra shares surge to record high on strong order book", "Demo Wire"),
        (20, "Alpha Infra Q2 results: net profit jumps 28%", "Demo Daily"),
    ],
    "BETAPOWER": [
        (3, "Beta Power announces new plant, capacity expansion of 500 MW", "Demo Wire"),
        (14, "Beta Power shares slip as coal costs rise", "Demo Times"),
        (30, "Beta Power Q2 results in line with estimates", "Demo Markets"),
    ],
    "GAMMAPHARMA": [
        (1, "SEBI issues show-cause notice to Gamma Pharma promoter", "Demo Daily"),
        (4, "Gamma Pharma shares plunge 8% after US FDA warning letter", "Demo Wire"),
        (11, "Anchor investor lock-in ends for Gamma Pharma this week", "Demo Times"),
        (26, "Broker downgrades Gamma Pharma, cuts target", "Demo Markets"),
    ],
    "DELTABANK": [
        (6, "Delta Bank Q2 results: net profit up 12%, asset quality stable", "Demo Markets"),
        (18, "Delta Bank board approves dividend, record date set", "Demo Daily"),
    ],
}

# Headlines that "arrive" before the second demo run, to show change detection.
NEXT_RUN: dict[str, list[tuple[float, str, str]]] = {
    "BETAPOWER": [(0.5, "Beta Power bags Rs 900 crore order from state utility; shares jump 6%", "Demo Wire"),
                  (0.3, "Broker upgrades Beta Power to buy after order win", "Demo Markets")],
    "GAMMAPHARMA": [(0.4, "Gamma Pharma promoter pledges additional 5% stake", "Demo Daily")],
}

_CUES: dict[str, list[tuple[float, str, str]]] = {
    "GIFT Nifty": [(1, "GIFT Nifty trades 90 points higher, signals positive start", "Demo Wire")],
    "US markets": [(6, "Wall Street rallies as Nasdaq gains 1.4% on tech surge", "Demo Times")],
    "Asian markets": [(1, "Asian markets mixed; Nikkei gains, Hang Seng slips", "Demo Markets")],
    "FII flows": [(10, "FIIs turn net buyers, invest Rs 2,100 crore in Indian equities", "Demo Daily")],
    "Crude oil": [(4, "Crude oil falls 2% as supply concerns ease", "Demo Wire")],
    "Rupee": [(3, "Rupee rises 12 paise against the dollar as dollar index slips", "Demo Times")],
    "US yields": [(5, "US Treasury yields edge lower", "Demo Markets")],
}


def _articles(rows, query: str) -> list[Article]:
    now = datetime.now(timezone.utc)
    return [Article(title=t, link="https://example.com/demo", source=s,
                    published=now - timedelta(hours=h), query=query) for h, t, s in rows]


def symbols() -> list[str]:
    return list(_SYMBOLS)


def symbol_articles(symbol: str) -> list[Article]:
    return _articles(_SYMBOLS[symbol], symbol)


def next_run_articles(symbol: str) -> list[Article]:
    return _articles(_SYMBOLS[symbol] + NEXT_RUN.get(symbol, []), symbol)


def cue_articles(cue_name: str) -> list[Article]:
    return _articles(_CUES.get(cue_name, []), cue_name)


assert set(_CUES) == {c.name for c in DEFAULT_CUES}
