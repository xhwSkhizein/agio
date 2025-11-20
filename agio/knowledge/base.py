from abc import ABC, abstractmethod

class Knowledge(ABC):
    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> list[str]:
        """
        检索外部知识库 (RAG)
        """
        pass

