"""Evaluate sentiment models and the catalyst tagger on a labelled headline set.

    python evals/run_evals.py                       # VADER baseline vs VADER+finance lexicon
    python evals/run_evals.py --models vader finbert ensemble   # needs requirements-finbert.txt
    python evals/run_evals.py --phrasebank          # also run on Financial PhraseBank (downloads it)

Labels are the expected effect on the stock (positive / negative / neutral). The built-in set
(evals/headlines.jsonl) is 110 hand-written headlines about FICTIONAL companies, including tricky
phrasing ("loss narrows", "cuts debt", "F&O ban list"). It was written by the same author as the
lexicon, so treat it as a regression guard, not an unbiased benchmark — Financial PhraseBank is
the independent check.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from newsscan import catalysts  # noqa: E402
from newsscan.sentiment import get_scorer, label  # noqa: E402

LABELS = ["positive", "negative", "neutral"]


def load_builtin() -> list[dict]:
    return [json.loads(l) for l in (ROOT / "evals" / "headlines.jsonl").read_text(encoding="utf-8").splitlines() if l]


def load_phrasebank() -> list[dict]:  # pragma: no cover - needs network
    try:
        from datasets import load_dataset
    except ImportError:
        sys.exit("pip install datasets  (Financial PhraseBank, CC BY-NC-SA 3.0, downloaded locally, never committed)")
    ds = load_dataset("takala/financial_phrasebank", "sentences_allagree", split="train", trust_remote_code=True)
    names = ds.features["label"].names  # ['negative', 'neutral', 'positive']
    return [{"text": r["sentence"], "label": names[r["label"]], "tags": None} for r in ds]


class PlainVader:
    """VADER with no finance lexicon — the baseline the custom lexicon has to beat."""
    name = "vader-plain"

    def __init__(self):
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        self.a = SentimentIntensityAnalyzer()

    def score(self, text):
        return self.a.polarity_scores(text)["compound"]


def sentiment_metrics(rows, scorer, threshold=0.05) -> dict:
    preds = [label(scorer.score(r["text"]), threshold).lower() for r in rows]
    gold = [r["label"] for r in rows]
    acc = sum(p == g for p, g in zip(preds, gold)) / len(rows)
    f1s = {}
    for c in LABELS:
        tp = sum(p == c == g for p, g in zip(preds, gold))
        fp = sum(p == c != g for p, g in zip(preds, gold))
        fn = sum(g == c != p for p, g in zip(preds, gold))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s[c] = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    confusion = Counter(zip(gold, preds))
    # The costly mistake for a trader: calling a negative headline positive or vice versa.
    flips = sum(1 for g, p in zip(gold, preds) if {g, p} == {"positive", "negative"})
    errors = [(r["text"], r["label"], p) for r, p in zip(rows, preds) if p != r["label"]]
    return {"n": len(rows), "accuracy": acc, "macro_f1": sum(f1s.values()) / 3, "f1": f1s,
            "polarity_flips": flips, "confusion": confusion, "errors": errors}


def catalyst_metrics(rows) -> dict:
    rows = [r for r in rows if r.get("tags") is not None]
    tp = fp = fn = 0
    per_tag: dict[str, Counter] = {}
    mistakes = []
    for r in rows:
        pred = {c.tag for c in catalysts.tag(r["text"])}
        gold = set(r["tags"])
        for t in pred | gold:
            c = per_tag.setdefault(t, Counter())
            c["tp" if t in pred and t in gold else "fp" if t in pred else "fn"] += 1
        tp, fp, fn = tp + len(pred & gold), fp + len(pred - gold), fn + len(gold - pred)
        if pred != gold:
            mistakes.append((r["text"], sorted(gold), sorted(pred)))
    p = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": p, "recall": rc, "f1": 2 * p * rc / (p + rc) if p + rc else 0.0,
            "per_tag": per_tag, "mistakes": mistakes}


def make_scorer(name):
    return PlainVader() if name == "vader-plain" else get_scorer(name)


def report(results: dict, cat: dict, show_errors: int) -> str:
    out = ["# Evaluation results", "", "## Sentiment (expected effect on the stock)", "",
           "| Dataset | Model | N | Accuracy | Macro-F1 | F1 pos / neg / neu | Pos↔Neg flips |",
           "|---|---|---:|---:|---:|---|---:|"]
    for (ds, model), m in results.items():
        f = m["f1"]
        out.append(f"| {ds} | {model} | {m['n']} | {m['accuracy']:.1%} | {m['macro_f1']:.3f} | "
                   f"{f['positive']:.2f} / {f['negative']:.2f} / {f['neutral']:.2f} | {m['polarity_flips']} |")
    out += ["", "*Pos↔Neg flips* = headlines scored in the opposite direction — the expensive mistake.", "",
            "## Catalyst tagger (built-in set)", "",
            f"Micro precision **{cat['precision']:.2f}** · recall **{cat['recall']:.2f}** · F1 **{cat['f1']:.2f}**", "",
            "| Tag | TP | FP | FN |", "|---|---:|---:|---:|"]
    for t, c in sorted(cat["per_tag"].items()):
        out.append(f"| {t} | {c['tp']} | {c['fp']} | {c['fn']} |")
    if show_errors:
        for (ds, model), m in results.items():
            if ds == "built-in" and m["errors"]:
                out += ["", f"### Misclassified by `{model}` (first {show_errors})", ""]
                out += [f"- gold **{g}**, got *{p}*: {t}" for t, g, p in m["errors"][:show_errors]]
        if cat["mistakes"]:
            out += ["", "### Catalyst mismatches", ""]
            out += [f"- expected {g or '—'}, got {p or '—'}: {t}" for t, g, p in cat["mistakes"]]
    return "\n".join(out) + "\n"


def run(models=("vader-plain", "vader"), phrasebank=False):
    data = {"built-in": load_builtin()}
    if phrasebank:
        data["PhraseBank (all-agree)"] = load_phrasebank()
    results = {(ds, m): sentiment_metrics(rows, make_scorer(m)) for ds, rows in data.items() for m in models}
    return results, catalyst_metrics(data["built-in"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["vader-plain", "vader"],
                    choices=["vader-plain", "vader", "finbert", "ensemble"])
    ap.add_argument("--phrasebank", action="store_true")
    ap.add_argument("--errors", type=int, default=15, help="Misclassified examples to list")
    ap.add_argument("-o", "--out", help="Also write the Markdown report here")
    a = ap.parse_args()
    results, cat = run(a.models, a.phrasebank)
    md = report(results, cat, a.errors)
    print(md)
    if a.out:
        Path(a.out).write_text(md, encoding="utf-8")


if __name__ == "__main__":
    main()
