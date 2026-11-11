"""Azure OpenAI structured-output helper. Offline mode skips the network."""

from __future__ import annotations

from pydantic import BaseModel

from loan_copilot.config import settings
from loan_copilot.resilience import resilient_call


def azure_ready() -> bool:
    return settings.azure_ready


def deployment_for(kind: str) -> str:
    if kind == "mini":
        return settings.azure_openai_deployment_mini
    return settings.azure_openai_deployment


def complete(kind: str, schema: type[BaseModel], system: str, user: str) -> BaseModel | None:
    """Ask Azure OpenAI for a schema object. Return None when offline or the call fails."""
    if not settings.azure_ready:
        return None

    def _call() -> BaseModel:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import AzureChatOpenAI, ChatOpenAI

        deployment = deployment_for(kind)
        # The RAG Key Vault endpoint is an OpenAI v1 base URL. AzureChatOpenAI
        # is retained for standard Azure resource endpoints.
        # gpt-6.1-terra is a reasoning model and accepts only the default
        # temperature, so temperature is not set. Numbers still come from tools.
        if "/openai/v1" in settings.azure_openai_endpoint.rstrip("/"):
            llm = ChatOpenAI(
                base_url=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                model=deployment,
            )
        else:
            llm = AzureChatOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
                azure_deployment=deployment,
            )
        # gpt-6.1-terra rejects the default json-schema method because the
        # agent models contain dict fields. Function calling accepts them.
        structured = llm.with_structured_output(schema, method="function_calling")
        return structured.invoke([SystemMessage(content=system), HumanMessage(content=user)])

    try:
        return resilient_call("azure-openai", _call)
    except Exception:
        return None


def main() -> None:
    """Print which mode the process is in. With credentials, ask gpt-6.1-terra."""
    if not settings.azure_ready:
        print("Offline mode: Azure OpenAI endpoint or key is empty. Agents use the tool results directly.")
        return
    from pydantic import BaseModel as Model

    class Ping(Model):
        sentence: str

    reply = complete("mini", Ping, "Reply with one short sentence.", "Say the loan copilot is connected.")
    print(reply.sentence if reply else "The model call failed and the breaker or retry limit stopped it.")


if __name__ == "__main__":
    main()
