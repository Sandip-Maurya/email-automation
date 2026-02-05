"""Base agent configuration for Pydantic AI agents."""

from pydantic_ai import Agent

from src.config import OPENAI_API_KEY

# Shared agent config: OpenAI model, verbose logging
def create_agent(name: str, system_prompt: str, **kwargs) -> Agent:
    """Create a Pydantic AI agent with OpenAI and shared settings."""
    return Agent(
        name=name,
        model="openai:gpt-4o-mini",
        system_prompt=system_prompt,
        retries=1,
        **kwargs,
    )
