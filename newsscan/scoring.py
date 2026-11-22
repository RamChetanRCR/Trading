"""Turn a pile of scored headlines into one signal per symbol."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import catalysts as cat
from .fetch import Article
from .sentiment import Scorer, label

CATALYST_WEIGHT = 0.15  # how far a bullish/bearish catalyst nudges a headline's polarity


@dataclass
class ScoredArticle:
    article: Article
    polarity: float
    adjusted: float
    weight: float
    catalysts: list[cat.Catalyst] = field(default_factory=list)


@dataclass
class Signal:
    symbol: str
    score: float  # recency-weighted, catalyst-adjusted polarity in [-1, 1]
    label: str
    confidence: float  # 0..1 — agreement between headlines x how much news there is
    n_articles: int
    positive: int
    negative: int
    neutral: int
    top_catalysts: list[str]
    items: list[ScoredArticle]

    @property
    def headline(self) -> str:
        return self.items[0].article.title if self.items else ""


def recency_weight(age_hours: float | None, half_life_hours: float) -> float:
    if age_hours is None:
        return 0.1  # unknown date could be months old: keep it visible but nearly weightless
    return 0.5 ** (age_hours / half_life_hours)


def score_articles(articles: list[Article], scorer: Scorer, half_life_hours: float = 24.0) -> list[ScoredArticle]:
    out = []
    for a in articles:
        p = scorer.score(a.title)
        tags = cat.tag(a.title)
        adj = max(-1.0, min(1.0, p + CATALYST_WEIGHT * cat.bias(tags)))
        a.tags = [c.tag for c in tags]
        out.append(ScoredArticle(a, p, adj, recency_weight(a.age_hours, half_life_hours), tags))
    return out


def aggregate(symbol: str, scored: list[ScoredArticle], threshold: float = 0.05) -> Signal:
    if not scored:
        return Signal(symbol, 0.0, "No news", 0.0, 0, 0, 0, 0, [], [])

    total_w = sum(s.weight for s in scored) or 1.0
    score = sum(s.adjusted * s.weight for s in scored) / total_w

    labels = [label(s.adjusted, threshold) for s in scored]
    pos, neg, neu = labels.count("Positive"), labels.count("Negative"), labels.count("Neutral")

    # Confidence (a heuristic, NOT a probability): recency-weighted share of headlines agreeing
    # with the overall direction x how much independent coverage there is. Coverage counts
    # distinct publishers, so one press release syndicated five times doesn't look like consensus.
    overall = label(score, threshold)
    agree = sum(s.weight for s, lb in zip(scored, labels) if lb == overall) / total_w
    publishers = len({s.article.source.lower() for s in scored if s.article.source}) or 1
    coverage = min(len(scored), publishers + 1)
    volume = 1 - math.exp(-coverage / 6)  # ~0.5 at 4 sources, ~0.8 at 10
    confidence = round(agree * volume, 2)

    counts: dict[str, int] = {}
    for s in scored:
        for c in s.catalysts:
            counts[c.tag] = counts.get(c.tag, 0) + 1
    top = [t for t, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:3]]

    ranked = sorted(scored, key=lambda s: abs(s.adjusted) * s.weight, reverse=True)
    return Signal(symbol, round(score, 3), label(score, threshold), confidence, len(scored),
                  pos, neg, neu, top, ranked)
