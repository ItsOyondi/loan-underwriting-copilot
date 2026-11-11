"""Settings for the loan copilot.

The Azure endpoint and key are read from Key Vault using the same secret names
as the existing `rag` project. Direct environment variables remain useful for
local experiments, but take precedence over Key Vault values.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RUNTIME = DATA / "runtime"
log = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Read `.env` from the finUseCase folder. Missing keys use the defaults."""

    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # These two values are populated from Key Vault when USE_KEY_VAULT=true.
    # Explicit .env values override the corresponding vault secret.
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_deployment: str = "gpt-6.1-terra"
    azure_openai_deployment_mini: str = "gpt-6.1-terra"
    azure_openai_deployment_embedding: str = "text-embedding-3-small"

    key_vault_name: str = "clinic-kv-tc-training"
    use_key_vault: bool = False
    key_vault_openai_endpoint_secret: str = "az-openai-endpoint"
    key_vault_openai_key_secret: str = "az-openai-apikey"
    key_vault_search_key_secret: str = "clinic-ss-api-key"
    key_vault_cosmos_connection_secret: str = "cosmos-cxn-str"
    key_vault_cosmos_key_secret: str = "cosmos-cxn-key"
    key_vault_app_insights_secret: str = "app-insights-cxn-str"

    redis_url: str = ""

    azure_search_endpoint: str = ""
    azure_search_api_key: str = ""
    azure_search_index_policies: str = "loan-policy-memory"
    azure_search_index_precedents: str = "loan-case-precedents"

    cosmos_endpoint: str = ""
    cosmos_key: str = ""
    cosmos_database: str = "loan_underwriting"
    cosmos_container_customers: str = "customers"
    use_cosmos: bool = False
    use_azure_search: bool = False

    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "loan-underwriting-copilot"
    applicationinsights_connection_string: str = ""

    max_retries: int = 3
    cb_failure_threshold: int = 5
    cb_window_seconds: int = 60
    cb_cooldown_seconds: int = 30
    max_revisions: int = 3
    new_loan_rate: float = 0.07

    @property
    def azure_ready(self) -> bool:
        return bool(self.azure_openai_endpoint and self.azure_openai_api_key)


def account_from_cosmos_secret(connection: str, key: str) -> tuple[str, str]:
    """Split the RAG vault secret into an account endpoint and key.

    `cosmos-cxn-str` may be an https endpoint or a connection string.
    `cosmos-cxn-key` is the account key and replaces any AccountKey in that string.
    """
    stored = connection.strip().rstrip(";")
    if stored.lower().startswith("http"):
        return stored, key.strip()
    endpoint = ""
    for part in stored.split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        if name.lower() == "accountendpoint":
            endpoint = value.strip()
    return endpoint, key.strip()


def _optional_secret(client, name: str) -> str:
    """Read one secret. A missing secret returns an empty string."""
    try:
        return _vault_secret(client, name)
    except Exception as exc:
        log.warning("Key Vault secret %s was not loaded: %s", name, exc)
        return ""


def _vault_secret(client, name: str) -> str:
    """Read one non-empty Key Vault secret without exposing it in logs."""
    value = client.get_secret(name).value
    if not value:
        raise ValueError(f"Key Vault secret '{name}' is empty.")
    return value.strip()


def load_settings() -> Settings:
    """Create settings and, when enabled, hydrate credentials from Key Vault.

    `DefaultAzureCredential` uses Azure CLI credentials on a developer
    workstation and managed identity once deployed to Azure, mirroring the RAG
    implementation. Failure leaves the offline MVP usable.
    """
    loaded = Settings()
    if not loaded.use_key_vault:
        return loaded

    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        credential = DefaultAzureCredential(process_timeout=20)
        client = SecretClient(
            vault_url=f"https://{loaded.key_vault_name}.vault.azure.net/",
            credential=credential,
        )
        try:
            if not loaded.azure_openai_endpoint:
                loaded.azure_openai_endpoint = _vault_secret(
                    client, loaded.key_vault_openai_endpoint_secret
                )
            if not loaded.azure_openai_api_key:
                loaded.azure_openai_api_key = _vault_secret(
                    client, loaded.key_vault_openai_key_secret
                )
            if loaded.use_azure_search and not loaded.azure_search_api_key:
                loaded.azure_search_api_key = _vault_secret(
                    client, loaded.key_vault_search_key_secret
                )
            if not loaded.applicationinsights_connection_string:
                loaded.applicationinsights_connection_string = _optional_secret(
                    client, loaded.key_vault_app_insights_secret
                )
            if not loaded.cosmos_endpoint or not loaded.cosmos_key:
                connection = _optional_secret(client, loaded.key_vault_cosmos_connection_secret)
                account_key = _optional_secret(client, loaded.key_vault_cosmos_key_secret)
                endpoint, account_key = account_from_cosmos_secret(connection, account_key)
                if not loaded.cosmos_endpoint:
                    loaded.cosmos_endpoint = endpoint
                if not loaded.cosmos_key:
                    loaded.cosmos_key = account_key
        finally:
            client.close()
            credential.close()
    except Exception as exc:
        log.warning("Key Vault settings were not loaded; offline mode remains available: %s", exc)
    return loaded


settings = load_settings()
RUNTIME.mkdir(parents=True, exist_ok=True)
