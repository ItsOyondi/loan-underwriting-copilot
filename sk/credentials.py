"""Azure OpenAI settings from the environment, then Key Vault."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def _from_key_vault() -> tuple[str, str]:
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    vault = os.environ.get("KEY_VAULT_NAME", "clinic-kv-tc-training")
    credential = DefaultAzureCredential(process_timeout=20)
    client = SecretClient(vault_url=f"https://{vault}.vault.azure.net/", credential=credential)
    try:
        endpoint = client.get_secret("az-openai-endpoint").value or ""
        key = client.get_secret("az-openai-apikey").value or ""
    finally:
        client.close()
        credential.close()
    return endpoint.strip(), key.strip()


def load_credentials() -> tuple[str, str, str]:
    """Return the endpoint, key, and deployment name."""
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip()
    key = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-6.1-terra").strip()
    if not endpoint or not key:
        endpoint, key = _from_key_vault()
    if not endpoint or not key:
        raise SystemExit("Azure OpenAI endpoint or key is empty.")
    return endpoint, key, deployment
