"""
Debate Judge Agent — evaluates the Bull vs Bear debate after each round
and decides whether another round is needed.

The judge looks for:
  - Substantive engagement: are arguments citing real data, or just
    repeating prior claims?
  - Key points addressed: have both sides addressed the other's
    strongest arguments with actual rebuttals?
  - Convergence: are the sides getting closer to a synthesis, or
    still entrenched?
  - Saturation: has the debate started repeating itself?
  - Minimum rounds: always at least 2 rounds
  - Maximum rounds: hard safety cap to prevent runaway loops

Returns a Pydantic-validated structured decision the debate loop
uses to route to another round or to the risk agent.
"""

import logging
from pydantic import BaseModel, Field
from backend.llm_client import call_llm_structured
from backend.utils.language import language_directive
from backend.config import settings

logger = logging.getLogger(__name__)


class JudgeDecision(BaseModel):
    """Structured output of the debate judge."""
    verdict: str = Field(
        description="One of: 'continue' (need another round), 'concluded' (debate is mature enough)"
    )
    quality_score: int = Field(
        ge=0, le=100,
        description="0-100 score of the debate's quality and depth so far"
    )
    reason: str = Field(description="Why the judge made this decision")
    unresolved_points: list[str] = Field(
        default_factory=list,
        description="Specific Bull/Bear points that still need rebuttal if continuing"
    )
    bull_strength: int = Field(ge=0, le=100, description="Bull side's argument strength 0-100")
    bear_strength: int = Field(ge=0, le=100, description="Bear side's argument strength 0-100")


# Absolute safety cap even if the judge keeps saying "continue"
MAX_DEBATE_ROUNDS = 5
# Minimum rounds before the judge is even consulted
MIN_DEBATE_ROUNDS = 2


