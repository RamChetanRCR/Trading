"""Global cues → expected opening bias for Indian markets.

Indian markets open after the US closes and while Asia is trading, so overnight news on
US indices, Asian markets, GIFT Nifty, crude, the dollar and FII flows is a decent read
on the opening tone. This module turns that news into one weighted "opening bias".

Each cue has a weight (how much it usually matters) and a sign: for crude oil and the dollar,
*rising* is bad for India (import bill, FII outflows), so their sentiment is inverted.
Inversion is approximate — "crude falls" reads as negative text but is good for India, which
is exactly what the sign flip captures.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Cue:
    name: str
    query: str
    weight: float
    sign: int = 1  # -1 = good news for this cue is bad for Indian equities


DEFAULT_CUES: list[Cue] = [
    Cue("GIFT Nifty", "GIFT Nifty", 3.0),
    Cue("US markets", "Wall Street Dow Nasdaq S&P 500 close", 2.5),
    Cue("Asian markets", "Asian markets Nikkei Hang Seng", 1.5),
    Cue("FII flows", "FII DII flows India", 1.5),
    Cue("Crude oil", "crude oil prices Brent", 1.0, sign=-1),
    Cue("Dollar / rupee", "dollar index rupee", 1.0, sign=-1),
    Cue("US yields", "US Treasury yields", 0.75, sign=-1),
]


@dataclass
class CueReading:
    cue: Cue
    score: float
    confidence: float
    n: int
    headline: str

    @property
    def impact(self) -> float:
        return self.cue.sign * self.score


def opening_bias(readings: list[CueReading]) -> tuple[float, str]:
    """Weighted impact across cues, scaled by each cue's confidence."""
    num = sum(r.impact * r.cue.weight * max(r.confidence, 0.1) for r in readings if r.n)
    den = sum(r.cue.weight * max(r.confidence, 0.1) for r in readings if r.n)
    if not den:
        return 0.0, "Unclear (no news)"
    b = num / den
    if b > 0.25:
        tone = "Gap-up likely"
    elif b > 0.08:
        tone = "Mildly positive open"
    elif b < -0.25:
        tone = "Gap-down likely"
    elif b < -0.08:
        tone = "Mildly negative open"
    else:
        tone = "Flat / mixed open"
    return round(b, 3), tone
