"""Server tests with FastAPI's test client and fake models, so they run without Ollama."""

import json

import pytest
from fastapi.testclient import TestClient

from index import get_collection, index_vault
from ingest import load_vault
from query import NO_RESULTS
from server import create_app, obsidian_url


def fake_embed(texts):
    return [[1.0, 0.0] if "redis" in t.lower() else [0.0, 1.0] for t in texts]


def fake_stream(pieces):
    def stream(system, prompt):
        yield from pieces

    return stream


def events(response) -> list[tuple[str, object]]:
    """Parse a Server-Sent Events body into (event, data) pairs."""
    parsed = []
    for block in response.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        parsed.append((lines["event"], json.loads(lines["data"])))
    return parsed


@pytest.fixture
def vault(tmp_path):
    v = tmp_path / "My Vault"
    v.mkdir()
    (v / "Redis.md").write_text("# Redis\nRedis is an in-memory store used for caching.", encoding="utf-8")
    (v / "Other.md").write_text("# Other\nNothing relevant here.", encoding="utf-8")
    return v


def make_client(vault, tmp_path, pieces=("Redis is used for caching ", "[1]."), index=True):
    collection = get_collection(tmp_path / "db", model="fake")
    if index:
        index_vault(load_vault(vault), collection, fake_embed, model="fake")
    app = create_app(vault, collection, fake_embed, fake_stream(pieces), embed_model="fake", llm_model="fake-llm")
    return TestClient(app)


def test_web_page_is_served(vault, tmp_path):
    response = make_client(vault, tmp_path).get("/")
    assert response.status_code == 200
    assert "<title>Oracle</title>" in response.text


def test_health(vault, tmp_path):
    assert make_client(vault, tmp_path).get("/api/health").json() == {
        "ok": True, "vault": "My Vault", "chunks": 2, "embed_model": "fake", "llm_model": "fake-llm",
    }


def test_search_returns_ranked_hits_with_obsidian_links(vault, tmp_path):
    results = make_client(vault, tmp_path).get("/api/search", params={"q": "redis caching"}).json()["results"]
    assert results[0]["note"] == "Redis.md"
    assert results[0]["via"] == "both"  # found by vector and keyword search
    assert results[0]["url"] == "obsidian://open?vault=My%20Vault&file=Redis"


def test_empty_queries_are_rejected(vault, tmp_path):
    client = make_client(vault, tmp_path)
    assert client.get("/api/search", params={"q": "  "}).status_code == 400
    assert client.get("/api/ask", params={"q": ""}).status_code == 400


def test_ask_streams_tokens_then_the_final_answer(vault, tmp_path):
    response = make_client(vault, tmp_path).get("/api/ask", params={"q": "What is Redis for?", "k": 2})
    assert response.headers["content-type"].startswith("text/event-stream")
    parsed = events(response)
    assert parsed[:2] == [("token", "Redis is used for caching "), ("token", "[1].")]
    event, done = parsed[-1]
    assert event == "done"
    assert done["text"] == "Redis is used for caching [1]."
    assert done["cited"] == [1]
    assert done["sources"][0]["note"] == "Redis.md"
    assert done["unsupported"] == []


def test_ask_flags_unsupported_details_instead_of_removing_them(vault, tmp_path):
    client = make_client(vault, tmp_path, pieces=("Redis listens on port 6379 [1].",))
    event, done = events(client.get("/api/ask", params={"q": "Redis port?"}))[-1]
    assert done["text"] == "Redis listens on port 6379 [1]."  # already streamed, so kept
    assert done["unsupported"] == ["6379"]


def test_ask_with_empty_index_skips_the_llm(vault, tmp_path):
    def must_not_run(system, prompt):
        raise AssertionError("LLM should not be called")
        yield

    collection = get_collection(tmp_path / "db", model="fake")
    client = TestClient(create_app(vault, collection, fake_embed, must_not_run, embed_model="fake"))
    assert events(client.get("/api/ask", params={"q": "anything"})) == [
        ("done", {"text": NO_RESULTS, "sources": [], "cited": [], "unsupported": []})
    ]


def test_reindex_picks_up_new_notes_for_search(vault, tmp_path):
    client = make_client(vault, tmp_path)
    (vault / "Kafka.md").write_text("# Kafka\nKafka stores event streams in topics.", encoding="utf-8")
    assert client.post("/api/index").json() == {"updated": 1, "unchanged": 2, "removed": 0, "chunks": 3}
    results = client.get("/api/search", params={"q": "kafka topics"}).json()["results"]
    assert results[0]["note"] == "Kafka.md"


def test_obsidian_url_encodes_folders_and_spaces(tmp_path):
    assert obsidian_url(tmp_path / "Notes", "AI/Gradient Descent.md") == (
        "obsidian://open?vault=Notes&file=AI/Gradient%20Descent"
    )


def test_obsidian_app_origin_is_allowed(vault, tmp_path):
    # The plugin's EventSource connects from Obsidian's app origin, so the server must allow it (CORS).
    client = make_client(vault, tmp_path)
    allowed = client.get("/api/health", headers={"Origin": "app://obsidian.md"})
    assert allowed.headers["access-control-allow-origin"] == "app://obsidian.md"
    other = client.get("/api/health", headers={"Origin": "https://example.com"})
    assert "access-control-allow-origin" not in other.headers
