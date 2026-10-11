from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    grobid_url: str = "http://localhost:8070"
    port: int = 3001
    openalex_mailto: str = ""
    unpaywall_email: str = ""


settings = Settings()
