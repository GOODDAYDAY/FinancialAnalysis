"""
Behavioral tests for the Advisory agent's numeric decision override.

_compute_decision_override is pure math — no LLM, no network.
Tests cover all 8 override rules and the composite score formula.

This is a key explainability/auditability test: the override is the mechanism
that prevents the LLM's HOLD bias from dominating against clear numeric signals.
Verifying it deterministically means we can demonstrate the override logic
is correct and traceable to the code.
"""

import pytest
from backend.agents.advisory.node import _compute_decision_override


def _override(
    mom_score=0, r5=0.0, r20=0.0, breakout=False,
    health=5.0, quant_score=0, sent_score=0.0, risk_score=5.0,
    bull_strength=50, bear_strength=50,
):
    """Helper: build synthetic agent dicts and call _compute_decision_override."""
    momentum = {
        "score": mom_score,
        "returns": {"5d": r5, "20d": r20},
        "breakout_20": breakout,
    }
    quant = {"score": quant_score}
    fundamental = {"health_score": health}
    sentiment = {"overall_score": sent_score}
    risk = {"risk_score": risk_score}
    debate_judge = {"bull_strength": bull_strength, "bear_strength": bear_strength}
    return _compute_decision_override(momentum, quant, fundamental, sentiment, risk, debate_judge)


class TestCompositeScoreFormula:
    """Verify the weighted composite calculation matches documented weights."""

    def test_all_neutral_scores_composite_zero(self):
        """health=5 → fund=0; risk=5 → risk_contrib=0; rest=0 → composite=0."""
        result = _override(mom_score=0, quant_score=0, health=5.0, sent_score=0.0, risk_score=5.0)
        assert abs(result["composite_score"]) < 0.01

    def test_strong_fundamentals_push_positive(self):
        """health=10 → fund_score=(10-5)*20=+100; 0.20 weight → +20 composite."""
        result = _override(health=10.0)
        assert result["composite_score"] == pytest.approx(20.0, abs=0.1)

    def test_high_risk_pushes_negative(self):
        """risk=10 → risk_score=(5-10)*20=-100; 0.20 weight → -20 composite."""
        result = _override(risk_score=10.0)
        assert result["composite_score"] == pytest.approx(-20.0, abs=0.1)

    def test_strong_momentum_pushes_positive(self):
        """mom_score=80; 0.25 weight → +20 composite."""
        result = _override(mom_score=80)
        assert result["composite_score"] == pytest.approx(20.0, abs=0.1)

    def test_composite_capped_at_extremes(self):
        """All dims at max → composite should be large but below 100 (weights sum to 1)."""
        result = _override(
            mom_score=100, quant_score=100, health=10.0,
            sent_score=1.0, risk_score=1.0
        )
        # composite = 0.25*100 + 0.20*100 + 0.20*100 + 0.15*100 + 0.20*80 = 96
        assert result["composite_score"] == pytest.approx(96.0, abs=1.0)


class TestOverrideRule1_StrongRally:
    """Rule: strong_short_term_rally — r5 >= 8 AND mom_score >= 30 AND composite >= 0."""

    def test_strong_rally_forces_buy(self):
        result = _override(mom_score=50, r5=10.0, health=6.0)
        assert result["forced_recommendation"] == "buy"
        assert result["rule"] == "strong_short_term_rally"

    def test_strong_rally_requires_r5_threshold(self):
        """r5=7 (< 8) — rule should NOT fire."""
        result = _override(mom_score=50, r5=7.0)
        assert result["rule"] != "strong_short_term_rally"

    def test_strong_rally_requires_positive_composite(self):
        """r5=10, mom=50 but risk=10 (composite negative) — rule should NOT fire."""
        result = _override(mom_score=50, r5=10.0, risk_score=10.0)
        assert result["rule"] != "strong_short_term_rally"


