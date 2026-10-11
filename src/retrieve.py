"""Find the chunks most relevant to a question.

A retriever is any function `(question, k) -> list[Hit]`, so strategies (vector-only,
graph expansion, hybrid keyword search) can be swapped and compared in evaluation.
"""

from collections.abc import Callable
from dataclasses import dataclass

from index import EmbedFn

QUERY_PREFIX = "search_query: "  # nomic-embed-text's prefix for questions (documents use search_document:)


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    note_key: str
    note_title: str
    heading: str  # "Remedies" or "A > A1"; "" for text before the first heading
    text: str  # the chunk text that was embedded (breadcrumb + content)
    score: float  # cosine similarity, higher is better


Retriever = Callable[[str, int], list[Hit]]


def vector_retriever(collection, embed: EmbedFn) -> Retriever:
    """Baseline: the k chunks whose embeddings are closest to the question's."""

    def retrieve(question: str, k: int) -> list[Hit]:
        if collection.count() == 0:
            return []
        [vector] = embed([QUERY_PREFIX + question])
        result = collection.query(query_embeddings=[vector], n_results=min(k, collection.count()))
        return [
            Hit(
                chunk_id=chunk_id,
                note_key=meta["note_key"],
                note_title=meta["note_title"],
                heading=meta["heading"],
                text=doc,
                score=1 - distance,  # Chroma returns cosine distance
            )
            for chunk_id, meta, doc, distance in zip(
                result["ids"][0], result["metadatas"][0], result["documents"][0], result["distances"][0]
            )
        ]

    return retrieve
