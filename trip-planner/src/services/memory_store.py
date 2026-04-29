from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class MemoryEntry:
    id: str
    created_at: float
    user_id: str
    destination: str
    text: str
    embedding: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ChromaMemoryStore:
    """Persistent vector memory store backed by ChromaDB.

    Notes:
    - This store expects embeddings to be computed upstream (we pass embeddings into `upsert`/`search`).
    - Filtering is done via Chroma metadata `where` clauses (exact match).
    """

    def __init__(
        self,
        *,
        persist_dir: str,
        collection_name: str = "trip_planner_memory",
    ):
        self.persist_dir = str(persist_dir)
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)

        self._collection_name_prefix = (collection_name or "trip_planner_memory").strip()
        self._collections_by_dim: Dict[int, Any] = {}

        try:
            import chromadb  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "ChromaDB is not installed. Add `chromadb` to requirements and install dependencies."
            ) from exc

        self._client = chromadb.PersistentClient(path=self.persist_dir)

    def _collection_for_dim(self, embedding_dim: int):
        embedding_dim = int(embedding_dim)
        if embedding_dim <= 0:
            raise ValueError("embedding_dim must be > 0")

        existing = self._collections_by_dim.get(embedding_dim)
        if existing is not None:
            return existing

        # IMPORTANT: Chroma collections have a fixed embedding dimension.
        # We namespace the collection name by dimension to avoid collisions
        # between (e.g.) deterministic fallback embeddings and real model embeddings.
        name = f"{self._collection_name_prefix}_dim{embedding_dim}"
        collection = self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
        self._collections_by_dim[embedding_dim] = collection
        return collection

    def upsert(
        self,
        *,
        entry_id: str,
        user_id: str,
        destination: str,
        text: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        embedding_dim = len(list(embedding or []))
        collection = self._collection_for_dim(embedding_dim)

        now = time.time()
        destination_norm = (destination or "").strip().lower()
        user_id_norm = (user_id or "").strip()
        combined_meta: Dict[str, Any] = {
            "created_at": float(now),
            "user_id": user_id_norm,
            "destination": destination_norm,
        }
        if metadata:
            combined_meta.update(metadata)

        collection.upsert(
            ids=[str(entry_id)],
            documents=[str(text or "")],
            embeddings=[list(embedding or [])],
            metadatas=[combined_meta],
        )

    def search(
        self,
        *,
        query_embedding: List[float],
        user_id: Optional[str] = None,
        destination: Optional[str] = None,
        top_k: int = 3,
    ) -> List[Tuple[MemoryEntry, float]]:
        if not query_embedding:
            return []

        embedding_dim = len(list(query_embedding or []))
        collection = self._collection_for_dim(embedding_dim)

        top_k = max(1, int(top_k))
        destination_norm = (destination or "").strip().lower()
        user_id_norm = (user_id or "").strip()

        def run_query(where: Optional[Dict[str, Any]]) -> List[Tuple[MemoryEntry, float]]:
            result = collection.query(
                query_embeddings=[list(query_embedding)],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
            ids = (result.get("ids") or [[]])[0] or []
            docs = (result.get("documents") or [[]])[0] or []
            metas = (result.get("metadatas") or [[]])[0] or []
            dists = (result.get("distances") or [[]])[0] or []

            matches: List[Tuple[MemoryEntry, float]] = []
            limit = min(len(ids), len(docs), len(metas))
            for idx in range(limit):
                entry_id = str(ids[idx])
                doc = str(docs[idx] or "")
                meta = dict(metas[idx] or {})
                dist = None
                if dists and idx < len(dists):
                    try:
                        dist = float(dists[idx])
                    except Exception:
                        dist = None

                # With cosine space, Chroma returns cosine distance in [0, 2].
                # Convert to a higher-is-better similarity score.
                score = 0.0
                if dist is not None:
                    score = max(0.0, 1.0 - dist)

                matches.append(
                    (
                        MemoryEntry(
                            id=entry_id,
                            created_at=float(meta.get("created_at", 0.0) or 0.0),
                            user_id=str(meta.get("user_id", "")),
                            destination=str(meta.get("destination", "")),
                            text=doc,
                            metadata=meta,
                        ),
                        float(score),
                    )
                )
            return matches

        # Chroma's `where` requires exactly one top-level operator.
        # Use $and to combine metadata constraints.
        where_clauses: List[Dict[str, Any]] = []
        if user_id_norm:
            where_clauses.append({"user_id": user_id_norm})
        if destination_norm:
            where_clauses.append({"destination": destination_norm})

        where: Optional[Dict[str, Any]]
        if len(where_clauses) == 0:
            where = None
        elif len(where_clauses) == 1:
            where = where_clauses[0]
        else:
            where = {"$and": where_clauses}

        matches = run_query(where)

        # If destination filtering yields nothing, fall back to user-only filtering.
        if destination_norm and not matches:
            where2: Optional[Dict[str, Any]] = None
            if user_id_norm:
                where2 = {"user_id": user_id_norm}
            matches = run_query(where2)

        return matches
