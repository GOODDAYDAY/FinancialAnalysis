"""Tests for HTML email template rendering."""

from backend.notification.templates import render_analysis_email, render_batch_summary


def _sample_result(ticker="600519.SS", rec="hold"):
    return {
        "ticker": ticker,
        "intent": "stock_query",
        "market_data": {
            "current_price": 1460.0,
            "price_change_pct": 1.2,
            "pe_ratio": 20.4,
            "rsi_14": 50.0,
            "fifty_two_week_high": 1800,
            "fifty_two_week_low": 1100,
        },
        "sentiment": {"overall_score": 0.3, "overall_label": "bullish"},
        "fundamental": {"health_score": 8.5, "summary": "Strong brand", "red_flags": []},
        "quant": {
            "score": 35,
            "verdict": "STRONG BUY SIGNAL",
            "signals": [{"name": "MACD Bullish", "type": "bullish", "detail": "Above signal", "weight": 15}],
        },
        "grid_strategy": {
            "score": 45,
            "verdict": "MARGINAL",
            "annual_volatility_pct": 11.15,
            "best_strategy_name": "Long-term Wide Grid",
            "best_monthly_return_pct": 4.12,
            "strategies": [
                {
                    "name": "Long-term Wide Grid", "horizon": "long-term",
                    "lower_price": 1080, "upper_price": 1800,
                    "grid_count": 10, "grid_step": 72, "grid_step_pct": 4.93,
                    "shares_per_grid": 100, "capital_required": 100000,
                    "profit_per_cycle": 7048, "profit_per_cycle_pct": 4.89,
                    "fees_per_cycle": 152, "break_even_move_pct": 0.1,
                    "estimated_cycles_per_month": 0.8,
                    "estimated_monthly_return_pct": 4.12,
                    "description": "Wide grid for 6-12 month holding",
                    "caveats": [],
                },
            ],
        },
        "risk": {"risk_score": 4.5, "risk_level": "medium", "risk_factors": ["Valuation premium"]},
        "debate_history": [
            {"role": "bull", "round_number": 1, "argument": "Strong moat", "key_points": ["ROE 54%"]},
            {"role": "bear", "round_number": 1, "argument": "Overvalued", "key_points": ["PE premium"]},
        ],
        "recommendation": {
            "recommendation": rec, "confidence": 0.55, "investment_horizon": "long-term",
            "supporting_factors": ["Strong brand"], "dissenting_factors": ["High PE"],
            "reasoning": "Mixed signals justify hold",
            "disclaimer": "Not financial advice.",
        },
    }


class TestAnalysisEmail:
    """Single-stock email rendering."""

    def test_subject_contains_ticker_and_recommendation(self):
        subject, _, _ = render_analysis_email(_sample_result("600519.SS", "buy"))
        assert "600519.SS" in subject
        assert "BUY" in subject

    def test_html_body_contains_key_data(self):
        _, html, _ = render_analysis_email(_sample_result())
        assert "600519.SS" in html
        assert "1460" in html  # price
        assert "50.0" in html or "50" in html  # RSI
        assert "8.5" in html  # health score
        assert "STRONG BUY SIGNAL" in html  # quant verdict
        assert "Long-term Wide Grid" in html  # grid strategy
        assert "Strong moat" in html  # bull argument
        assert "Overvalued" in html  # bear argument
        assert "Disclaimer" in html

    def test_text_body_is_plain(self):
        _, _, text = render_analysis_email(_sample_result())
        assert "<html>" not in text
        assert "<div" not in text
        assert "600519.SS" in text

    def test_recommendation_color_buy(self):
        _, html, _ = render_analysis_email(_sample_result(rec="buy"))
        assert "#16a34a" in html  # green for buy

    def test_recommendation_color_sell(self):
        _, html, _ = render_analysis_email(_sample_result(rec="sell"))
        assert "#dc2626" in html  # red for sell


class TestBatchSummary:
    """Multi-stock summary email rendering."""

    def test_summary_includes_all_tickers(self):
        results = [
            _sample_result("600519.SS", "hold"),
            _sample_result("000858.SZ", "buy"),
            _sample_result("300750.SZ", "sell"),
        ]
        subject, html, text = render_batch_summary(results)
        assert "600519.SS" in html
        assert "000858.SZ" in html
        assert "300750.SZ" in html
        for ticker in ["600519.SS", "000858.SZ", "300750.SZ"]:
            assert ticker in text

    def test_summary_contains_disclaimer(self):
        _, html, _ = render_batch_summary([_sample_result()])
        assert "Disclaimer" in html

    def test_subject_has_timestamp(self):
        subject, _, _ = render_batch_summary([_sample_result()])
        assert "Watchlist" in subject