def debate_judge_node(state: dict) -> dict:
    """Evaluate the debate so far and decide whether to continue."""
    ticker = state.get("ticker", "???")
    debate_history = state.get("debate_history", [])
    current_round = state.get("debate_round", 0)
    language = state.get("language", "en")

    logger.info("Debate judge evaluating round %d for %s", current_round, ticker)

    # Safety: always require at least MIN rounds, always stop at MAX
    if current_round < MIN_DEBATE_ROUNDS:
        logger.info("Judge: below minimum %d rounds, auto-continuing", MIN_DEBATE_ROUNDS)
        return {
            "debate_judge": {
                "verdict": "continue",
                "quality_score": 0,
                "reason": f"Minimum {MIN_DEBATE_ROUNDS} rounds required before judging.",
                "unresolved_points": [],
                "bull_strength": 50,
                "bear_strength": 50,
                "round_evaluated": current_round,
            },
            "reasoning_chain": [{
                "agent": "debate_judge",
                "round_evaluated": current_round,
                "verdict": "continue",
                "reason": "min rounds not reached",
            }],
        }

    if current_round >= MAX_DEBATE_ROUNDS:
        logger.info("Judge: max %d rounds reached, forcing conclusion", MAX_DEBATE_ROUNDS)
        return {
            "debate_judge": {
                "verdict": "concluded",
                "quality_score": 70,
                "reason": f"Safety cap of {MAX_DEBATE_ROUNDS} rounds reached.",
                "unresolved_points": [],
                "bull_strength": 50,
                "bear_strength": 50,
                "round_evaluated": current_round,
            },
            "reasoning_chain": [{
                "agent": "debate_judge",
                "round_evaluated": current_round,
                "verdict": "concluded",
                "reason": "max rounds reached",
            }],
        }

    # Build debate transcript for the judge
    transcript = f"=== Bull vs Bear Debate on {ticker}, {current_round} rounds so far ===\n"
    for entry in debate_history:
        role = (entry.get("role") or "?").upper()
        rnd = entry.get("round_number", "?")
        transcript += (
            f"\n[Round {rnd} - {role}]\n"
            f"Argument: {entry.get('argument', '')}\n"
            f"Key Points: {entry.get('key_points', [])}\n"
            f"Evidence: {entry.get('evidence', [])}\n"
            f"Rebuttals: {entry.get('rebuttals', [])}\n"
        )

    system_prompt = (
        f"You are an impartial financial debate judge. You have read a "
        f"{current_round}-round Bull vs Bear debate about {ticker}. "
        f"Your job is to decide whether the debate has reached sufficient depth "
        f"to inform a final investment recommendation, or whether another round "
        f"is needed.\n\n"
        f"DECISION CRITERIA:\n"
        f"- Rule 'continue' if:\n"
        f"  * Either side has raised a key point the other has NOT rebutted\n"
        f"  * Arguments are still shallow or lacking data citations\n"
        f"  * The sides are still talking past each other\n"
        f"  * Fewer than 3 substantive data points have been contested\n"
        f"- Rule 'concluded' if:\n"
        f"  * Both sides have addressed the other's strongest points\n"
        f"  * The debate has surfaced clear trade-offs and uncertainties\n"
        f"  * Further rounds would just repeat existing arguments\n"
        f"  * A senior analyst reading this could make a decision\n\n"
        f"Return: verdict (continue|concluded), quality_score (0-100), "
        f"reason (one sentence), unresolved_points (if continuing, "
        f"the specific points that still need rebuttal), "
        f"bull_strength and bear_strength (0-100).\n\n"
        f"This is round {current_round} of max {MAX_DEBATE_ROUNDS}. "
        f"Don't be shy about demanding another round if the debate is weak, "
        f"but don't be stubborn about requesting more if both sides have done their job."
    ) + language_directive(language)

    try:
        result = call_llm_structured(
            user_prompt=transcript,
            response_model=JudgeDecision,
            system_prompt=system_prompt,
            temperature=0.3,
        )
    except Exception as e:
        logger.warning("Judge LLM call failed: %s. Auto-concluding.", e)
        return {
            "debate_judge": {
                "verdict": "concluded",
                "quality_score": 50,
                "reason": f"Judge LLM failed ({type(e).__name__}), auto-concluding.",
                "unresolved_points": [],
                "bull_strength": 50,
                "bear_strength": 50,
                "round_evaluated": current_round,
            },
            "errors": [{"agent": "debate_judge", "error": str(e)}],
        }

    verdict = (result.verdict or "concluded").strip().lower()
    if verdict not in ("continue", "concluded"):
        logger.warning("Judge returned invalid verdict %r, defaulting to 'concluded'", verdict)
        verdict = "concluded"

    logger.info(
        "Judge verdict: %s (quality=%d, bull=%d, bear=%d, round=%d)",
        verdict, result.quality_score, result.bull_strength, result.bear_strength, current_round,
    )

    return {
        "debate_judge": {
            "verdict": verdict,
            "quality_score": result.quality_score,
            "reason": result.reason,
            "unresolved_points": result.unresolved_points,
            "bull_strength": result.bull_strength,
            "bear_strength": result.bear_strength,
            "round_evaluated": current_round,
        },
        "reasoning_chain": [{
            "agent": "debate_judge",
            "round_evaluated": current_round,
            "verdict": verdict,
            "quality_score": result.quality_score,
            "bull_strength": result.bull_strength,
            "bear_strength": result.bear_strength,
            "reason": result.reason,
        }],
    }


def should_continue_debate_with_judge(state: dict) -> str:
    """
    Conditional edge function: reads the latest judge verdict and
    routes to either 'debate' (another round) or 'risk' (done).
    """
    judge = state.get("debate_judge", {})
    verdict = (judge.get("verdict") or "concluded").lower()
    round_num = state.get("debate_round", 0)

    if verdict == "continue" and round_num < MAX_DEBATE_ROUNDS:
        logger.info("Routing: judge says continue, round %d -> debate again", round_num)
        return "debate"
    logger.info("Routing: judge says %s, round %d -> risk", verdict, round_num)
    return "risk"
