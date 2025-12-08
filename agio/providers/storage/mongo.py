"""
MongoDB implementation of SessionStore.
"""

from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorClient

from agio.providers.storage.base import SessionStore
from agio.domain import AgentRun, Step
from agio.utils.logging import get_logger

logger = get_logger(__name__)


def filter_none_values(data: dict) -> dict:
    """
    Recursively filter out None values from a dictionary.
    """
    if not isinstance(data, dict):
        return data

    filtered = {}
    for key, value in data.items():
        if value is None:
            continue
        elif isinstance(value, dict):
            filtered[key] = filter_none_values(value)
        elif isinstance(value, list):
            filtered[key] = [
                filter_none_values(item) if isinstance(item, dict) else item
                for item in value
                if item is not None
            ]
        else:
            filtered[key] = value

    return filtered


class MongoSessionStore(SessionStore):
    """
    MongoDB implementation of SessionStore.

    Collections:
    - runs: Stores AgentRun documents
    - steps: Stores Step documents
    """

    def __init__(
        self,
        uri: str = "mongodb://localhost:27017",
        db_name: str = "agio",
    ):
        self.uri = uri
        self.db_name = db_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self.runs_collection = None
        self.steps_collection = None

    async def _ensure_connection(self):
        """Ensure database connection is established."""
        if self.client is None:
            self.client = AsyncIOMotorClient(self.uri)
            self.db = self.client[self.db_name]
            self.runs_collection = self.db["runs"]
            self.steps_collection = self.db["steps"]

            # Create indexes for runs
            await self.runs_collection.create_index("id", unique=True)
            await self.runs_collection.create_index("agent_id")
            await self.runs_collection.create_index("user_id")
            await self.runs_collection.create_index("session_id")
            await self.runs_collection.create_index("created_at")

            # Create indexes for steps
            await self.steps_collection.create_index("id", unique=True)
            await self.steps_collection.create_index(
                [("session_id", 1), ("sequence", 1)], unique=True
            )
            await self.steps_collection.create_index("run_id")
            await self.steps_collection.create_index("created_at")

            logger.info("mongodb_connected", uri=self.uri, db_name=self.db_name)

    async def save_run(self, run: AgentRun) -> None:
        """Save or update a run."""
        await self._ensure_connection()

        try:
            run_data = run.model_dump(mode="json")
            run_data = filter_none_values(run_data)

            await self.runs_collection.update_one({"id": run.id}, {"$set": run_data}, upsert=True)
        except Exception as e:
            logger.error("save_run_failed", error=str(e), run_id=run.id)
            raise

    async def get_run(self, run_id: str) -> Optional[AgentRun]:
        """Get a run by ID."""
        await self._ensure_connection()

        try:
            doc = await self.runs_collection.find_one({"id": run_id})
            if doc:
                return AgentRun.model_validate(doc)
            return None
        except Exception as e:
            logger.error("get_run_failed", error=str(e), run_id=run_id)
            raise

    async def list_runs(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[AgentRun]:
        """List runs with filtering and pagination."""
        await self._ensure_connection()

        try:
            query = {}
            if user_id:
                query["user_id"] = user_id
            if session_id:
                query["session_id"] = session_id

            cursor = (
                self.runs_collection.find(query).sort("created_at", -1).skip(offset).limit(limit)
            )

            runs = []
            async for doc in cursor:
                runs.append(AgentRun.model_validate(doc))
            return runs
        except Exception as e:
            logger.error("list_runs_failed", error=str(e))
            raise

    async def delete_run(self, run_id: str) -> None:
        """Delete a run and its associated steps."""
        await self._ensure_connection()

        try:
            run = await self.get_run(run_id)
            await self.runs_collection.delete_one({"id": run_id})

            if run and run.session_id:
                await self.steps_collection.delete_many({"session_id": run.session_id})

        except Exception as e:
            logger.error("delete_run_failed", error=str(e), run_id=run_id)
            raise

    # --- Step Operations ---

    async def save_step(self, step: Step) -> None:
        """Save or update a step."""
        await self._ensure_connection()

        try:
            step_data = step.model_dump(mode="json")
            step_data = filter_none_values(step_data)

            await self.steps_collection.update_one(
                {"id": step.id}, {"$set": step_data}, upsert=True
            )
        except Exception as e:
            logger.error("save_step_failed", error=str(e), step_id=step.id)
            raise

    async def save_steps_batch(self, steps: List[Step]) -> None:
        """Batch save steps."""
        if not steps:
            return

        await self._ensure_connection()

        try:
            operations = []
            for step in steps:
                step_data = step.model_dump(mode="json")
                step_data = filter_none_values(step_data)

                from pymongo import UpdateOne

                operations.append(UpdateOne({"id": step.id}, {"$set": step_data}, upsert=True))

            if operations:
                await self.steps_collection.bulk_write(operations)
        except Exception as e:
            logger.error("save_steps_batch_failed", error=str(e), count=len(steps))
            raise

    async def get_steps(
        self,
        session_id: str,
        start_seq: Optional[int] = None,
        end_seq: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Step]:
        """Get steps for a session."""
        await self._ensure_connection()

        try:
            query = {"session_id": session_id}

            if start_seq is not None or end_seq is not None:
                query["sequence"] = {}
                if start_seq is not None:
                    query["sequence"]["$gte"] = start_seq
                if end_seq is not None:
                    query["sequence"]["$lte"] = end_seq

            cursor = self.steps_collection.find(query).sort("sequence", 1).limit(limit)

            steps = []
            async for doc in cursor:
                steps.append(Step.model_validate(doc))
            return steps
        except Exception as e:
            logger.error("get_steps_failed", error=str(e), session_id=session_id)
            raise

    async def get_last_step(self, session_id: str) -> Optional[Step]:
        """Get the last step of a session."""
        await self._ensure_connection()

        try:
            cursor = (
                self.steps_collection.find({"session_id": session_id}).sort("sequence", -1).limit(1)
            )

            async for doc in cursor:
                return Step.model_validate(doc)
            return None
        except Exception as e:
            logger.error("get_last_step_failed", error=str(e), session_id=session_id)
            raise

    async def delete_steps(self, session_id: str, start_seq: int) -> int:
        """Delete steps from a sequence number onwards."""
        await self._ensure_connection()

        try:
            result = await self.steps_collection.delete_many(
                {"session_id": session_id, "sequence": {"$gte": start_seq}}
            )
            return result.deleted_count
        except Exception as e:
            logger.error("delete_steps_failed", error=str(e), session_id=session_id)
            raise

    async def get_step_count(self, session_id: str) -> int:
        """Get total number of steps for a session."""
        await self._ensure_connection()

        try:
            return await self.steps_collection.count_documents({"session_id": session_id})
        except Exception as e:
            logger.error("get_step_count_failed", error=str(e), session_id=session_id)
            raise


__all__ = ["MongoSessionStore"]
