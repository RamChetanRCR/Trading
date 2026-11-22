from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import pytest

from newsscan import catalysts, cues, fetch, history, scoring, sizing
from newsscan.cli import main
from newsscan.config import load
from newsscan.sentiment import get_scorer, label

FIXTURE = Path(__file__).parent / "fixtures" / "sample_feed.xml"


@pytest.fixture
def articles():
    return fetch.parse_feed(feedparser.parse(FIXTURE.read_text()), query="ACME")


def test_parse_splits_publisher(articles):
    assert articles[0].title == "Acme Ltd shares surge after company bags Rs 500 crore order"
    assert articles[0].source == "Example Times"
    assert articles[0].published.tzinfo is not None


def test_dedupe_keeps_newest(articles):
    d = fetch.dedupe(articles)
    assert len(d) == 3
    assert d[0].source == "Example Times"  # the 04:00 copy beats the 02:00 copy


def test_vader_finance_lexicon():
    s = get_scorer("vader")
    assert s.score("Acme shares surge to record high") > 0.3
    assert s.score("Acme shares plunge after fraud probe") < -0.3
    assert label(0.0) == "Neutral"


@pytest.mark.parametrize("text,tag", [
    ("Acme bags Rs 500 crore order from railways", "order_win"),
    ("Broker upgrades Acme, raises target", "rating_up"),
    ("Acme Q2 results: net profit up 20%", "results"),
    ("Anchor lock-in ends for Acme today", "lock_in"),
    ("SEBI slaps penalty on Acme", "regulatory"),
    ("US FDA issues warning letter to Acme plant", "regulatory"),
    ("Acme CEO resigns with immediate effect", "management"),
    ("Acme announces buyback at premium", "corporate_action"),
])
def test_catalyst_tags(text, tag):
    assert tag in [c.tag for c in catalysts.tag(text)]


def test_aggregate_signal(articles):
    scored = scoring.score_articles(fetch.dedupe(articles), get_scorer("vader"))
    sig = scoring.aggregate("ACME", scored)
    assert sig.n_articles == 3
    assert sig.label == "Positive"
    assert 0 < sig.confidence <= 1
    assert "order_win" in sig.top_catalysts


def test_empty_aggregate():
    sig = scoring.aggregate("NONE", [])
    assert sig.label == "No news" and sig.n_articles == 0


def test_recency_weight_halves():
    assert scoring.recency_weight(0, 24) == 1
    assert scoring.recency_weight(24, 24) == pytest.approx(0.5)
    assert scoring.recency_weight(None, 24) == 0.1


def test_opening_bias_inverts_crude():
    crude = cues.Cue("Crude", "crude", 1.0, sign=-1, mode="direction", subject="crude")
    us = cues.Cue("US", "us", 1.0)
    # Crude rallying (positive news) is negative for India.
    b, tone = cues.opening_bias([cues.CueReading(crude, 0.8, 1.0, 5, "")])
    assert b == pytest.approx(-0.8) and tone == "Strongly negative backdrop"
    b, _ = cues.opening_bias([cues.CueReading(us, 0.6, 1.0, 5, ""), cues.CueReading(crude, -0.4, 1.0, 5, "")])
    assert b > 0.25
    assert cues.opening_bias([])[1].startswith("Unclear")


def _sig(sym, score, lbl, cats=()):
    return scoring.Signal(sym, score, lbl, 0.5, 5, 3, 1, 1, list(cats), [])


def test_history_diff(tmp_path):
    h = history.History(tmp_path / "h.db")
    s1 = _sig("ACME", 0.4, "Positive", ["results"])
    assert history.diff(h.last("ACME"), s1)[0].kind == "new"
    h.save([s1], run_at=datetime.now(timezone.utc) - timedelta(hours=1))
    s2 = _sig("ACME", -0.3, "Negative", ["results", "regulatory"])
    kinds = {c.kind for c in history.diff(h.last("ACME"), s2)}
    assert kinds == {"flip", "new_catalyst"}
    h.save([s2])
    assert len(h.trend("ACME")) == 2
    assert history.diff(h.last("ACME"), _sig("ACME", -0.32, "Negative", ["results", "regulatory"])) == []
    h.close()


def test_position_size_long():
    p = sizing.size_position(capital=100_000, entry=500, stop=480, risk_pct=1, target=560)
    assert p.qty == 50  # ₹1,000 risk / ₹20 per share
    assert p.risk_amount == 1000.0 and p.capital_used == 25_000
    assert p.reward_risk == 3.0 and not p.warnings


def test_position_size_caps_tight_stop():
    p = sizing.size_position(capital=100_000, entry=1000, stop=999, risk_pct=1, max_position_pct=20)
    assert p.qty == 20 and p.warnings


def test_position_size_short_and_errors():
    p = sizing.size_position(capital=50_000, entry=200, stop=206, risk_pct=1, target=188, side="short")
    assert p.qty == 62  # 83 by risk, capped to 25% of capital (₹12,500 / ₹200)
    assert p.reward_risk == 2.0
    with pytest.raises(ValueError):
        sizing.size_position(100_000, 100, 100)
    with pytest.raises(ValueError, match="stop must be below"):
        sizing.size_position(100_000, 500, 520, target=560)  # long with stop above entry
    with pytest.raises(ValueError, match="target must be above"):
        sizing.size_position(100_000, 500, 480, target=450)


