from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_redirect_uri: str = "http://localhost:8000/auth/linkedin/callback"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tross"

    session_cookie_name: str = "tross_session"
    session_secret: str = "change-me-in-production"

    # Comma-separated OpenID Connect scopes granted by the LinkedIn app.
    # "openid profile email" is the standard "Sign In with LinkedIn using OpenID Connect" product.
    linkedin_scopes: str = "openid profile email"


settings = Settings()
