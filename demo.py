import asyncio
import os
import random
from agio.agent import Agent
from agio.models import Deepseek
from agio.tools import FunctionTool
from agio.memory import SimpleMemory
from agio.config import settings

# 1. Define some tools
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    print(f"--- Tool Call: get_weather({city}) ---")
    # Mock response
    weathers = ["Sunny", "Rainy", "Cloudy", "Windy"]
    return f"The weather in {city} is {random.choice(weathers)}"

def calculate(a: int, b: int, op: str) -> int:
    """Perform basic calculation (add, sub, mul)."""
    print(f"--- Tool Call: calculate({a}, {b}, {op}) ---")
    if op == "add":
        return a + b
    elif op == "sub":
        return a - b
    elif op == "mul":
        return a * b
    return 0

async def main():
    print("Initializing Agent...")
    
    # 2. Configure Model (ensure you have AGIO_DEEPSEEK_API_KEY env var set or in .env)
    # If not set, this might fail or use a default mock if we had one.
    # For this demo, we assume the user will set it.
    if not os.getenv("AGIO_DEEPSEEK_API_KEY") and not os.getenv("DEEPSEEK_API_KEY"):
        print("WARNING: AGIO_DEEPSEEK_API_KEY not found. Please set it in .env or environment variables.")
        # You can uncomment this line to test with a fake key if you just want to see the error handling
        # os.environ["DEEPSEEK_API_KEY"] = "fake-key"

    model = Deepseek(
        temperature=0.0
    )

    # 3. Initialize Agent
    agent = Agent(
        model=model,
        tools=[
            FunctionTool(get_weather),
            FunctionTool(calculate)
        ],
        memory=SimpleMemory(),
        name="demo_agent"
    )

    # 4. Run Agent
    query = "What's the weather in Beijing? And what is 15 * 12?"
    print(f"\nUser Query: {query}\n")
    print("-" * 50)

    full_response = ""
    try:
        async for chunk in agent.arun(query):
            print(chunk, end="", flush=True)
            full_response += chunk
    except Exception as e:
        print(f"\n\n[Error]: {e}")

    print("\n" + "-" * 50)
    print("\nRun Completed.")
    
    # 5. Inspect Metrics (Optional, if we exposed run object return)
    # Currently arun yields strings. In a real app, we might want access to the run object.
    # We can check storage if we had one configured.

if __name__ == "__main__":
    asyncio.run(main())

