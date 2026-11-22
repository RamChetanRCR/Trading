"""Rule-based catalyst tagging.

Sentiment alone says *how* a headline sounds; catalysts say *why the stock might move*.
Each rule has a regex and a directional bias (+1 bullish, -1 bearish, 0 = direction depends
on the details, e.g. results). Biases nudge the final score; they never override it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Catalyst:
    tag: str
    pattern: re.Pattern
    bias: int
    note: str


def _c(tag: str, regex: str, bias: int, note: str) -> Catalyst:
    return Catalyst(tag, re.compile(regex, re.I), bias, note)


CATALYSTS: list[Catalyst] = [
    _c("results", r"\b(q[1-4]|quarterly|results?|earnings|profit|revenue|ebitda|net loss)\b", 0,
       "Earnings event — check numbers vs estimates"),
    _c("order_win", r"\b(bags?|wins?|secures?|bagged)\b.*\b(order|contract|deal)\b", +1,
       "New order/contract"),
    _c("rating_up", r"\b(upgrade[sd]?|raises? target|target (price )?raised|outperform|overweight|buy rating)\b", +1,
       "Broker upgrade / target raise"),
    _c("rating_down", r"\b(downgrade[sd]?|cuts? target|target (price )?cut|underperform|underweight|sell rating)\b", -1,
       "Broker downgrade / target cut"),
    _c("block_deal", r"\b(block deal|bulk deal|stake sale|offer for sale|ofs)\b", 0,
       "Large stake transaction — supply overhang or strong hands buying"),
    _c("lock_in", r"\b(lock-?in)\b", -1, "Lock-in expiry — possible selling pressure"),
    _c("ipo", r"\b(ipo|gmp|grey market premium|listing (day|gains?)|subscribed)\b", 0, "IPO / listing news"),
    _c("corporate_action", r"\b(dividend|buyback|bonus issue|stock split|record date)\b", +1,
       "Shareholder-friendly corporate action"),
    _c("m_and_a", r"\b(acquir\w*|merger|takeover|amalgamation|demerger)\b", 0, "M&A / restructuring"),
    _c("regulatory", r"\b(sebi|rbi|penalty|show[- ]cause|probe|raid|ban|ed\b|cbi|investigation)\b", -1,
       "Regulatory / legal risk"),
    _c("management", r"\b(ceo|cfo|md|chairman)\b.*\b(resign\w*|quits?|steps? down|exit)\b", -1,
       "Top management exit"),
    _c("capex", r"\b(capex|new plant|capacity expansion|commission(s|ed)?)\b", +1, "Capacity / capex expansion"),
    _c("pledge", r"\b(pledge[sd]?)\b", -1, "Promoter pledge"),
]


def tag(text: str) -> list[Catalyst]:
    return [c for c in CATALYSTS if c.pattern.search(text or "")]


def bias(tags: list[Catalyst]) -> int:
    """Net directional bias, clipped to [-1, 1]."""
    return max(-1, min(1, sum(c.bias for c in tags)))
