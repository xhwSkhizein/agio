"""
Example 2: Agent with Tools

This example shows how to add tools to an agent.
"""
import asyncio
from agio.agent.base import Agent
from agio.models.openai import OpenAIModel
from agio.tools.local import tool


@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    # In a real application, this would call a weather API
    weather_data = {
        "Beijing": "Sunny, 25°C",
        "Shanghai": "Cloudy, 22°C",
        "Shenzhen": "Rainy, 28°C",
    }
    return weather_data.get(city, f"Weather data not available for {city}")


@tool
def calculate(a: float, b: float, operation: str = "add") -> float:
    """
    Perform a mathematical calculation.
    
    Args:
        a: First number
        b: Second number
        operation: Operation to perform (add, subtract, multiply, divide)
    """
    operations = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x / y if y != 0 else "Error: Division by zero",
    }
    
    if operation in operations:
        result = operations[operation](a, b)
        return result
    else:
        return f"Unknown operation: {operation}"


async def main():
    """Create an agent with tools."""
    
    agent = Agent(
        model=OpenAIModel(),
        tools=[get_weather, calculate],
        name="tool_agent",
        system_prompt="You are a helpful assistant with access to weather and calculation tools."
    )
    
    # Query that requires tool use
    query = "What's the weather in Beijing? Also, what is 15 * 12?"
    
    print(f"User: {query}")
    print("Agent: ", end="", flush=True)
    
    async for chunk in agent.arun(query):
        print(chunk, end="", flush=True)
    
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())