class TestOverrideRule2_CompositeStronglyBullish:
    """Rule: composite >= 35 → buy."""

    def test_composite_35_triggers_buy(self):
        # mom=100 (0.25*100=25), health=10 (0.20*100=20): composite = 45 >= 35
        result = _override(mom_score=100, health=10.0, risk_score=5.0)
        assert result["forced_recommendation"] == "buy"
        assert result["rule"] in ("strong_short_term_rally", "composite_strongly_bullish")

    def test_composite_exactly_35(self):
        # health=10 → fund=+100 → contrib=20; quant=75 → contrib=15: total=35
        result = _override(health=10.0, quant_score=75)
        assert result["forced_recommendation"] == "buy"


class TestOverrideRule3_CompositeStronglyBearish:
    """Rule: composite <= -35 → sell."""

    def test_composite_minus_35_forces_sell(self):
        # risk=10 (-20), health=1 (-80*0.20=-16), quant=-100 (-20): composite ~ -56
        result = _override(quant_score=-100, health=1.0, risk_score=10.0)
        assert result["forced_recommendation"] == "sell"
        assert result["rule"] == "composite_strongly_bearish"

    def test_moderate_bearish_no_sell_override(self):
        """composite=-20 (not <= -35) → no forced sell."""
        result = _override(quant_score=-50, risk_score=7.0)
        assert result["forced_recommendation"] != "sell" or result["rule"] != "composite_strongly_bearish"


class TestOverrideRule4_Breakout:
    """Rule: breakout_with_positive_composite."""

    def test_breakout_forces_buy(self):
        result = _override(breakout=True, r5=3.0, mom_score=20, health=7.0)
        assert result["forced_recommendation"] == "buy"
        assert result["rule"] == "breakout_with_positive_composite"

    def test_breakout_requires_positive_r5(self):
        """breakout=True but r5 < 0 — rule should not fire."""
        result = _override(breakout=True, r5=-1.0, mom_score=20)
        assert result["rule"] != "breakout_with_positive_composite"


class TestOverrideRule5_RisingNoSellGuard:
    """Rule: rising_stock_no_sell_guard — no forced rec, just a guard."""

    def test_rising_stock_no_forced_rec(self):
        """r5=6 and composite slightly positive → no forced recommendation (guard only)."""
        result = _override(r5=6.0, mom_score=10, health=5.5)
        assert result["forced_recommendation"] is None
        assert result["rule"] == "rising_stock_no_sell_guard"


class TestOverrideRule6And7_DebateDominance:
    """Rules: debate_bull_dominant and debate_bear_dominant."""

    def test_bull_dominant_forces_buy(self):
        # composite must be >= 10: health=6 → fund=(6-5)*20=+20 → 0.20*20=+4; quant=30 → 0.20*30=+6; total=10
        result = _override(bull_strength=80, bear_strength=50, quant_score=30, health=6.0)
        assert result["forced_recommendation"] == "buy"
        assert result["rule"] == "debate_bull_dominant"

    def test_bear_dominant_forces_sell(self):
        result = _override(bull_strength=40, bear_strength=75, quant_score=-30, risk_score=8.0)
        assert result["forced_recommendation"] == "sell"
        assert result["rule"] == "debate_bear_dominant"

    def test_balanced_debate_no_override(self):
        """bull=60, bear=40 — difference < 25, rule should not fire."""
        result = _override(bull_strength=60, bear_strength=40)
        assert result["rule"] not in ("debate_bull_dominant", "debate_bear_dominant")


class TestOverrideRule8_NoOverride:
    """Rule: no_override — all conditions neutral."""

    def test_neutral_state_no_override(self):
        result = _override()
        assert result["forced_recommendation"] is None
        assert result["rule"] == "no_override"

    def test_no_override_composite_near_zero(self):
        result = _override()
        assert abs(result["composite_score"]) < 0.01


class TestConfidenceFloor:
    """Confidence floor must be consistent with rule severity."""

    def test_strong_rally_confidence_above_60(self):
        result = _override(mom_score=60, r5=10.0, health=6.0)
        assert result["confidence_floor"] >= 0.60

    def test_no_override_confidence_floor_zero(self):
        result = _override()
        assert result["confidence_floor"] == 0.0

    def test_forced_recs_have_positive_confidence(self):
        result = _override(quant_score=-100, health=1.0, risk_score=10.0)
        if result["forced_recommendation"] == "sell":
            assert result["confidence_floor"] > 0
