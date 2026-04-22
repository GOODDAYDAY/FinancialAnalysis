"""Application configuration via environment variables, loaded through Pydantic BaseSettings."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 4096
    debate_max_rounds: int = 2
    debate_temperature: float = 0.7
    agent_timeout: int = 30
    log_level: str = "INFO"

    # MLflow experiment tracking
    mlflow_tracking_uri: str = ""  # empty = local mlruns directory
    mlflow_experiment_name: str = "investment-research"

    model_config = {
        "env_file": str(Path(__file__).resolve().parent.parent / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
