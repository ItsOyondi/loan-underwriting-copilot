"""Build a kernel pointed at Azure OpenAI."""

from __future__ import annotations

import os

from semantic_kernel.kernel import Kernel


def build_kernel(endpoint: str, key: str, deployment: str) -> Kernel:
    """Use the v1 base URL when the endpoint contains it, otherwise the Azure client."""
    kernel = Kernel()
    endpoint = endpoint.rstrip("/")
    if "/openai/v1" in endpoint:
        from openai import AsyncOpenAI
        from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

        client = AsyncOpenAI(api_key=key, base_url=endpoint)
        service = OpenAIChatCompletion(ai_model_id=deployment, async_client=client)
    else:
        from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion

        service = AzureChatCompletion(
            deployment_name=deployment,
            endpoint=endpoint,
            api_key=key,
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        )
    kernel.add_service(service)
    return kernel
