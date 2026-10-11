"""Index tests use a fake embedder, so they run without Ollama."""

import pytest

from index import get_collection, index_vault
from ingest import load_vault


class FakeEmbedder:
    """Returns a fixed vector per text and records how many texts it was asked to embed."""

    def __init__(self):
        self.calls = 0

    def __call__(self, texts):
        self.calls += len(texts)
        return [[float(len(t) % 7), 1.0, 0.5] for t in texts]


@pytest.fixture
def vault_dir(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    long = "Enough text to stay its own chunk instead of being merged. " * 2
    (vault / "A.md").write_text(f"# A\n## One\n{long}\n## Two\n{long}", encoding="utf-8")
    (vault / "B.md").write_text("# B\nB links to [[A]].", encoding="utf-8")
    return vault


@pytest.fixture
def collection(tmp_path):
    return get_collection(tmp_path / "db", model="fake")


def run(vault_dir, collection, embed):
    return index_vault(load_vault(vault_dir), collection, embed, model="fake")


def test_first_run_embeds_everything(vault_dir, collection):
    embed = FakeEmbedder()
    stats = run(vault_dir, collection, embed)
    assert (stats.updated, stats.unchanged, stats.removed) == (2, 0, 0)
    assert collection.count() == embed.calls == stats.chunks_embedded


def test_second_run_embeds_nothing(vault_dir, collection):
    run(vault_dir, collection, FakeEmbedder())
    embed = FakeEmbedder()
    stats = run(vault_dir, collection, embed)
    assert (stats.updated, stats.unchanged) == (0, 2)
    assert embed.calls == 0


def test_only_changed_note_is_reembedded(vault_dir, collection):
    run(vault_dir, collection, FakeEmbedder())
    (vault_dir / "B.md").write_text("# B\nB now says something else.", encoding="utf-8")
    embed = FakeEmbedder()
    stats = run(vault_dir, collection, embed)
    assert (stats.updated, stats.unchanged) == (1, 1)
    docs = collection.get(where={"note_key": "B.md"})["documents"]
    assert docs == ["B\n\nB now says something else."]


def test_shrinking_note_leaves_no_stale_chunks(vault_dir, collection):
    run(vault_dir, collection, FakeEmbedder())
    assert len(collection.get(where={"note_key": "A.md"})["ids"]) == 2
    (vault_dir / "A.md").write_text("# A\nNow just one section of text here.", encoding="utf-8")
    run(vault_dir, collection, FakeEmbedder())
    assert len(collection.get(where={"note_key": "A.md"})["ids"]) == 1


def test_deleted_note_is_removed(vault_dir, collection):
    run(vault_dir, collection, FakeEmbedder())
    (vault_dir / "B.md").unlink()
    stats = run(vault_dir, collection, FakeEmbedder())
    assert stats.removed == 1
    assert collection.get(where={"note_key": "B.md"})["ids"] == []


def test_failed_embedding_keeps_old_index(vault_dir, collection):
    run(vault_dir, collection, FakeEmbedder())
    before = collection.count()
    (vault_dir / "B.md").write_text("# B\nChanged.", encoding="utf-8")

    def broken(texts):
        raise ConnectionError("Ollama is down")

    with pytest.raises(ConnectionError):
        run(vault_dir, collection, broken)
    assert collection.count() == before


def test_metadata_is_stored(vault_dir, collection):
    run(vault_dir, collection, FakeEmbedder())
    meta = collection.get(where={"note_key": "A.md"})["metadatas"]
    assert {m["heading"] for m in meta} == {"One", "Two"}
    assert all(m["note_title"] == "A" for m in meta)


def test_switching_models_requires_rebuild(tmp_path):
    get_collection(tmp_path / "db", model="model-one")
    with pytest.raises(ValueError, match="--rebuild"):
        get_collection(tmp_path / "db", model="model-two")
    assert get_collection(tmp_path / "db", model="model-two", rebuild=True).count() == 0
