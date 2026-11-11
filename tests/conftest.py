"""Keep the test suite offline.

The app reads `.env`, which can turn on Key Vault, Cosmos, and Azure AI Search.
Tests must not depend on those services, so this file switches them off before
any loan_copilot module is imported. Set LOAN_COPILOT_LIVE=1 to skip this and
run the suite against the configured Azure services.
"""

import os

if os.environ.get("LOAN_COPILOT_LIVE") != "1":
    os.environ["USE_KEY_VAULT"] = "false"
    os.environ["USE_COSMOS"] = "false"
    os.environ["USE_AZURE_SEARCH"] = "false"
    os.environ["AZURE_OPENAI_ENDPOINT"] = ""
    os.environ["AZURE_OPENAI_API_KEY"] = ""
    os.environ["REDIS_URL"] = ""
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"] = ""
