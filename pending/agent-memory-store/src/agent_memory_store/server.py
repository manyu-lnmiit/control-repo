"""Optional HTTP API for agent-memory-store, built on FastAPI.

Not imported by the core package — install the ``server`` extra to use it:

    pip install agent-memory-store[server]
    agent-memory-store serve
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .memory import MemoryType
from .store import MemoryStore


class AddRequest(BaseModel):
    content: str
    memory_type: MemoryType = MemoryType.EPISODIC
    importance: float = Field(0.5, ge=0.0, le=1.0)
    tags: list[str] = []
    metadata: dict = {}


class SearchRequest(BaseModel):
    query: str
    k: int = 5
    memory_type: MemoryType | None = None


def build_app(db_path: str = "agent_memory.db") -> FastAPI:
    app = FastAPI(title="agent-memory-store", version="0.1.0")
    store = MemoryStore(db_path=db_path)

    @app.post("/memories")
    def add_memory(req: AddRequest):
        item = store.add(
            content=req.content,
            memory_type=req.memory_type,
            importance=req.importance,
            tags=req.tags,
            metadata=req.metadata,
        )
        return {"id": item.id}

    @app.get("/memories/{memory_id}")
    def get_memory(memory_id: str):
        item = store.get(memory_id)
        if item is None:
            raise HTTPException(status_code=404, detail="memory not found")
        return {
            "id": item.id,
            "content": item.content,
            "memory_type": item.memory_type.value,
            "importance": item.importance,
            "tags": item.tags,
        }

    @app.delete("/memories/{memory_id}")
    def delete_memory(memory_id: str):
        if not store.forget(memory_id):
            raise HTTPException(status_code=404, detail="memory not found")
        return {"deleted": True}

    @app.post("/search")
    def search(req: SearchRequest):
        results = store.search(req.query, k=req.k, memory_type=req.memory_type)
        return [
            {
                "id": item.id,
                "content": item.content,
                "score": score,
                "memory_type": item.memory_type.value,
            }
            for item, score in results
        ]

    @app.post("/maintenance/decay")
    def decay():
        return {"updated": store.decay_all()}

    @app.post("/maintenance/consolidate")
    def consolidate():
        created = store.consolidate()
        return {"created": [item.id for item in created]}

    @app.get("/stats")
    def stats():
        return store.stats()

    return app
