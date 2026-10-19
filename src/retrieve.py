"""Find the chunks most relevant to a question.

A retriever is any function `(question, k) -> list[Hit]`, so strategies (vector-only,
graph expansion, hybrid keyword search) can be swapped and compared in evaluation.
Every strategy returns at most k chunks, so comparisons give the LLM the same amount of context.
"""

import dataclasses
import math
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from index import EmbedFn
from ingest import Note, name_index, parse_links, resolve_link

QUERY_PREFIX = "search_query: "  # nomic-embed-text's prefix for questions (documents use search_document:)
CANDIDATE_POOL = 30  # how many results graph expansion and hybrid search choose from
RRF_K = 60  # Reciprocal Rank Fusion constant; 60 is the standard value from the original paper

TOKEN_RE = re.compile(r"[a-z0-9_]+")
STOPWORDS = frozenset(
    "a an and are as at be but by can could did do does for from had has have how i if in into is it its me my "
    "of on or our should so than that the their them then there these they this to was we were what when where "
    "which who why will with would you your".split()
)


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    note_key: str
    note_title: str
    heading: str  # "Remedies" or "A > A1"; "" for text before the first heading
    text: str  # the chunk text that was embedded (breadcrumb + content)
    score: float  # higher is better; cosine similarity (vector), BM25 (keyword), or RRF (hybrid)
    via: str = "vector"  # "vector", "keyword", "both" (hybrid: found by each), or "link" (graph expansion)


Retriever = Callable[[str, int], list[Hit]]


def _hit(chunk_id: str, meta: dict, doc: str, score: float, via: str = "vector") -> Hit:
    return Hit(chunk_id, meta["note_key"], meta["note_title"], meta["heading"], doc, score, via)


def _search(collection, vector: list[float], n: int, where: dict | None = None) -> list[Hit]:
    result = collection.query(query_embeddings=[vector], n_results=n, where=where)
    return [
        _hit(chunk_id, meta, doc, 1 - distance)  # Chroma returns cosine distance
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


# --- Keyword search ---


def tokenize(text: str) -> list[str]:
    """Lowercase words and numbers, without common English stopwords."""
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


class BM25:
    """Okapi BM25, the standard keyword ranking: rewards terms that are frequent in a chunk but rare
    across all chunks, with diminishing returns for repeats and a correction for chunk length."""

    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.term_counts = [Counter(doc) for doc in docs]
        self.lengths = [len(doc) for doc in docs]
        self.avg_length = sum(self.lengths) / len(docs) if docs else 0.0
        doc_freq = Counter(term for doc in docs for term in set(doc))
        n = len(docs)
        self.idf = {term: math.log(1 + (n - df + 0.5) / (df + 0.5)) for term, df in doc_freq.items()}

    def scores(self, query: list[str]) -> list[float]:
        terms = set(query)
        results = []
        for counts, length in zip(self.term_counts, self.lengths):
            score = 0.0
            for term in terms & counts.keys():
                tf = counts[term]
                score += self.idf[term] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * length / self.avg_length))
            results.append(score)
        return results


def _ranked_keyword_hits(data: dict, bm25: BM25, question: str, k: int) -> list[Hit]:
    scores = bm25.scores(tokenize(question))
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    hits = []
    for i in order:
        if scores[i] <= 0 or len(hits) == k:
            break
        hits.append(_hit(data["ids"][i], data["metadatas"][i], data["documents"][i], scores[i], "keyword"))
    return hits


def keyword_retriever(collection) -> Retriever:
    """BM25 over the same chunks as the vector index (a snapshot taken when the retriever is created)."""
    data = collection.get(include=["documents", "metadatas"])
    bm25 = BM25([tokenize(doc) for doc in data["documents"]])

    def retrieve(question: str, k: int) -> list[Hit]:
        return _ranked_keyword_hits(data, bm25, question, k)

    return retrieve


def obsidian_like_retriever(collection) -> Retriever:
    """Approximates Obsidian's search bar: a note matches only if it contains every search term
    (case-insensitive substring match, like Obsidian). Matching notes' chunks are ranked by BM25.

    More lenient than the real search bar in one way: stopwords ("what", "is") are dropped, whereas
    Obsidian requires them too. So this is an upper bound on what typing the question would find.
    """
    data = collection.get(include=["documents", "metadatas"])
    bm25 = BM25([tokenize(doc) for doc in data["documents"]])
    note_text: dict[str, str] = defaultdict(str)
    for meta, doc in zip(data["metadatas"], data["documents"]):
        note_text[meta["note_key"]] += "\n" + doc.lower()

    def retrieve(question: str, k: int) -> list[Hit]:
        terms = set(tokenize(question))
        if not terms:
            return []
        matching = {key for key, text in note_text.items() if all(term in text for term in terms)}
        # Rank the matching notes' chunks by BM25, then by how many terms they contain as substrings
        # ("expire" in "expired" scores 0 in BM25 but still matches, as in Obsidian).
        scores = bm25.scores(list(terms))
        candidates = []
        for i, (meta, doc) in enumerate(zip(data["metadatas"], data["documents"])):
            substring_hits = sum(term in doc.lower() for term in terms)
            if meta["note_key"] in matching and substring_hits:
                candidates.append((scores[i], substring_hits, i))
        candidates.sort(reverse=True)
        return [
            _hit(data["ids"][i], data["metadatas"][i], data["documents"][i], score, "keyword")
            for score, _, i in candidates[:k]
        ]

    return retrieve


def hybrid_retriever(collection, embed: EmbedFn, pool: int = CANDIDATE_POOL, rrf_k: int = RRF_K) -> Retriever:
    """Vector + keyword search merged with Reciprocal Rank Fusion: each chunk scores the sum of
    1 / (rrf_k + rank) over the lists it appears in. Uses ranks only, so BM25 and cosine scores
    never need to be put on the same scale, and there are no weights to tune."""
    by_vector = vector_retriever(collection, embed)
    by_keyword = keyword_retriever(collection)

    def retrieve(question: str, k: int) -> list[Hit]:
        fused: dict[str, float] = defaultdict(float)
        found_by: dict[str, set[str]] = defaultdict(set)
        first_seen: dict[str, Hit] = {}
        for hits in (by_vector(question, pool), by_keyword(question, pool)):
            for rank, hit in enumerate(hits, 1):
                fused[hit.chunk_id] += 1 / (rrf_k + rank)
                found_by[hit.chunk_id].add(hit.via)
                first_seen.setdefault(hit.chunk_id, hit)
        top = sorted(fused, key=fused.get, reverse=True)[:k]
        return [
            dataclasses.replace(
                first_seen[c], score=fused[c], via="both" if len(found_by[c]) > 1 else first_seen[c].via
            )
            for c in top
        ]

    return retrieve
