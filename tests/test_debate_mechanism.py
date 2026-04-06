"""
AI Test Suite: Bull vs Bear Debate (F-16)

Tests that the debate mechanism produces structured arguments
with evidence, rebuttals, and correct round progression.
"""
import pytest
from backend.agents.debate import debate_node, should_continue_debate


class TestDebateRoundProgression:
    """Debate should run exactly 2 rounds via conditional self-loop."""

    def test_round_increments(self, mock_llm):
        """Input: debate_round=0 → Expected: debate_round=1 after one call."""
        mock_llm.set_responses(
            # Bull response
            {"role": "bull", "round_number": 1, "argument": "Buy because strong fundamentals",
             "key_points": ["High revenue"], "evidence": ["P/E 25"], "rebuttals": []},
            # Bear response
            {"role": "bear", "round_number": 1, "argument": "Sell because overvalued",
             "key_points": ["High P/E"], "evidence": ["P/E above average"], "rebuttals": ["P/E misleading"]},
        )
        state = {
            "ticker": "AAPL", "debate_round": 0, "debate_history": [],
            "market_data": {"current_price": 190}, "sentiment": {"overall_score": 0.5},
            "fundamental": {"health_score": 8}, "reasoning_chain": [],
        }
        result = debate_node(state)
        assert result["debate_round"] == 1

    def test_produces_bull_and_bear(self, mock_llm):
        """Expected: each round produces exactly 1 bull + 1 bear entry."""
        mock_llm.set_responses(
            {"role": "bull", "round_number": 1, "argument": "Bull case",
             "key_points": ["P1"], "evidence": ["E1"], "rebuttals": []},
            {"role": "bear", "round_number": 1, "argument": "Bear case",
             "key_points": ["P1"], "evidence": ["E1"], "rebuttals": ["R1"]},
        )
        state = {
            "ticker": "AAPL", "debate_round": 0, "debate_history": [],
            "market_data": {}, "sentiment": {}, "fundamental": {},
            "reasoning_chain": [],
        }
        result = debate_node(state)
        history = result["debate_history"]

        assert len(history) == 2
        roles = [h["role"] for h in history]
        assert "bull" in roles
        assert "bear" in roles

    def test_round_2_sees_round_1_arguments(self, mock_llm):
        """Expected: Round 2 prompt includes Round 1 debate history."""
        round1_history = [
            {"role": "bull", "round_number": 1, "argument": "Buy for growth",
             "key_points": ["Revenue up"], "evidence": [], "rebuttals": []},
            {"role": "bear", "round_number": 1, "argument": "Sell for risk",
             "key_points": ["Debt high"], "evidence": [], "rebuttals": []},
        ]
        mock_llm.set_responses(
            {"role": "bull", "round_number": 2, "argument": "Rebutting bear: debt is manageable",
             "key_points": ["Cash covers debt"], "evidence": [], "rebuttals": ["Debt ratio OK"]},
            {"role": "bear", "round_number": 2, "argument": "Rebutting bull: growth slowing",
             "key_points": ["Growth decelerating"], "evidence": [], "rebuttals": ["Revenue plateau"]},
        )
        state = {
            "ticker": "AAPL", "debate_round": 1, "debate_history": round1_history,
            "market_data": {}, "sentiment": {}, "fundamental": {},
            "reasoning_chain": [],
        }
        result = debate_node(state)

        # The Bull prompt should contain prior debate context
        bull_prompt = mock_llm.calls[0]["messages"][-1]["content"]
        assert "PRIOR DEBATE" in bull_prompt or "Round 1" in bull_prompt


class TestDebateConditionalEdge:
    """Conditional edge should loop debate or proceed."""

    @pytest.mark.parametrize("round_num,expected", [
        (0, "debate"),   # Round 0 → need more debate
        (1, "debate"),   # Round 1 → need round 2
        (2, "risk"),     # Round 2 → done, go to risk
        (3, "risk"),     # Beyond max → done
    ])
    def test_routing_by_round(self, round_num, expected):
        """Input: debate_round=N → Expected: correct next node."""
        assert should_continue_debate({"debate_round": round_num}) == expected


