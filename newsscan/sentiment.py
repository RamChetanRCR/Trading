"""Sentiment scorers. All return a polarity in [-1, 1].

* ``vader``   — fast lexicon model, no download, default.
* ``finbert`` — finance-tuned transformer (yiyanghkust/finbert-tone). Optional; loaded lazily
                so the CLI starts instantly when you don't use it.
* ``ensemble``— average of both, falls back to VADER if FinBERT isn't installed.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Protocol

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Finance words VADER's general lexicon gets wrong or misses entirely.
# Single tokens only — VADER tokenises on whitespace. Multi-word phrases go in FINANCE_PHRASES.
FINANCE_LEXICON = {
    # Neutralise words that are positive in everyday English but neutral in market news.
    "share": 0.0, "shares": 0.0, "stock": 0.0, "stocks": 0.0, "interest": 0.0, "trust": 0.0,
    "credit": 0.0, "bond": 0.0, "bonds": 0.0, "security": 0.0, "securities": 0.0, "fund": 0.0,
    "funds": 0.0,
    # Index / company names that VADER reads as sentiment words (Nifty, GIFT Nifty, Yes Bank,
    # Hero MotoCorp, United Spirits, Care Ratings, Tata Power, Adani Energy, block deals...).
    "nifty": 0.0, "gift": 0.0, "yes": 0.0, "hero": 0.0, "united": 0.0, "care": 0.0, "energy": 0.0,
    "super": 0.0, "fine": 0.0, "free": 0.0, "block": 0.0, "flat": 0.0, "bonus": 0.4,
    # Up moves
    "surge": 2.0, "surges": 2.0, "surged": 2.0, "soar": 2.2, "soars": 2.2, "rally": 1.8, "rallies": 1.8,
    "jumps": 1.6, "jump": 1.4, "climbs": 1.3, "rises": 1.2, "rise": 1.0, "rose": 1.0, "gains": 1.4,
    "higher": 1.0, "advances": 1.2, "rebounds": 1.4, "beats": 1.8, "upgrade": 1.8, "upgrades": 1.8,
    "upgraded": 1.8, "outperform": 1.6, "bullish": 2.0, "buyback": 1.4, "inflows": 1.4, "netbuyers": 1.6,
    "recordhigh": 1.8, "orderwin": 1.8,
    # Down moves
    "plunge": -2.2, "plunges": -2.2, "plunged": -2.2, "slump": -2.0, "slumps": -2.0, "tumbles": -2.0,
    "tumble": -2.0, "crash": -2.6, "crashes": -2.6, "sinks": -1.8, "slides": -1.5, "falls": -1.4,
    "fall": -1.2, "fell": -1.3, "slips": -1.3, "slip": -1.3, "declines": -1.3, "decline": -1.2,
    "drops": -1.3, "dropped": -1.3, "sheds": -1.4, "lower": -1.0, "misses": -1.8, "downgrade": -1.8,
    "downgrades": -1.8, "downgraded": -1.8, "bearish": -2.0, "underperform": -1.6, "selloff": -2.0,
    "sell-off": -2.0, "outflows": -1.4, "netsellers": -1.6, "probe": -1.4, "penalty": -1.6,
    "default": -2.2, "fraud": -2.8, "resigns": -1.2, "pledge": -0.8, "pledged": -0.8,
}

# Phrases collapsed into single tokens before scoring so VADER can see them.
FINANCE_PHRASES = {
    "net buyers": "netbuyers", "net buyer": "netbuyers", "net sellers": "netsellers",
    "net seller": "netsellers", "record high": "recordhigh", "all-time high": "recordhigh",
    "order win": "orderwin", "pull out": "outflows", "pulled out": "outflows",
}


class Scorer(Protocol):
    name: str

    def score(self, text: str) -> float: ...


class VaderScorer:
    name = "vader"

    def __init__(self) -> None:
        self._a = SentimentIntensityAnalyzer()
        for word, val in FINANCE_LEXICON.items():
            if val == 0.0:
                # Remove rather than set to 0: VADER's caps rule turns an ALL-CAPS 0-valence word
                # (e.g. "GIFT Nifty", "YES Bank") into a -0.73 hit.
                self._a.lexicon.pop(word, None)
            else:
                self._a.lexicon[word] = val

    def score(self, text: str) -> float:
        t = text or ""
        low = t.lower()
        for phrase, token in FINANCE_PHRASES.items():
            if phrase in low:
                t = re.sub(re.escape(phrase), token, t, flags=re.I)
                low = t.lower()
        return float(self._a.polarity_scores(t)["compound"])


class FinbertScorer:
    name = "finbert"
    MODEL = "yiyanghkust/finbert-tone"

    def __init__(self) -> None:
        try:
            import torch  # noqa: F401
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as e:  # pragma: no cover - optional dependency
            raise RuntimeError("FinBERT needs extras: pip install -r requirements-finbert.txt") from e
        self._tok = AutoTokenizer.from_pretrained(self.MODEL)
        self._model = AutoModelForSequenceClassification.from_pretrained(self.MODEL)
        self._model.eval()

    def score(self, text: str) -> float:  # pragma: no cover - needs model download
        import torch

        if not text.strip():
            return 0.0
        inputs = self._tok(text, return_tensors="pt", truncation=True, max_length=128)
        with torch.no_grad():
            probs = torch.softmax(self._model(**inputs).logits, dim=1)[0].tolist()
        # Read label order from the model config instead of hard-coding it
        # (finbert-tone is 0=Neutral, 1=Positive, 2=Negative).
        by_label = {self._model.config.id2label[i].lower(): p for i, p in enumerate(probs)}
        return float(by_label.get("positive", 0.0) - by_label.get("negative", 0.0))


class EnsembleScorer:
    name = "ensemble"

    def __init__(self) -> None:
        self._scorers: list[Scorer] = [VaderScorer()]
        try:
            self._scorers.append(FinbertScorer())
        except RuntimeError:
            pass

    def score(self, text: str) -> float:
        return sum(s.score(text) for s in self._scorers) / len(self._scorers)


@lru_cache(maxsize=None)
def get_scorer(name: str = "vader") -> Scorer:
    name = name.lower()
    if name == "vader":
        return VaderScorer()
    if name == "finbert":
        return FinbertScorer()
    if name == "ensemble":
        return EnsembleScorer()
    raise ValueError(f"Unknown model '{name}'. Use vader, finbert or ensemble.")


def label(polarity: float, threshold: float = 0.05) -> str:
    if polarity > threshold:
        return "Positive"
    if polarity < -threshold:
        return "Negative"
    return "Neutral"
