from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    aws_region: str = "us-east-1"
    primary_model_id: str = "us.anthropic.claude-opus-4-8"
    fallback_model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    log_level: str = "INFO"
    latency_threshold_ms: int = 30_000


settings = Settings()
