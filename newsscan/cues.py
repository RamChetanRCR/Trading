"""Global cues → news backdrop for the Indian market open.

Indian markets open after the US closes and while Asia is trading, so overnight news on
US indices, Asian markets, GIFT Nifty, FII flows, crude, the rupee and US yields is a decent
read on the opening tone.

Two kinds of cue:

* ``sentiment`` cues (GIFT Nifty, US, Asia, FII flows): the headline's tone is the signal.
* ``direction`` cues (crude, rupee, dollar, yields): tone is misleading — "rupee weakens"
  sounds negative *and is* negative for India, while "crude falls" sounds negative but is
  positive for India. So for these we detect which way the instrument moved and multiply by
  how that move affects Indian equities (``sign``).

The output is a heuristic *news backdrop*, not a calibrated gap forecast. Confirm with live
prices before acting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import scoring
from .fetch import Article
from .sentiment import Scorer

UP = re.compile(r"\b(rise[sn]?|rose|jumps?|jumped|surge[sd]?|climbs?|climbed|gains?|gained|higher|"
                r"strengthens?|strengthened|firms?|firmed|rall(y|ies|ied)|soars?|spikes?|spiked|"
                r"appreciates?|appreciated|up|record high|advances?)\b", re.I)
DOWN = re.compile(r"\b(falls?|fell|drops?|dropped|slips?|slipped|declines?|declined|lower|weakens?|"
                  r"weakened|eases?|eased|slides?|slid|tumbles?|tumbled|plunges?|plunged|sinks?|sank|"
                  r"down|depreciates?|depreciated|record low|retreats?|cools?)\b", re.I)


@dataclass(frozen=True)
class Cue:
    name: str
    query: str
    weight: float
    sign: int = 1  # effect on Indian equities of good news (sentiment) or an UP move (direction)
    mode: str = "sentiment"  # "sentiment" | "direction"
    subject: str = ""  # regex for the instrument, used in direction mode
    region: str = "IN"


DEFAULT_CUES: list[Cue] = [
    Cue("GIFT Nifty", "GIFT Nifty", 3.0),
    Cue("US markets", "Wall Street Dow Nasdaq S&P 500 close", 2.5, region="US"),
    Cue("Asian markets", "Asian markets Nikkei Hang Seng", 1.5),
    Cue("FII flows", "FII DII flows India", 1.5),
    Cue("Crude oil", "crude oil prices Brent", 1.0, sign=-1, mode="direction", subject=r"crude|brent|oil"),
    Cue("Rupee", "rupee vs dollar", 1.0, sign=+1, mode="direction", subject=r"rupee|inr"),
    Cue("US yields", "US Treasury yields", 0.75, sign=-1, mode="direction", subject=r"yields?|treasur(y|ies)"),
]


def move_direction(text: str, subject: str) -> int:
    """+1 if the subject instrument moved up, -1 if down, 0 if unclear.

    Looks for the first direction word within a few words *after* the subject, so
    "Rupee falls as dollar index rises" reads as rupee DOWN.
    """
    m = re.search(rf"\b({subject})\b", text, re.I)
    if not m:
        return 0
    window = " ".join(text[m.end():].split()[:6])
    up, down = UP.search(window), DOWN.search(window)
    if up and (not down or up.start() < down.start()):
        return 1
    if down:
        return -1
    return 0


@dataclass
class CueReading:
    cue: Cue
    score: float  # sentiment cues: tone; direction cues: net move (-1..1)
    confidence: float
    n: int
    headline: str

    @property
    def impact(self) -> float:
        return self.cue.sign * self.score


def read_cue(cue: Cue, articles: list[Article], scorer: Scorer) -> CueReading:
    scored = scoring.score_articles(articles, scorer, half_life_hours=8)
    sig = scoring.aggregate(cue.name, scored)
    if cue.mode == "sentiment" or not scored:
        return CueReading(cue, sig.score, sig.confidence, sig.n_articles, sig.headline)
    moves = [(move_direction(s.article.title, cue.subject), s.weight, s.article.title) for s in scored]
    known = [(d, w, t) for d, w, t in moves if d]
    if not known:
        return CueReading(cue, 0.0, 0.0, len(scored), scored[0].article.title)
    total = sum(w for _, w, _ in known)
    net = sum(d * w for d, w, _ in known) / total
    agree = sum(w for d, w, _ in known if d == (1 if net > 0 else -1)) / total
    top = max(known, key=lambda x: x[1])[2]
    return CueReading(cue, round(net, 3), round(agree * min(1.0, len(known) / 3), 2), len(scored), top)


def opening_bias(readings: list[CueReading]) -> tuple[float, str]:
    """Weighted impact across cues, scaled by each cue's confidence."""
    num = sum(r.impact * r.cue.weight * max(r.confidence, 0.1) for r in readings if r.n)
    den = sum(r.cue.weight * max(r.confidence, 0.1) for r in readings if r.n)
    if not den:
        return 0.0, "Unclear (no news)"
    b = num / den
    if b > 0.25:
        tone = "Strongly positive backdrop"
    elif b > 0.08:
        tone = "Mildly positive backdrop"
    elif b < -0.25:
        tone = "Strongly negative backdrop"
    elif b < -0.08:
        tone = "Mildly negative backdrop"
    else:
        tone = "Mixed / neutral backdrop"
    return round(b, 3), tone
