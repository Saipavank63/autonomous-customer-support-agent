from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    openai_api_key: str = Field(..., description="OpenAI API key")
    database_url: str = Field(
        "postgresql+asyncpg://support_agent:support_agent@localhost:5432/support_agent"
    )
    database_url_sync: str = Field(
        "postgresql://support_agent:support_agent@localhost:5432/support_agent"
    )

    twilio_account_sid: str = Field("", description="Twilio account SID")
    twilio_auth_token: str = Field("", description="Twilio auth token")
    twilio_from_number: str = Field("", description="Twilio sender number")

    app_env: str = "development"
    log_level: str = "INFO"
    agent_model: str = "gpt-4o"
    agent_temperature: float = 0.1
    memory_window_size: int = 20
    max_refund_amount: float = 500.00

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
