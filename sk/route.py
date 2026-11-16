"""Route sample loan cases to an approver.

Sign in with `az login` first. When AZURE_OPENAI_API_KEY is empty, credentials
come from clinic-kv-tc-training. Run this file from the sk folder:

    .\.venv\Scripts\python route.py
"""

from __future__ import annotations

import asyncio

from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
from semantic_kernel.functions.kernel_arguments import KernelArguments
from semantic_kernel.kernel import Kernel

from credentials import load_credentials
from handlers import invoke_route
from kernel_factory import build_kernel
from routes import PLUGIN_NAME, ROUTE_FUNCTIONS, ApprovalRoutes

CASES = (
    "Maple Street Bakery requests $750,000. Risk grade 3.",
    "Northwind Packaging requests $1,500,000. Risk grade 3.",
    "Lakeshore Foods requests $4,000,000. Risk grade 6.",
    "Summit Steel requests $28,000,000. Risk grade 3.",
)


async def route_case(kernel: Kernel, routes: ApprovalRoutes, case_summary: str) -> None:
    """Ask the model to call exactly one route for this case."""
    routes.chosen = ""
    settings = OpenAIChatPromptExecutionSettings(
        function_choice_behavior=FunctionChoiceBehavior.Required(
            filters={"included_functions": list(ROUTE_FUNCTIONS)}
        ),
        # gpt-6.1-terra rejects function tools on chat completions unless
        # reasoning is turned off. "none" is not in the client's enum.
        extra_body={"reasoning_effort": "none"},
    )
    reply = await kernel.invoke_prompt(
        "Choose exactly one approval route for this loan case: {{$case}}",
        arguments=KernelArguments(settings=settings, case=case_summary),
    )
    action = invoke_route(routes.chosen, case_summary)
    print(case_summary)
    print(f"  route: {routes.chosen or '(none)'}")
    print(f"  reply: {reply}")
    print(f"  action: {action}")
    print()


async def main() -> None:
    endpoint, key, deployment = load_credentials()
    kernel = build_kernel(endpoint, key, deployment)
    routes = ApprovalRoutes()
    kernel.add_plugin(routes, plugin_name=PLUGIN_NAME)
    for case_summary in CASES:
        await route_case(kernel, routes, case_summary)


if __name__ == "__main__":
    asyncio.run(main())
