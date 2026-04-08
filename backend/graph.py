"""
LangGraph StateGraph: wires all agents into the analysis pipeline.

Pipeline:
  orchestrator
    -> market_data -> macro_env -> sector
    -> news -> announcement -> social_sentiment
    -> sentiment -> fundamental
    -> momentum -> quant -> grid_strategy
    -> debate -> debate_judge -> (debate again | risk)
    -> advisory

Each agent lives in its own sub-package under backend/agents/.
"""

import logging
from langgraph.graph import StateGraph, END

from backend.state import ResearchState
from backend.agents.orchestrator import orchestrator_node
from backend.agents.market_data import market_data_node
from backend.agents.macro_env import macro_env_node
from backend.agents.sector import sector_node
from backend.agents.news import news_node
from backend.agents.announcement import announcement_node
from backend.agents.social_sentiment import social_sentiment_node
from backend.agents.sentiment import sentiment_node
from backend.agents.fundamental import fundamental_node
from backend.agents.momentum import momentum_node
from backend.agents.quant import quant_node
from backend.agents.grid_strategy import grid_strategy_node
from backend.agents.debate import debate_node
from backend.agents.debate_judge import debate_judge_node
from backend.agents.debate_judge.node import should_continue_debate_with_judge
from backend.agents.risk import risk_node
from backend.agents.advisory import advisory_node

logger = logging.getLogger(__name__)


def _safe(node_fn, agent_name: str):
    """F-19: Universal fallback — wrap node to catch exceptions."""
    def wrapper(state: dict) -> dict:
        try:
            return node_fn(state)
        except Exception as e:
            logger.exception("Agent %s failed: %s", agent_name, e)
            return {
                "errors": [{"agent": agent_name, "error": str(e)}],
                "reasoning_chain": [{"agent": agent_name, "status": "FAILED", "error": str(e)}],
            }
    return wrapper


def _route_after_orchestrator(state: dict) -> str:
    """Route based on intent classification."""
    intent = state.get("intent", "")
    if intent in ("chitchat", "out_of_scope", "rejected"):
        return "end"
    return "collect_data"


def build_graph():
    """Build and compile the LangGraph StateGraph."""
    graph = StateGraph(ResearchState)

    # Register nodes
    graph.add_node("orchestrator", _safe(orchestrator_node, "orchestrator"))
    graph.add_node("market_data", _safe(market_data_node, "market_data"))
    graph.add_node("macro_env", _safe(macro_env_node, "macro_env"))
    graph.add_node("sector", _safe(sector_node, "sector"))
    graph.add_node("news", _safe(news_node, "news"))
    graph.add_node("announcement", _safe(announcement_node, "announcement"))
    graph.add_node("social_sentiment", _safe(social_sentiment_node, "social_sentiment"))
    graph.add_node("sentiment", _safe(sentiment_node, "sentiment"))
    graph.add_node("fundamental", _safe(fundamental_node, "fundamental"))
    graph.add_node("momentum", _safe(momentum_node, "momentum"))
    graph.add_node("quant", _safe(quant_node, "quant"))
    graph.add_node("grid_strategy", _safe(grid_strategy_node, "grid_strategy"))
    graph.add_node("debate", _safe(debate_node, "debate"))
    graph.add_node("debate_judge", _safe(debate_judge_node, "debate_judge"))
    graph.add_node("risk", _safe(risk_node, "risk"))
    graph.add_node("advisory", _safe(advisory_node, "advisory"))

    # Entry point
    graph.set_entry_point("orchestrator")

    # After orchestrator: route by intent
    graph.add_conditional_edges(
        "orchestrator",
        _route_after_orchestrator,
        {
            "collect_data": "market_data",
            "end": END,
        },
    )

    # Data collection pipeline
    graph.add_edge("market_data", "macro_env")
    graph.add_edge("macro_env", "sector")
    graph.add_edge("sector", "news")
    graph.add_edge("news", "announcement")
    graph.add_edge("announcement", "social_sentiment")

    # Analysis pipeline
    graph.add_edge("social_sentiment", "sentiment")
    graph.add_edge("sentiment", "fundamental")
    graph.add_edge("fundamental", "momentum")
    graph.add_edge("momentum", "quant")
    graph.add_edge("quant", "grid_strategy")

    # Debate loop with judge
    graph.add_edge("grid_strategy", "debate")
    graph.add_edge("debate", "debate_judge")
    graph.add_conditional_edges(
        "debate_judge",
        should_continue_debate_with_judge,
        {
            "debate": "debate",
            "risk": "risk",
        },
    )

    # Risk -> Advisory -> END
    graph.add_edge("risk", "advisory")
    graph.add_edge("advisory", END)

    compiled = graph.compile()
    logger.info("LangGraph compiled successfully with 16 nodes")
    return compiled


# Singleton compiled graph
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def run_analysis(query: str) -> dict:
    """Run the full analysis pipeline for a user query."""
    graph = get_graph()
    initial_state = {
        "user_query": query,
        "ticker": "",
        "intent": "",
        "language": "en",
        "market_data": {},
        "macro_env": {},
        "sector": {},
        "news_articles": [],
        "announcements": [],
        "financial_summary": {},
        "social_sentiment": {},
        "sentiment": {},
        "fundamental": {},
        "momentum": {},
        "quant": {},
        "grid_strategy": {},
        "debate_history": [],
        "debate_round": 0,
        "debate_judge": {},
        "risk": {},
        "recommendation": {},
        "reasoning_chain": [],
        "errors": [],
    }

    logger.info("Starting analysis for: %s", query[:100])
    result = graph.invoke(initial_state, config={"recursion_limit": 50})
    logger.info("Analysis complete for: %s", query[:100])
    return result
