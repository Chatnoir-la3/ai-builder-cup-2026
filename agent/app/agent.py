import os

from google.adk.agents.llm_agent import Agent
from google.adk.apps import App
from google.adk.plugins.base_plugin import BasePlugin

root_agent = Agent(
    model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
    name="root_agent",
    description="Placeholder agent. Replace once the problem statement is fixed.",
    instruction="Answer user questions concisely.",
)


def _plugins() -> list[BasePlugin]:
    """Guardrail and audit plugins, enabled only when their env vars are set (unset in local dev)."""
    plugins: list[BasePlugin] = []
    template = os.getenv("MODEL_ARMOR_TEMPLATE")
    if template:
        from google.adk.integrations.model_armor import ModelArmorConfig, ModelArmorPlugin

        plugins.append(
            ModelArmorPlugin(config=ModelArmorConfig(prompt_template_name=template, response_template_name=template))
        )
    dataset = os.getenv("AUDIT_DATASET")
    if dataset:
        from google.adk.plugins.bigquery_agent_analytics_plugin import BigQueryAgentAnalyticsPlugin

        plugins.append(
            BigQueryAgentAnalyticsPlugin(
                project_id=os.environ["GOOGLE_CLOUD_PROJECT"],
                dataset_id=dataset,
                location=os.getenv("AUDIT_LOCATION", "asia-southeast1"),
            )
        )
    return plugins


app = App(name="app", root_agent=root_agent, plugins=_plugins())
