"""Sentiment Analysis agent: analyze news sentiment with explainable reasoning."""

import logging
from backend.llm_client import call_llm_structured
from backend.state import SentimentOutput

logger = logging.getLogger(__name__)


def sentiment_node(state: dict) -> dict:
    """F-09, F-10: Sentiment scoring with explainable reasoning chain."""
    ticker = state.get("ticker", "")
    articles = state.get("news_articles", [])

    if not articles:
        logger.warning("No news articles for sentiment analysis")
        default = SentimentOutput(
            overall_score=0.0,
            confidence=0.1,
            overall_label="neutral",
            reasoning="No news data available for sentiment analysis.",
        )
        return {
            "sentiment": default.model_dump(),
            "reasoning_chain": [{"agent": "sentiment", "note": "no articles available"}],
        }

    # Build article summaries for LLM
    article_text = ""
    for i, article in enumerate(articles[:8], 1):
        article_text += (
            f"\nArticle {i}: [{article.get('source', 'unknown')}] "
            f"{article.get('title', 'Untitled')}\n"
            f"Summary: {article.get('summary', 'No summary')}\n"
        )

    system_prompt = (
        f"You are a financial sentiment analysis expert. Analyze the following news articles "
        f"about {ticker} and provide a comprehensive sentiment assessment.\n\n"
        f"Be aware of sarcasm and irony. Consider both positive and negative aspects. "
        f"Provide specific evidence from the articles for your scoring.\n\n"
        f"For overall_label, use: bullish, bearish, or neutral.\n"
        f"For overall_score, use -1.0 (very bearish) to +1.0 (very bullish).\n"
        f"For article_scores, provide a list of dicts with 'title' and 'score' for each article."
    )

    result = call_llm_structured(
        user_prompt=f"Analyze sentiment for {ticker} based on these articles:\n{article_text}",
        response_model=SentimentOutput,
        system_prompt=system_prompt,
    )

    logger.info("Sentiment for %s: score=%.2f, label=%s", ticker, result.overall_score, result.overall_label)

    return {
        "sentiment": result.model_dump(),
        "reasoning_chain": [{
            "agent": "sentiment",
            "score": result.overall_score,
            "label": result.overall_label,
            "confidence": result.confidence,
            "key_factors": result.key_factors,
            "reasoning": result.reasoning,
        }],
    }
