from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    aws_region: str = "us-east-1"
    primary_model_id: str = "us.anthropic.claude-opus-4-8"
    fallback_model_id: str = "us.anthropic.claude-haiku-4-5-20251001"
    log_level: str = "INFO"
    latency_threshold_ms: int = 30_000

    class Config:
        env_file = ".env"


settings = Settings()
