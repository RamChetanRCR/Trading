"""Risk-based position sizing.

Size a trade from the stop, not from conviction: decide how much of the account you are
willing to lose if the stop is hit, then buy only as many shares as that allows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Position:
    qty: int
    capital_used: float
    risk_amount: float
    risk_per_share: float
    pct_of_capital: float
    target: float | None
    reward_risk: float | None
    warnings: list[str]


def size_position(
    capital: float,
    entry: float,
    stop: float,
    risk_pct: float = 1.0,
    target: float | None = None,
    max_position_pct: float = 25.0,
) -> Position:
    if capital <= 0 or entry <= 0 or stop <= 0:
        raise ValueError("capital, entry and stop must be positive")
    if stop == entry:
        raise ValueError("stop cannot equal entry")
    if not 0 < risk_pct <= 100:
        raise ValueError("risk_pct must be in (0, 100]")

    long = stop < entry
    rps = abs(entry - stop)
    risk_amount = capital * risk_pct / 100
    qty = math.floor(risk_amount / rps)

    warnings = []
    cap_qty = math.floor(capital * max_position_pct / 100 / entry)
    if qty > cap_qty:
        warnings.append(f"capped at {max_position_pct:.0f}% of capital (stop is very tight)")
        qty = cap_qty
    if qty == 0:
        warnings.append("risk budget is smaller than one share's risk — skip or widen risk %")

    rr = None
    if target is not None:
        reward = (target - entry) if long else (entry - target)
        if reward <= 0:
            warnings.append("target is on the wrong side of entry")
        else:
            rr = round(reward / rps, 2)
            if rr < 1.5:
                warnings.append(f"reward:risk {rr} is below 1.5")

    if rps / entry > 0.08:
        warnings.append(f"stop is {rps / entry:.0%} away — wide for a short-term trade")

    used = qty * entry
    return Position(qty, round(used, 2), round(qty * rps, 2), round(rps, 2),
                    round(100 * used / capital, 2), target, rr, warnings)
