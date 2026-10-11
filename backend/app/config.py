from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    grobid_url: str = "http://localhost:8070"
    port: int = 3001
    openalex_mailto: str = ""
    unpaywall_email: str = ""

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):
        # backend/.env wins over shell environment variables, so a stale exported
        # OPENAI_API_KEY (e.g. in ~/.zshrc) cannot silently override the file.
        return (init_settings, dotenv_settings, env_settings, file_secret_settings)


settings = Settings()
