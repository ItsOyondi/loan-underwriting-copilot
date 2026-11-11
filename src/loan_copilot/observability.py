"""Turn on LangSmith and Azure Monitor when their settings are present."""

from __future__ import annotations

import logging
import os

from loan_copilot.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("azure").setLevel(logging.WARNING)
log = logging.getLogger("loan_copilot")


def setup_observability() -> None:
    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        log.info("LangSmith tracing is on for project %s", settings.langsmith_project)
    if not settings.applicationinsights_connection_string:
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=settings.applicationinsights_connection_string)
        log.info("Azure Monitor export is on")
    except Exception as exc:
        log.info("Azure Monitor export was not started: %s", exc)
