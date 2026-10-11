"""Retrieval and answering tests with fake embedding and generation, so they run without Ollama."""

import pytest

from index import get_collection, index_vault
from ingest import load_vault
from query import NO_RESULTS, SYSTEM_PROMPT, Answer, answer, build_prompt
from retrieve import QUERY_PREFIX, Hit, vector_retriever

# Two-dimensional "embeddings": texts mentioning Scala point one way, everything else the other.
def fake_embed(texts):
    return [[1.0, 0.0] if "scala" in t.lower() else [0.0, 1.0] for t in texts]


def make_hit(n: int, note: str = "N.md", heading: str = "") -> Hit:
    return Hit(f"{note}::{n}", note, note.removesuffix(".md"), heading, f"text {n}", 0.9)


@pytest.fixture
def collection(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Scala.md").write_text("# Scala\nScala is a JVM language with case classes.", encoding="utf-8")
    (vault / "Cooking.md").write_text("# Cooking\nPasta needs salted water.", encoding="utf-8")
    collection = get_collection(tmp_path / "db", model="fake")
    index_vault(load_vault(vault), collection, fake_embed, model="fake")
    return collection


# --- Retrieval ---


def test_vector_retriever_ranks_the_closest_chunk_first(collection):
    hits = vector_retriever(collection, fake_embed)("Tell me about Scala", 2)
    assert [h.note_key for h in hits] == ["Scala.md", "Cooking.md"]
    assert hits[0].score == pytest.approx(1.0)
    assert hits[1].score == pytest.approx(0.0)
    assert hits[0].note_title == "Scala"


def test_vector_retriever_adds_query_prefix(collection):
    seen = []

    def recording_embed(texts):
        seen.extend(texts)
        return fake_embed(texts)

    vector_retriever(collection, recording_embed)("pasta?", 1)
    assert seen == [QUERY_PREFIX + "pasta?"]


def test_k_larger_than_index_returns_everything(collection):
    assert len(vector_retriever(collection, fake_embed)("anything", 50)) == 2


def test_empty_index_returns_no_hits(tmp_path):
    empty = get_collection(tmp_path / "db", model="fake")
    assert vector_retriever(empty, fake_embed)("anything", 5) == []


# --- Prompt and answer ---


def test_build_prompt_numbers_excerpts():
    prompt = build_prompt("Why?", [make_hit(1, "A.md"), make_hit(2, "B.md")])
    assert "[1] (from A.md)\ntext 1" in prompt
    assert "[2] (from B.md)\ntext 2" in prompt
    assert prompt.endswith("Question: Why?")


def test_answer_passes_prompt_to_generator():
    calls = []

    def generate(system, prompt):
        calls.append((system, prompt))
        return "  It's because of X [1].  "

    hits = [make_hit(1)]
    result = answer("Why?", lambda q, k: hits, generate)
    assert result.text == "It's because of X [1]."
    assert result.sources == hits
    assert calls == [(SYSTEM_PROMPT, build_prompt("Why?", hits))]


def test_answer_skips_the_llm_when_nothing_is_retrieved():
    def generate(system, prompt):
        raise AssertionError("should not be called")

    assert answer("Why?", lambda q, k: [], generate).text == NO_RESULTS


def test_answer_passes_k_to_retriever():
    seen = []
    answer("Q", lambda q, k: seen.append(k) or [make_hit(1)], lambda s, p: "ok", k=7)
    assert seen == [7]


def test_cited_ignores_out_of_range_numbers():
    result = Answer("A [2], B [1][2], C [9], D [0].", [make_hit(1), make_hit(2)])
    assert result.cited == [1, 2]
