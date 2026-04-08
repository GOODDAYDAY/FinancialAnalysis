"""Sentiment Analysis agent node: analyze news sentiment with explainable reasoning."""

import logging
from backend.llm_client import call_llm_structured
from backend.state import SentimentOutput
from backend.utils.language import language_directive

logger = logging.getLogger(__name__)


def sentiment_node(state: dict) -> dict:
    """F-09, F-10: Sentiment scoring with explainable reasoning chain."""
    ticker = state.get("ticker", "")
    articles = state.get("news_articles", [])
    language = state.get("language", "en")

    if not articles:
        logger.warning("No news articles available for sentiment analysis")
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

    # Build article summaries for LLM — number each so the LLM can
    # cite article_index in its per-article scores
    article_text = ""
    for i, article in enumerate(articles[:10], 1):
        article_text += (
            f"\n[Article {i}] Source: {article.get('source', 'unknown')} | "
            f"Published: {article.get('published', 'unknown')}\n"
            f"Title: {article.get('title', 'Untitled')}\n"
            f"Summary: {article.get('summary', 'No summary')}\n"
        )

    system_prompt = (
        f"You are a financial sentiment analysis expert. Analyze the following news articles "
        f"about {ticker} and provide a comprehensive sentiment assessment.\n\n"
        f"Be aware of sarcasm and irony. Consider both positive and negative aspects. "
        f"Weigh each article by RELEVANCE to {ticker} specifically — generic market news "
        f"that only mentions the ticker in passing should get lower weight than articles "
        f"directly about the company's operations, earnings, management, or products.\n\n"
        f"REQUIRED per-article output: for EACH article above, emit one entry in "
        f"`article_scores` as: "
        f"{{'article_index': <int>, 'title': <str>, 'score': <float in -1..+1>, "
        f"'relevance': <float in 0..1>, 'rationale': <short str>, 'impact': <'high'|'medium'|'low'>}}.\n\n"
        f"Overall score MUST be the relevance-weighted average of per-article scores.\n"
        f"For overall_label, use: bullish, bearish, or neutral.\n"
        f"For overall_score, use -1.0 (very bearish) to +1.0 (very bullish).\n"
        f"In `key_factors`, list 3-5 concrete drivers from the articles (e.g. 'Q3 earnings beat', "
        f"'new product launch', 'regulatory probe') — no generic phrases like 'positive news'."
    ) + language_directive(language)

    result = call_llm_structured(
        user_prompt=f"Analyze sentiment for {ticker} based on these articles:\n{article_text}",
        response_model=SentimentOutput,
        system_prompt=system_prompt,
    )

    # Post-process: if the LLM returned per-article scores with relevance,
    # recompute the overall_score as a relevance-weighted average. This
    # makes the final number defensible and traceable to specific articles.
    if result.article_scores:
        weighted_sum = 0.0
        total_weight = 0.0
        for entry in result.article_scores:
            score = _as_float(entry.get("score"))
            relevance = _as_float(entry.get("relevance"), default=0.5)
            if score is None:
                continue
            relevance = max(0.0, min(1.0, relevance))
            weighted_sum += score * relevance
            total_weight += relevance
        if total_weight > 0:
            recomputed = weighted_sum / total_weight
            # Clamp to valid range
            recomputed = max(-1.0, min(1.0, recomputed))
            if abs(recomputed - result.overall_score) > 0.05:
                logger.info(
                    "Sentiment recomputed from per-article scores: %.2f -> %.2f",
                    result.overall_score, recomputed,
                )
            result.overall_score = round(recomputed, 3)

    logger.info(
        "Sentiment for %s: score=%.2f, label=%s (%d articles scored)",
        ticker, result.overall_score, result.overall_label, len(result.article_scores),
    )

    return {
        "sentiment": result.model_dump(),
        "reasoning_chain": [{
            "agent": "sentiment",
            "score": result.overall_score,
            "label": result.overall_label,
            "confidence": result.confidence,
            "articles_scored": len(result.article_scores),
            "key_factors": result.key_factors,
            "reasoning": result.reasoning,
        }],
    }


def _as_float(value, default=None):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
