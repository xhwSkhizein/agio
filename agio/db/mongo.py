from motor.motor_asyncio import AsyncIOMotorClient
from agio.db.base import Storage
from agio.domain.run import AgentRun
from agio.config import settings

class MongoStorage(Storage):
    def __init__(self, db_name: str = "agio", collection_name: str = "runs", uri: str | None = None):
        self.uri = uri or settings.mongo_uri or "mongodb://localhost:27017"
        self.db_name = db_name
        self.collection_name = collection_name
        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client[self.db_name]
        self.collection = self.db[self.collection_name]

    async def upsert_run(self, run: AgentRun) -> None:
        # Convert Pydantic model to dict, handling datetime serialization usually handled by mongo driver or pydantic
        # Pydantic's model_dump(mode='json') converts datetime to string (ISO), 
        # but Mongo can store native datetime. standard model_dump() keeps datetime objects.
        run_data = run.model_dump(mode='json') 
        
        # Upsert based on run_id
        await self.collection.update_one(
            {"id": run.id},
            {"$set": run_data},
            upsert=True
        )

    async def get_run(self, run_id: str) -> AgentRun | None:
        data = await self.collection.find_one({"id": run_id})
        if data:
            # We need to handle _id from mongo if we want to be clean, but Pydantic ignores extra fields by default
            if "_id" in data:
                del data["_id"]
            return AgentRun.model_validate(data)
        return None

    async def list_runs(self, agent_id: str, limit: int = 10) -> list[AgentRun]:
        cursor = self.collection.find({"agent_id": agent_id}).sort("created_at", -1).limit(limit)
        runs = []
        async for doc in cursor:
            if "_id" in doc:
                del doc["_id"]
            runs.append(AgentRun.model_validate(doc))
        return runs

