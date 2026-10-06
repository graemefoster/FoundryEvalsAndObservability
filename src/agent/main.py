import os

import tools
from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from configuration import read_config


def main() -> None:
    with DefaultAzureCredential() as credential:
        config = read_config(credential=credential)
        client = FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=config.model,
            credential=credential,
        )
        agent = Agent(
            client=client,
            name="purchasing-advice-demo",
            instructions=(
                f"{config.instructions}\n\n"
                f"Scenario reference date (UTC): {tools.REFERENCE_DATE.isoformat()}."
            ),
            tools=config.apply_tool_descriptions(
                [tool(tools.search_policies), tool(tools.search_workplace_notices)]
            ),
            default_options={
                "store": False,
                "reasoning": {"effort": "low"},
                **({"temperature": config.temperature} if config.temperature is not None else {}),
            },
        )
        ResponsesHostServer(agent).run()


if __name__ == "__main__":
    main()