class TestDebateArgumentStructure:
    """Each debate argument must have required fields."""

    def test_bull_has_key_points(self, mock_llm):
        """Expected: bull argument includes key_points list."""
        mock_llm.set_responses(
            {"role": "bull", "round_number": 1, "argument": "Strong buy case",
             "key_points": ["Point A", "Point B", "Point C"],
             "evidence": ["Data 1", "Data 2"], "rebuttals": []},
            {"role": "bear", "round_number": 1, "argument": "Counter",
             "key_points": ["X"], "evidence": ["Y"], "rebuttals": ["Z"]},
        )
        state = {
            "ticker": "AAPL", "debate_round": 0, "debate_history": [],
            "market_data": {}, "sentiment": {}, "fundamental": {},
            "reasoning_chain": [],
        }
        result = debate_node(state)
        bull = [h for h in result["debate_history"] if h["role"] == "bull"][0]

        assert len(bull["key_points"]) >= 1, "Bull must provide key points"
        assert len(bull["argument"]) > 10, "Argument should be substantive"

    def test_bear_has_rebuttals_in_round_2(self, mock_llm):
        """Expected: Bear in Round 2 provides rebuttals to Bull."""
        mock_llm.set_responses(
            {"role": "bull", "round_number": 2, "argument": "Still bullish",
             "key_points": ["P1"], "evidence": ["E1"],
             "rebuttals": ["Bear's debt concern is overstated"]},
            {"role": "bear", "round_number": 2, "argument": "Still bearish",
             "key_points": ["P1"], "evidence": ["E1"],
             "rebuttals": ["Bull ignores macro headwinds", "Growth not sustainable"]},
        )
        state = {
            "ticker": "AAPL", "debate_round": 1,
            "debate_history": [
                {"role": "bull", "round_number": 1, "argument": "Buy", "key_points": [], "evidence": [], "rebuttals": []},
                {"role": "bear", "round_number": 1, "argument": "Sell", "key_points": [], "evidence": [], "rebuttals": []},
            ],
            "market_data": {}, "sentiment": {}, "fundamental": {},
            "reasoning_chain": [],
        }
        result = debate_node(state)
        bear = [h for h in result["debate_history"] if h["role"] == "bear"][0]

        assert len(bear["rebuttals"]) >= 1, "Bear should rebut Bull in Round 2"


class TestDebateUsesAnalysisData:
    """Debate prompts must reference actual analysis data, not hallucinate."""

    def test_bull_prompt_contains_ticker(self, mock_llm):
        """Expected: debate prompt includes the stock ticker."""
        mock_llm.set_responses(
            {"role": "bull", "round_number": 1, "argument": "A",
             "key_points": [], "evidence": [], "rebuttals": []},
            {"role": "bear", "round_number": 1, "argument": "B",
             "key_points": [], "evidence": [], "rebuttals": []},
        )
        state = {
            "ticker": "NVDA", "debate_round": 0, "debate_history": [],
            "market_data": {"current_price": 800}, "sentiment": {"overall_score": 0.7},
            "fundamental": {"health_score": 9}, "reasoning_chain": [],
        }
        debate_node(state)
        bull_user_prompt = mock_llm.calls[0]["messages"][-1]["content"]
        assert "NVDA" in bull_user_prompt

    def test_bull_prompt_contains_price(self, mock_llm):
        """Expected: debate prompt includes the stock price from market data."""
        mock_llm.set_responses(
            {"role": "bull", "round_number": 1, "argument": "A",
             "key_points": [], "evidence": [], "rebuttals": []},
            {"role": "bear", "round_number": 1, "argument": "B",
             "key_points": [], "evidence": [], "rebuttals": []},
        )
        state = {
            "ticker": "AAPL", "debate_round": 0, "debate_history": [],
            "market_data": {"current_price": 189.5}, "sentiment": {},
            "fundamental": {}, "reasoning_chain": [],
        }
        debate_node(state)
        bull_prompt = mock_llm.calls[0]["messages"][-1]["content"]
        assert "189.5" in bull_prompt, "Bull prompt should contain actual stock price"

    def test_bear_prompt_contains_bull_argument(self, mock_llm):
        """Expected: Bear's prompt includes Bull's argument for rebuttal."""
        mock_llm.set_responses(
            {"role": "bull", "round_number": 1, "argument": "AAPL is undervalued gem",
             "key_points": ["Low P/E"], "evidence": ["P/E 25"], "rebuttals": []},
            {"role": "bear", "round_number": 1, "argument": "Counter",
             "key_points": [], "evidence": [], "rebuttals": []},
        )
        state = {
            "ticker": "AAPL", "debate_round": 0, "debate_history": [],
            "market_data": {}, "sentiment": {}, "fundamental": {},
            "reasoning_chain": [],
        }
        debate_node(state)
        bear_prompt = mock_llm.calls[1]["messages"][-1]["content"]
        assert "undervalued gem" in bear_prompt, "Bear should see Bull's argument"
