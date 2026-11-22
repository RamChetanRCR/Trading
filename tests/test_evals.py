"""Regression guard: CI fails if a change makes the models worse on the labelled eval set.

Thresholds sit just under the current scores (see evals/RESULTS.md). Raise them when you
genuinely improve the model; never lower them to make a change pass.
"""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("run_evals", Path(__file__).parent.parent / "evals" / "run_evals.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def test_sentiment_does_not_regress():
    results, _ = ev.run(models=("vader-plain", "vader"))
    tuned, plain = results[("built-in", "vader")], results[("built-in", "vader-plain")]
    assert tuned["macro_f1"] >= 0.77
    assert tuned["polarity_flips"] <= 10
    assert tuned["macro_f1"] > plain["macro_f1"] + 0.15  # the finance lexicon must keep earning its place


def test_catalyst_tagger_does_not_regress():
    _, cat = ev.run(models=("vader",))
    assert cat["precision"] >= 0.95 and cat["recall"] >= 0.90


def test_eval_set_is_well_formed():
    rows = ev.load_builtin()
    assert len(rows) >= 100 and {r["label"] for r in rows} == set(ev.LABELS)
    assert len({r["text"] for r in rows}) == len(rows)
