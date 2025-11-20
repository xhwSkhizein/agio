import asyncio
import os
from agio.agent import Agent
from agio.models import Deepseek
from agio.tools import FunctionTool
from agio.memory import SimpleMemory
from agio.db import MongoStorage
from agio.knowledge import ChromaKnowledge
from agio.config import settings

# 1. Tools
def get_user_profile(user_id: str) -> str:
    """Mock tool to get user profile from legacy system."""
    return f"User {user_id} is a software engineer interested in AI Agents."

async def main():
    print("Initializing Production Agent...")
    
    # 2. Initialize Components
    # Storage: Persist run traces to MongoDB
    try:
        storage = MongoStorage() 
        print(f"Connected to MongoDB at {storage.uri}")
    except Exception as e:
        print(f"Warning: MongoDB connection failed ({e}), storage disabled.")
        storage = None

    # Knowledge: RAG from local vector store
    # (In real app, you would ingest documents first)
    knowledge = ChromaKnowledge()
    
    # Memory: Short-term history + Long-term semantic
    memory = SimpleMemory()

    # Model
    model = Deepseek(temperature=0.0)

    # 3. Assembly
    agent = Agent(
        model=model,
        tools=[FunctionTool(get_user_profile)],
        memory=memory,
        knowledge=knowledge,
        storage=storage,
        name="prod_agent",
        system_prompt="You are a helpful AI assistant with access to long-term memory and external knowledge."
    )

    # 4. Simulate a Multi-Turn Conversation
    user_id = "user_123"
    session_id = "session_abc"

    queries = [
        "My name is Hong. I'm building an Agent framework called Agio.", # Turn 1: Provide Info
        "What is my name and what am I building?",                      # Turn 2: Recall Short-term History
        "Do you know what my job is based on my profile?"               # Turn 3: Use Tool
    ]

    for i, q in enumerate(queries):
        print(f"\n\n--- Turn {i+1}: {q} ---")
        full_response = ""
        async for chunk in agent.arun(q, user_id=user_id, session_id=session_id):
            print(chunk, end="", flush=True)
            full_response += chunk
        
        # Simulate user reading time
        await asyncio.sleep(1)

    print("\n\n" + "="*50)
    print("Simulation Completed.")
    print("Check your MongoDB to see the persisted run traces!")

if __name__ == "__main__":
    asyncio.run(main())

