"""
LangGraph StateGraph: wires all 8 agents into the analysis pipeline.

Graph topology:
  orchestrator → market_data → news
  → sentiment → fundamental → quant → debate (self-loop x2) → risk → advisory

Quant Agent runs pure algorithms (no LLM) and feeds into the debate as "data referee".
"""

import logging
from langgraph.graph import StateGraph, END

from backend.state import ResearchState
from backend.agents.orchestrator import orchestrator_node
from backend.agents.market_data import market_data_node
from backend.agents.news import news_node
from backend.agents.sentiment import sentiment_node
from backend.agents.fundamental import fundamental_node
from backend.agents.quant import quant_node
from backend.agents.debate import debate_node, should_continue_debate
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

    # Register nodes (8 agents)
    graph.add_node("orchestrator", _safe(orchestrator_node, "orchestrator"))
    graph.add_node("market_data", _safe(market_data_node, "market_data"))
    graph.add_node("news", _safe(news_node, "news"))
    graph.add_node("sentiment", _safe(sentiment_node, "sentiment"))
    graph.add_node("fundamental", _safe(fundamental_node, "fundamental"))
    graph.add_node("quant", _safe(quant_node, "quant"))
    graph.add_node("debate", _safe(debate_node, "debate"))
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

    # Data collection
    graph.add_edge("market_data", "news")

    # Analysis pipeline
    graph.add_edge("news", "sentiment")
    graph.add_edge("sentiment", "fundamental")

    # Quant → Debate: quant provides algorithmic evidence for the debate
    graph.add_edge("fundamental", "quant")
    graph.add_edge("quant", "debate")

    # Debate self-loop
    graph.add_conditional_edges(
        "debate",
        should_continue_debate,
        {
            "debate": "debate",
            "risk": "risk",
        },
    )

    # Risk → Advisory → END
    graph.add_edge("risk", "advisory")
    graph.add_edge("advisory", END)

    compiled = graph.compile()
    logger.info("LangGraph compiled successfully with 9 nodes")
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
        "market_data": {},
        "news_articles": [],
        "sentiment": {},
        "fundamental": {},
        "quant": {},
        "risk": {},
        "debate_history": [],
        "debate_round": 0,
        "recommendation": {},
        "reasoning_chain": [],
        "errors": [],
    }

    logger.info("Starting analysis for: %s", query[:100])
    result = graph.invoke(initial_state)
    logger.info("Analysis complete for: %s", query[:100])
    return result
