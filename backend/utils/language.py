"""
Language detection for user queries.

Determines whether the user's input is primarily Chinese or English,
so all downstream agents can produce reports in the matching language.
"""


def detect_language(text: str) -> str:
    """
    Detect the language of a query.

    Rule:
        - At least 2 CJK characters anywhere in the text -> "zh"
        - Otherwise -> "en"

    The 2-character minimum prevents a single Chinese name embedded in
    an English sentence from flipping the report to Chinese, while still
    catching cases like "分析茅台" (4 CJK chars, clearly Chinese intent).
    """
    if not text:
        return "en"

    cjk_count = 0
    for ch in text:
        cp = ord(ch)
        # CJK Unified Ideographs (basic + extension A)
        if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
            cjk_count += 1
            if cjk_count >= 2:
                return "zh"

    return "en"


def language_directive(language: str) -> str:
    """
    Build a directive string to append to LLM system prompts so that
    the LLM responds in the requested language.

    Args:
        language: "zh" or "en"

    Returns:
        A short instruction string.
    """
    if language == "zh":
        return (
            "\n\nIMPORTANT: Respond in SIMPLIFIED CHINESE (简体中文). "
            "All natural language fields in your output (reasoning, summary, "
            "arguments, key points, factors, etc.) must be written in Chinese. "
            "Keep stock tickers, numerical values, and JSON field names in English."
        )
    return (
        "\n\nIMPORTANT: Respond in ENGLISH. "
        "All natural language fields in your output must be written in English."
    )
