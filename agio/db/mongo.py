"""
MongoDB implementation of AgentRunRepository.
"""

from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorClient
from agio.domain.run import AgentRun
from agio.domain.step import Step
from agio.protocol.events import AgentEvent, EventType
from agio.db.repository import AgentRunRepository, StoredEvent
from agio.utils.logging import get_logger

logger = get_logger(__name__)


def filter_none_values(data: dict) -> dict:
    """
    Recursively filter out None values from a dictionary.
    MongoDB doesn't require this but it keeps the database cleaner.
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


class MongoDBRepository(AgentRunRepository):
    """
    MongoDB implementation of AgentRunRepository.

    Collections:
    - runs: Stores AgentRun documents
    - steps: Stores Step documents (NEW)
    - events: Stores AgentEvent documents (DEPRECATED)
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
        self.events_collection = None

    async def _ensure_connection(self):
        """Ensure database connection is established."""
        if self.client is None:
            self.client = AsyncIOMotorClient(self.uri)
            self.db = self.client[self.db_name]
            self.runs_collection = self.db["runs"]
            self.steps_collection = self.db["steps"]
            self.events_collection = self.db["events"]

            # Create indexes for runs
            await self.runs_collection.create_index("id", unique=True)
            await self.runs_collection.create_index("agent_id")
            await self.runs_collection.create_index("user_id")
            await self.runs_collection.create_index("session_id")
            await self.runs_collection.create_index("created_at")

            # Create indexes for steps (NEW)
            await self.steps_collection.create_index("id", unique=True)
            await self.steps_collection.create_index(
                [("session_id", 1), ("sequence", 1)], unique=True
            )
            await self.steps_collection.create_index("run_id")
            await self.steps_collection.create_index("created_at")

            # Create indexes for events (DEPRECATED)
            await self.events_collection.create_index([("run_id", 1), ("sequence", 1)])

            logger.info("mongodb_connected", uri=self.uri, db_name=self.db_name)

    async def save_run(self, run: AgentRun) -> None:
        """Save or update a run."""
        await self._ensure_connection()

        try:
            # Convert to dict and filter None values
            run_data = run.model_dump(mode="json")
            run_data = filter_none_values(run_data)

            # Upsert based on run id
            await self.runs_collection.update_one(
                {"id": run.id}, {"$set": run_data}, upsert=True
            )

            logger.debug("run_saved", run_id=run.id)

        except Exception as e:
            logger.error("save_run_failed", run_id=run.id, error=str(e), exc_info=True)
            raise

    async def get_run(self, run_id: str) -> Optional[AgentRun]:
        """Get a run by ID."""
        await self._ensure_connection()

        try:
            doc = await self.runs_collection.find_one({"id": run_id})

            if not doc:
                return None

            # Remove MongoDB _id field
            if "_id" in doc:
                del doc["_id"]

            return AgentRun.model_validate(doc)

        except Exception as e:
            logger.error("get_run_failed", run_id=run_id, error=str(e), exc_info=True)
            raise

    async def save_event(self, event: AgentEvent, sequence: int) -> None:
        """Save an event."""
        await self._ensure_connection()

        try:
            # Create stored event
            stored_event = StoredEvent(
                run_id=event.run_id,
                sequence=sequence,
                event_type=event.type.value,
                timestamp=event.timestamp,
                data=event.data,
                metadata=event.metadata,
            )

            # Convert to dict and filter None values
            event_data = stored_event.model_dump(mode="json")
            event_data = filter_none_values(event_data)

            # Insert event
            await self.events_collection.insert_one(event_data)

            logger.debug("event_saved", run_id=event.run_id, sequence=sequence)

        except Exception as e:
            logger.error(
                "save_event_failed", run_id=event.run_id, error=str(e), exc_info=True
            )
            raise

    async def get_events(
        self, run_id: str, offset: int = 0, limit: int = 100
    ) -> List[AgentEvent]:
        """Get events for a run with pagination."""
        await self._ensure_connection()

        try:
            cursor = (
                self.events_collection.find({"run_id": run_id})
                .sort("sequence", 1)
                .skip(offset)
                .limit(limit)
            )

            events = []
            async for doc in cursor:
                # Remove MongoDB _id
                if "_id" in doc:
                    del doc["_id"]

                # Convert back to AgentEvent
                event = AgentEvent(
                    type=EventType(doc["event_type"]),
                    run_id=doc["run_id"],
                    timestamp=doc["timestamp"],
                    data=doc["data"],
                    metadata=doc.get("metadata", {}),
                )
                events.append(event)

            return events

        except Exception as e:
            logger.error(
                "get_events_failed", run_id=run_id, error=str(e), exc_info=True
            )
            raise

    async def get_event_count(self, run_id: str) -> int:
        """Get total count of events for a run."""
        await self._ensure_connection()

        try:
            count = await self.events_collection.count_documents({"run_id": run_id})
            return count

        except Exception as e:
            logger.error(
                "get_event_count_failed", run_id=run_id, error=str(e), exc_info=True
            )
            raise

    async def list_runs(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[AgentRun]:
        """List runs with optional filtering."""
        await self._ensure_connection()

        try:
            # Build query
            query = {}
            if user_id:
                query["user_id"] = user_id
            if agent_id:
                query["agent_id"] = agent_id
            if status:
                query["status"] = status

            # Execute query with pagination
            cursor = (
                self.runs_collection.find(query)
                .sort("created_at", -1)
                .skip(offset)
                .limit(limit)
            )

            runs = []
            async for doc in cursor:
                # Remove MongoDB _id
                if "_id" in doc:
                    del doc["_id"]

                runs.append(AgentRun.model_validate(doc))

            logger.debug("runs_listed", count=len(runs), filters=query)
            return runs

        except Exception as e:
            logger.error("list_runs_failed", error=str(e), exc_info=True)
            raise

    # --- Step Operations (NEW) ---

    async def save_step(self, step: Step) -> None:
        """Save a single step."""
        await self._ensure_connection()

        try:
            step_data = step.model_dump(mode="json")
            step_data = filter_none_values(step_data)

            # Upsert based on step id
            await self.steps_collection.update_one(
                {"id": step.id}, {"$set": step_data}, upsert=True
            )

            logger.debug("step_saved", step_id=step.id, session_id=step.session_id)

        except Exception as e:
            logger.error(
                "save_step_failed", step_id=step.id, error=str(e), exc_info=True
            )
            raise

    async def save_steps_batch(self, steps: List[Step]) -> None:
        """Batch save steps (for fork operation)."""
        await self._ensure_connection()

        try:
            if not steps:
                return

            operations = []
            for step in steps:
                step_data = step.model_dump(mode="json")
                step_data = filter_none_values(step_data)
                operations.append(
                    {
                        "update_one": {
                            "filter": {"id": step.id},
                            "update": {"$set": step_data},
                            "upsert": True,
                        }
                    }
                )

            await self.steps_collection.bulk_write(operations)

            logger.debug("steps_batch_saved", count=len(steps))

        except Exception as e:
            logger.error("save_steps_batch_failed", error=str(e), exc_info=True)
            raise

    async def get_steps(
        self,
        session_id: str,
        start_seq: Optional[int] = None,
        end_seq: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Step]:
        """Get steps for a session, optionally filtered by sequence range."""
        await self._ensure_connection()

        try:
            query = {"session_id": session_id}

            if start_seq is not None:
                query["sequence"] = {"$gte": start_seq}
            if end_seq is not None:
                if "sequence" in query:
                    query["sequence"]["$lte"] = end_seq
                else:
                    query["sequence"] = {"$lte": end_seq}

            cursor = self.steps_collection.find(query).sort("sequence", 1).limit(limit)

            steps = []
            async for doc in cursor:
                if "_id" in doc:
                    del doc["_id"]
                steps.append(Step.model_validate(doc))

            return steps

        except Exception as e:
            logger.error(
                "get_steps_failed", session_id=session_id, error=str(e), exc_info=True
            )
            raise

    async def get_last_step(self, session_id: str) -> Optional[Step]:
        """Get the last step in a session."""
        await self._ensure_connection()

        try:
            doc = await self.steps_collection.find_one(
                {"session_id": session_id}, sort=[("sequence", -1)]
            )

            if not doc:
                return None

            if "_id" in doc:
                del doc["_id"]

            return Step.model_validate(doc)

        except Exception as e:
            logger.error(
                "get_last_step_failed",
                session_id=session_id,
                error=str(e),
                exc_info=True,
            )
            raise

    async def delete_steps(self, session_id: str, start_seq: int) -> int:
        """Delete steps with sequence >= start_seq."""
        await self._ensure_connection()

        try:
            result = await self.steps_collection.delete_many(
                {"session_id": session_id, "sequence": {"$gte": start_seq}}
            )

            deleted_count = result.deleted_count
            logger.info(
                "steps_deleted",
                session_id=session_id,
                start_seq=start_seq,
                count=deleted_count,
            )

            return deleted_count

        except Exception as e:
            logger.error(
                "delete_steps_failed",
                session_id=session_id,
                error=str(e),
                exc_info=True,
            )
            raise

    async def get_step_count(self, session_id: str) -> int:
        """Get total step count for a session."""
        await self._ensure_connection()

        try:
            count = await self.steps_collection.count_documents(
                {"session_id": session_id}
            )
            return count

        except Exception as e:
            logger.error(
                "get_step_count_failed",
                session_id=session_id,
                error=str(e),
                exc_info=True,
            )
            raise

    # --- Old Methods ---

    async def delete_run(self, run_id: str) -> None:
        """Delete a run and its events."""
        await self._ensure_connection()

        try:
            # Delete run
            await self.runs_collection.delete_one({"id": run_id})

            # Delete associated events
            await self.events_collection.delete_many({"run_id": run_id})

            logger.info("run_deleted", run_id=run_id)

        except Exception as e:
            logger.error(
                "delete_run_failed", run_id=run_id, error=str(e), exc_info=True
            )
            raise

    async def close(self):
        """Close database connection."""
        if self.client:
            self.client.close()
            logger.info("mongodb_disconnected")
