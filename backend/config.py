from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql://filings:filings@localhost:5432/filings_iq"
    openai_api_key: str = ""
    sec_user_agent: str = "FilingsIQ tvharshawardhan@gmail.com"
    log_level: str = "INFO"
    environment: str = "development"

    # Supported tickers (Phase 1)
    supported_tickers: list[str] = ["MSFT", "AAPL", "JPM", "GS", "NVDA"]


settings = Settings()
