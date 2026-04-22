"""
Algorithmic valuation helpers for the Fundamental agent.

Pure math, no LLM. Produces numeric anchors the LLM can cite so
fundamental assessments stop being hand-wavy. Inputs are the plain
market_data dict; unknown fields degrade to None instead of raising.

Indicators:
  - PEG ratio              (P/E divided by implied growth rate)
  - Simplified DCF value   (perpetuity-growth 1-stage model)
  - EV/EBITDA multiple     (cheap enterprise-value proxy)
  - Earnings yield         (inverse P/E, compare to risk-free rate)
"""

import logging

logger = logging.getLogger(__name__)


def compute_peg_ratio(pe: float | None, growth_rate_pct: float | None) -> float | None:
    """
    PEG = P/E / growth rate (in percent).
    PEG < 1 = potentially undervalued for growth.
    PEG > 2 = rich relative to growth.
    """
    if pe is None or growth_rate_pct is None or growth_rate_pct <= 0:
        return None
    return round(pe / growth_rate_pct, 2)


def compute_simple_dcf(
    current_earnings: float | None,
    growth_rate: float = 0.08,
    discount_rate: float = 0.10,
    terminal_growth: float = 0.03,
    years: int = 5,
) -> float | None:
    """
    Single-stage DCF: project earnings for `years` at `growth_rate`,
    then apply a Gordon terminal value. Discount back at `discount_rate`.

    Returns intrinsic value per share if earnings (EPS) are provided,
    else None. This is deliberately coarse — it's a sanity anchor, not
    a precise valuation.
    """
    if current_earnings is None or current_earnings <= 0:
        return None
    if discount_rate <= terminal_growth:
        return None  # invalid assumption

    pv = 0.0
    earnings = current_earnings
    for year in range(1, years + 1):
        earnings = earnings * (1 + growth_rate)
        pv += earnings / ((1 + discount_rate) ** year)

    terminal_value = (earnings * (1 + terminal_growth)) / (discount_rate - terminal_growth)
    pv += terminal_value / ((1 + discount_rate) ** years)
    return round(pv, 2)


def compute_earnings_yield(pe: float | None) -> float | None:
    """
    Earnings yield = 1 / P/E (in percent). Useful vs 10y bond yield.
    """
    if pe is None or pe <= 0:
        return None
    return round(100 / pe, 2)


def compute_ev_ebitda_proxy(market_cap: float | None, ebitda: float | None) -> float | None:
    """
    Proxy for EV/EBITDA when we lack debt/cash data: just market_cap/EBITDA.
    Under 10 = cheap, over 20 = rich (very rough).
    """
    if not market_cap or not ebitda or ebitda <= 0:
        return None
    return round(market_cap / ebitda, 2)


def compute_valuation_summary(market_data: dict) -> dict:
    """
    Top-level helper — runs all valuation calcs and returns a dict of
    numeric anchors + textual verdicts. Safe against missing fields.

    Assumed growth rate defaults to 8% because the agent typically
    lacks forward guidance; caller can override if it has better data.
    """
    pe = market_data.get("pe_ratio")
    price = market_data.get("current_price")

    # Derive EPS from P/E + price if possible: EPS = price / P/E
    eps = (price / pe) if (price and pe and pe > 0) else None

    peg = compute_peg_ratio(pe, 8.0)  # assume 8% growth — override if known
    dcf_value = compute_simple_dcf(eps) if eps else None
    earnings_yield = compute_earnings_yield(pe)

    # Margin of safety: how far is price below DCF value?
    margin_of_safety = None
    if dcf_value and price:
        margin_of_safety = round((dcf_value - price) / price * 100, 1)

    verdicts: list[str] = []
    if peg is not None:
        if peg < 1:
            verdicts.append(f"PEG {peg} (<1) — potentially undervalued for growth")
        elif peg > 2:
            verdicts.append(f"PEG {peg} (>2) — rich relative to assumed 8% growth")
        else:
            verdicts.append(f"PEG {peg} — fair relative to growth")

    if margin_of_safety is not None:
        if margin_of_safety > 20:
            verdicts.append(f"DCF implies {margin_of_safety:+.0f}% margin of safety — undervalued")
        elif margin_of_safety < -20:
            verdicts.append(f"DCF implies {margin_of_safety:+.0f}% — overvalued vs model")
        else:
            verdicts.append(f"DCF margin of safety {margin_of_safety:+.0f}% — fairly priced")

    if earnings_yield is not None:
        verdicts.append(f"Earnings yield {earnings_yield}%")

    return {
        "pe_ratio": pe,
        "eps_implied": round(eps, 2) if eps else None,
        "peg_ratio": peg,
        "dcf_value_per_share": dcf_value,
        "margin_of_safety_pct": margin_of_safety,
        "earnings_yield_pct": earnings_yield,
        "assumptions": {
            "growth_rate_pct": 8.0,
            "discount_rate_pct": 10.0,
            "terminal_growth_pct": 3.0,
            "projection_years": 5,
        },
        "verdicts": verdicts,
    }
