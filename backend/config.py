from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    keycloak_url: str = "http://127.0.0.1:8080"
    keycloak_realm: str = "demo-realm"
    keycloak_client_id: str = "streamlit-app"
    db_path: str = "data/business.db"
    audit_log_path: str = "logs/audit.jsonl"

    @property
    def issuer(self) -> str:
        return f"{self.keycloak_url.rstrip('/')}/realms/{self.keycloak_realm}"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/protocol/openid-connect/certs"


settings = Settings()