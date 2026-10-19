"""Keyword (BM25), Obsidian-like, and hybrid retrieval tests. Fake embeddings, so no Ollama needed."""

import pytest

from index import get_collection, index_vault
from ingest import load_vault
from retrieve import BM25, hybrid_retriever, keyword_retriever, obsidian_like_retriever, tokenize


# Embeddings only know about meaning words: "async"/"concurrency" point one way, everything else another.
def fake_embed(texts):
    return [[1.0, 0.0] if ("async" in t or "concurrency" in t) else [0.0, 1.0] for t in texts]


@pytest.fixture
def collection(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Errors.md").write_text("# Errors\nError E4021 means the cache expired.", encoding="utf-8")
    (vault / "Futures.md").write_text("# Futures\nFutures give async concurrency on the JVM.", encoding="utf-8")
    (vault / "Cache.md").write_text("# Cache\nThe cache stores results. The cache is fast.", encoding="utf-8")
    c = get_collection(tmp_path / "db", model="fake")
    index_vault(load_vault(vault), c, fake_embed, model="fake")
    return c


# --- Tokenizing and BM25 ---


def test_tokenize_lowercases_and_drops_stopwords():
    assert tokenize("What is the ef_search value in HNSW?") == ["ef_search", "value", "hnsw"]


def test_bm25_rare_terms_outweigh_common_ones():
    docs = [["cache", "rare"], ["cache"], ["cache"], ["other"]]
    scores = BM25(docs).scores(["cache", "rare"])
    assert scores[0] > scores[1] > 0
    assert scores[3] == 0


def test_bm25_has_diminishing_returns_for_repeats():
    once, five_times = BM25([["x", "y"], ["x"] * 5 + ["y"]]).scores(["x"])
    assert five_times < 5 * once


# --- Keyword retriever ---


def test_keyword_finds_exact_rare_terms(collection):
    hits = keyword_retriever(collection)("what does E4021 mean?", 3)
    assert [h.note_key for h in hits] == ["Errors.md"]
    assert hits[0].via == "keyword"


def test_keyword_returns_nothing_without_overlap(collection):
    assert keyword_retriever(collection)("parallel programming", 3) == []


# --- Obsidian-like ---


def test_obsidian_like_requires_every_term_in_the_note(collection):
    search = obsidian_like_retriever(collection)
    assert [h.note_key for h in search("cache results", 3)] == ["Cache.md"]
    assert search("cache concurrency", 3) == []  # no single note has both


def test_obsidian_like_matches_substrings_like_obsidian(collection):
    assert [h.note_key for h in obsidian_like_retriever(collection)("expire", 3)] == ["Errors.md"]


# --- Hybrid ---


def test_hybrid_finds_both_meaning_and_exact_terms(collection):
    search = hybrid_retriever(collection, fake_embed)
    assert search("async code", 1)[0].note_key == "Futures.md"  # meaning only: no "async code" keyword match needed
    assert search("E4021", 1)[0].note_key == "Errors.md"  # exact term the embeddings know nothing about


def test_hybrid_labels_where_each_hit_came_from(collection):
    hits = hybrid_retriever(collection, fake_embed)("async concurrency", 3)
    assert hits[0].note_key == "Futures.md"
    assert hits[0].via == "both"


def test_hybrid_respects_k_without_duplicates(collection):
    for k in (1, 2, 3, 10):
        hits = hybrid_retriever(collection, fake_embed)("cache async", k)
        assert len(hits) == min(k, 3)
        assert len({h.chunk_id for h in hits}) == len(hits)


def test_empty_index(tmp_path):
    empty = get_collection(tmp_path / "db", model="fake")
    assert keyword_retriever(empty)("anything", 3) == []
    assert obsidian_like_retriever(empty)("anything", 3) == []
    assert hybrid_retriever(empty, fake_embed)("anything", 3) == []
