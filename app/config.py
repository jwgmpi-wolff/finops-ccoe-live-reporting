from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FinOps CCoE Live Reporting"
    strict_live_mode_default: bool = True
    arm_resource: str = "https://management.azure.com/.default"
    graph_resource: str = "https://graph.microsoft.com/.default"
    entra_client_id: str = ""
    entra_authority: str = "https://login.microsoftonline.com/organizations"
    entra_redirect_uri: str = "http://127.0.0.1:8010"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FINOPS_",
        extra="ignore",
    )


settings = Settings()