def test_example_config_loads():
    cfg = load(Path(__file__).parent.parent / "config" / "watchlist.example.yaml")
    assert cfg.symbols and all(s.queries for s in cfg.symbols)


def test_cli_size(capsys):
    assert main(["size", "--capital", "100000", "--entry", "500", "--stop", "490"]) == 0
    assert "Quantity" in capsys.readouterr().out


def test_cli_scan_end_to_end(tmp_path, monkeypatch, articles):
    """Full scan with the network stubbed out: table, markdown, json and history all work."""
    cfg = tmp_path / "w.yaml"
    cfg.write_text("watchlist:\n  - symbol: ACME\n    queries: ['Acme share']\n")
    monkeypatch.setattr(fetch, "fetch_news", lambda *a, **k: list(articles))
    md, js, db = tmp_path / "r.md", tmp_path / "r.json", tmp_path / "h.db"
    args = ["scan", "-c", str(cfg), "--markdown", str(md), "--json", str(js), "--db", str(db)]
    assert main(args) == 0
    assert "| ACME | Positive |" in md.read_text()
    assert '"symbol": "ACME"' in js.read_text()
    assert main(args) == 0  # second run reads history without error
    h = history.History(db)
    assert len(h.trend("ACME")) == 2
    h.close()


@pytest.mark.parametrize("text", ["SEBI approves Acme IPO", "RBI keeps repo rate unchanged",
                                  "Acme Q2 profit rises 10%"])
def test_no_false_regulatory_tag(text):
    assert "regulatory" not in [c.tag for c in catalysts.tag(text)]


def test_finance_lexicon_fixes():
    s = get_scorer("vader")
    assert s.score("Acme shares slip as costs rise") < 0      # "shares" is not "to share"
    assert s.score("GIFT Nifty trades flat") == 0               # names aren't sentiment words
    assert s.score("YES Bank shares fall") < 0
    assert s.score("FIIs turn net buyers") > 0 > s.score("FIIs turn net sellers")


def test_timestamps_are_utc_regardless_of_local_tz(monkeypatch, articles):
    import time
    monkeypatch.setenv("TZ", "Asia/Kolkata")
    time.tzset()
    try:
        arts = fetch.parse_feed(feedparser.parse(FIXTURE.read_text()))
        assert arts[0].published == datetime(2026, 11, 22, 4, 0, tzinfo=timezone.utc)
    finally:
        monkeypatch.delenv("TZ")
        time.tzset()


@pytest.mark.parametrize("text,subject,expected", [
    ("Rupee falls as dollar index rises", "rupee", -1),    # subject-aware: rupee moved DOWN
    ("Rupee strengthens against the dollar", "rupee", 1),
    ("Brent crude jumps on supply disruption", "crude|brent", 1),
    ("Crude oil falls 2% as supply concerns ease", "crude|oil", -1),
    ("Rupee steady in early trade", "rupee", 0),
])
def test_move_direction(text, subject, expected):
    assert cues.move_direction(text, subject) == expected


def test_direction_cue_uses_move_not_tone():
    rupee = next(c for c in cues.DEFAULT_CUES if c.name == "Rupee")
    weak = [fetch.Article("Rupee weakens to record low against dollar",
                          published=datetime.now(timezone.utc), source="X")]
    r = cues.read_cue(rupee, weak, get_scorer("vader"))
    assert r.impact < 0  # a weaker rupee is bad for Indian equities, not "inverted good"
    crude = next(c for c in cues.DEFAULT_CUES if c.name == "Crude oil")
    up = [fetch.Article("Brent crude surges 4% on Middle East supply fears",
                        published=datetime.now(timezone.utc), source="X")]
    assert cues.read_cue(crude, up, get_scorer("vader")).impact < 0


def test_history_ignores_already_seen_headlines(tmp_path, articles):
    h = history.History(tmp_path / "h.db")
    sig = scoring.aggregate("ACME", scoring.score_articles(fetch.dedupe(articles), get_scorer("vader")))
    assert h.mark_seen(sig) == 3
    assert h.mark_seen(sig) == 0
    assert history.diff(("0.9", "Negative", ""), sig, new_articles=0) == []
    h.close()


@pytest.mark.parametrize("yaml_text,msg", [
    ("watchlist: []", "non-empty list"),
    ("watchlist:\n  - symbol: ''", "missing 'symbol'"),
    ("watchlist: [A, a]", "duplicate"),
    ("settings: {model: gpt}\nwatchlist: [A]", "settings.model"),
    ("settings: {half_life_hours: 0}\nwatchlist: [A]", "half_life_hours"),
    ("settings: {window: forever}\nwatchlist: [A]", "settings.window"),
])
def test_config_validation(tmp_path, yaml_text, msg):
    from newsscan.config import ConfigError
    f = tmp_path / "w.yaml"
    f.write_text(yaml_text)
    with pytest.raises(ConfigError, match=msg):
        load(f)


def test_notify_reports_failed_delivery(monkeypatch):
    import requests
    from newsscan import notify

    class Resp:
        status_code = 401
        def raise_for_status(self):
            raise requests.HTTPError(response=self)
    monkeypatch.setenv("NEWSSCAN_NTFY_TOPIC", "t")
    monkeypatch.setattr(notify.requests, "post", lambda *a, **k: Resp())
    assert notify.send("x", "y") == []
