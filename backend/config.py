"""Application configuration via environment variables."""

import os
from dataclasses import dataclass


@dataclass
class Settings:
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 4096
    debate_max_rounds: int = 2
    debate_temperature: float = 0.7
    agent_timeout: int = 30
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            debate_max_rounds=int(os.getenv("DEBATE_MAX_ROUNDS", "2")),
            debate_temperature=float(os.getenv("DEBATE_TEMPERATURE", "0.7")),
            agent_timeout=int(os.getenv("AGENT_TIMEOUT", "30")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


settings = Settings.from_env()
