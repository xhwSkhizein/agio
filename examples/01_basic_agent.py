"""
Example 1: Basic Agent

This example demonstrates the simplest way to create and use an Agio agent.
"""
import asyncio
from agio.agent.base import Agent
from agio.models.openai import OpenAIModel


async def main():
    """Create a basic agent and run a simple query."""
    
    # Create an agent with just a model
    agent = Agent(
        model=OpenAIModel(),
        name="basic_agent",
        system_prompt="You are a helpful assistant."
    )
    
    # Simple text streaming
    print("User: Hello, who are you?")
    print("Agent: ", end="", flush=True)
    
    async for chunk in agent.arun("Hello, who are you?"):
        print(chunk, end="", flush=True)
    
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())
