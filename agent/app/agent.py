import os

from google.adk.agents.llm_agent import Agent

root_agent = Agent(
    model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
    name="root_agent",
    description="Placeholder agent. Replace once the problem statement is fixed.",
    instruction="Answer user questions concisely.",
)
