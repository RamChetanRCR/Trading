"""Sentiment scorers. All return a polarity in [-1, 1].

* ``vader``   — fast lexicon model, no download, default.
* ``finbert`` — finance-tuned transformer (yiyanghkust/finbert-tone). Optional; loaded lazily
                so the CLI starts instantly when you don't use it.
* ``ensemble``— average of both, falls back to VADER if FinBERT isn't installed.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Finance words VADER's general lexicon gets wrong or misses entirely.
FINANCE_LEXICON = {
    "surge": 2.0, "surges": 2.0, "soar": 2.2, "soars": 2.2, "rally": 1.8, "rallies": 1.8,
    "jumps": 1.6, "gains": 1.4, "beats": 1.8, "upgrade": 1.8, "upgraded": 1.8, "outperform": 1.6,
    "bullish": 2.0, "record high": 1.8, "buyback": 1.4, "order win": 1.8,
    "plunge": -2.2, "plunges": -2.2, "slump": -2.0, "slumps": -2.0, "tumbles": -2.0, "crash": -2.6,
    "falls": -1.4, "slips": -1.2, "misses": -1.8, "downgrade": -1.8, "downgraded": -1.8,
    "bearish": -2.0, "underperform": -1.6, "selloff": -2.0, "sell-off": -2.0, "probe": -1.4,
    "penalty": -1.6, "default": -2.2, "fraud": -2.8, "resigns": -1.2, "pledge": -0.8,
}


class Scorer(Protocol):
    name: str

    def score(self, text: str) -> float: ...


class VaderScorer:
    name = "vader"

    def __init__(self) -> None:
        self._a = SentimentIntensityAnalyzer()
        self._a.lexicon.update({k: v for k, v in FINANCE_LEXICON.items() if " " not in k})

    def score(self, text: str) -> float:
        return float(self._a.polarity_scores(text or "")["compound"])


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
