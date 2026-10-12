"""Graph expansion tests with hand-placed fake embeddings, so they run without Ollama.

Similarity to the question "alpha?":  A = 1.0, C = 0.8, D = 0.7, B = 0.6.
A links to B; C and D are unrelated distractors that are more similar than B.
"""

import pytest

from index import get_collection, index_vault
from ingest import load_vault
from retrieve import graph_retriever, vector_retriever

VECTORS = {"alpha": [1.0, 0.0, 0.0], "near": [0.8, 0.6, 0.0], "close": [0.7, 0.0, 0.714], "beta": [0.6, 0.8, 0.0]}


def fake_embed(texts):
    return [next((v for word, v in VECTORS.items() if word in t), [0.0, 0.0, 1.0]) for t in texts]


@pytest.fixture
def setup(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "A.md").write_text("# A\nalpha main topic, see [[B]]", encoding="utf-8")
    (vault / "B.md").write_text("# B\nbeta details", encoding="utf-8")
    (vault / "C.md").write_text("# C\nnear distractor", encoding="utf-8")
    (vault / "D.md").write_text("# D\nclose distractor", encoding="utf-8")
    notes = load_vault(vault).notes
    collection = get_collection(tmp_path / "db", model="fake")
    index_vault(load_vault(vault), collection, fake_embed, model="fake")
    return collection, notes


def note_order(hits):
    return [h.note_key for h in hits]


def test_vector_baseline_order(setup):
    collection, _ = setup
    assert note_order(vector_retriever(collection, fake_embed)("alpha?", 4)) == ["A.md", "C.md", "D.md", "B.md"]


def test_zero_boost_matches_vector_search(setup):
    collection, notes = setup
    hits = graph_retriever(collection, fake_embed, notes, seeds=1, boost=0.0)("alpha?", 3)
    assert note_order(hits) == ["A.md", "C.md", "D.md"]


def test_large_boost_pulls_in_linked_note(setup):
    collection, notes = setup
    hits = graph_retriever(collection, fake_embed, notes, seeds=1, boost=1.0)("alpha?", 2)
    assert note_order(hits) == ["A.md", "B.md"]
    assert [h.via for h in hits] == ["vector", "link"]


def test_moderate_boost_only_beats_weaker_candidates(setup):
    # B (0.6) + 0.15 = 0.75 beats D (0.7) but not C (0.8).
    collection, notes = setup
    hits = graph_retriever(collection, fake_embed, notes, seeds=1, boost=0.15)("alpha?", 3)
    assert note_order(hits) == ["A.md", "C.md", "B.md"]


def test_backlinks_count_as_links(setup):
    # The top hit for "beta" is B, which A links *to*; A should be pulled in via the backlink.
    collection, notes = setup
    hits = graph_retriever(collection, fake_embed, notes, seeds=1, boost=1.0)("beta?", 2)
    assert note_order(hits) == ["B.md", "A.md"]


def test_never_returns_more_than_k_or_duplicates(setup):
    collection, notes = setup
    for k in (1, 2, 3, 4, 10):
        hits = graph_retriever(collection, fake_embed, notes, seeds=2, boost=1.0)("alpha?", k)
        assert len(hits) == min(k, 4)
        assert len({h.chunk_id for h in hits}) == len(hits)


def test_k_equal_to_seeds_is_plain_vector_search(setup):
    collection, notes = setup
    hits = graph_retriever(collection, fake_embed, notes, seeds=1, boost=1.0)("alpha?", 1)
    assert note_order(hits) == ["A.md"]


def test_empty_index(tmp_path):
    empty = get_collection(tmp_path / "db", model="fake")
    assert graph_retriever(empty, fake_embed, {}, seeds=1)("alpha?", 3) == []
