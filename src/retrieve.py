"""Find the chunks most relevant to a question.

A retriever is any function `(question, k) -> list[Hit]`, so strategies (vector-only,
graph expansion, hybrid keyword search) can be swapped and compared in evaluation.
Every strategy returns at most k chunks, so comparisons give the LLM the same amount of context.
"""

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass

from index import EmbedFn
from ingest import Note, name_index, parse_links, resolve_link

QUERY_PREFIX = "search_query: "  # nomic-embed-text's prefix for questions (documents use search_document:)
CANDIDATE_POOL = 30  # how many vector results graph expansion chooses from


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    note_key: str
    note_title: str
    heading: str  # "Remedies" or "A > A1"; "" for text before the first heading
    text: str  # the chunk text that was embedded (breadcrumb + content)
    score: float  # cosine similarity, higher is better
    via: str = "vector"  # "vector", or "link" if graph expansion added it


Retriever = Callable[[str, int], list[Hit]]


def _search(collection, vector: list[float], n: int, where: dict | None = None) -> list[Hit]:
    result = collection.query(query_embeddings=[vector], n_results=n, where=where)
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


def vector_retriever(collection, embed: EmbedFn) -> Retriever:
    """Baseline: the k chunks whose embeddings are closest to the question's."""

    def retrieve(question: str, k: int) -> list[Hit]:
        if collection.count() == 0:
            return []
        [vector] = embed([QUERY_PREFIX + question])
        return _search(collection, vector, min(k, collection.count()))

    return retrieve


def _linked_notes(seeds: list[Hit], notes: dict[str, Note], by_name: dict[str, list[str]], links: str) -> set[str]:
    """Notes one link away from the seed hits.

    links="note":       every outgoing link and backlink of the seed notes.
    links="chunk":      only the links written inside the seed chunks themselves.
    links="chunk+back": chunk links, plus notes that link to the seed notes.
    """
    linked: set[str] = set()
    for hit in seeds:
        note = notes.get(hit.note_key)
        if note is None:
            continue
        if links == "note":
            linked |= note.outgoing | note.backlinks
            continue
        for link in parse_links(hit.text):
            target = resolve_link(link.target, note, notes, by_name)
            if target:
                linked.add(target)
        if links == "chunk+back":
            linked |= note.backlinks
    return linked - {hit.note_key for hit in seeds}


def graph_retriever(
    collection, embed: EmbedFn, notes: dict[str, Note], seeds: int = 1, boost: float = 0.05, links: str = "note"
) -> Retriever:
    """Vector search, then favour notes linked from the top results.

    1. The top `seeds` vector hits are kept as-is.
    2. Notes one link away from them become "linked" notes (which links count depends on `links`;
       see _linked_notes).
    3. Remaining slots go to the best of: other vector candidates, and the best chunks of the linked
       notes (fetched even if they weren't in the vector results), with `boost` added to linked
       chunks' scores. boost=0 behaves like plain vector search; a large boost fills every
       remaining slot from linked notes.
    """

    if links not in ("note", "chunk", "chunk+back"):
        raise ValueError(f"links must be 'note', 'chunk', or 'chunk+back', not {links!r}")
    by_name = name_index(notes)

    def retrieve(question: str, k: int) -> list[Hit]:
        if collection.count() == 0:
            return []
        [vector] = embed([QUERY_PREFIX + question])
        pool = _search(collection, vector, min(max(CANDIDATE_POOL, k), collection.count()))
        top = pool[: min(seeds, k)]
        linked = _linked_notes(top, notes, by_name, links)

        candidates = {hit.chunk_id: hit for hit in pool[len(top) :]}
        if linked:
            for hit in _search(collection, vector, k, where={"note_key": {"$in": sorted(linked)}}):
                candidates.setdefault(hit.chunk_id, hit)
        for hit in top:
            candidates.pop(hit.chunk_id, None)

        def adjusted(hit: Hit) -> float:
            return hit.score + (boost if hit.note_key in linked else 0.0)

        rest = sorted(candidates.values(), key=adjusted, reverse=True)[: k - len(top)]
        return top + [dataclasses.replace(h, via="link") if h.note_key in linked else h for h in rest]

    return retrieve
