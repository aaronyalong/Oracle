"""MCP server tests: tools are called through an in-process MCP client with fake models, so they run without Ollama."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest
from mcp import Client
from mcp_types import LATEST_PROTOCOL_VERSION

from index import get_collection, index_vault
from ingest import load_vault
from mcp_server import OLLAMA_DOWN, Oracle, create_server, default_db, slug
from query import REFUSAL

SCRIPT = Path(__file__).parent.parent / "src" / "mcp_server.py"


def fake_embed(texts):
    return [[1.0, 0.0] if "redis" in t.lower() else [0.0, 1.0] for t in texts]


def fake_generate(text):
    prompts = []

    def generate(system, prompt):
        prompts.append(prompt)
        return text

    generate.prompts = prompts
    return generate


def down(texts):
    raise ConnectionError("connection refused")


@pytest.fixture
def vault(tmp_path):
    v = tmp_path / "My Vault"
    v.mkdir()
    (v / "Redis.md").write_text(
        "# Redis\n## Uses\nRedis is an in-memory store used for caching, session storage, and rate limiting "
        "between services, usually in front of a slower database.",
        encoding="utf-8",
    )
    (v / "Other.md").write_text("# Other\nNothing relevant here.", encoding="utf-8")
    return v


def make_oracle(vault, tmp_path, answer_text="Redis is used for caching [1].", index=True, embed=fake_embed):
    collection = get_collection(tmp_path / "db", model="fake")
    if index:
        index_vault(load_vault(vault), collection, fake_embed, model="fake")
    return Oracle(vault, collection, embed, fake_generate(answer_text), embed_model="fake")


def call(oracle, tool, arguments=None):
    async def run():
        async with Client(create_server(oracle)) as client:
            return await client.call_tool(tool, arguments or {})

    return asyncio.run(run())


def list_tools(server):
    async def run():
        async with Client(server) as client:
            return (await client.list_tools()).tools

    return asyncio.run(run())


def test_tools_are_listed_with_schemas(vault, tmp_path):
    tools = {t.name: t for t in list_tools(create_server(make_oracle(vault, tmp_path)))}
    assert set(tools) == {"search", "answer", "reindex"}
    assert tools["search"].input_schema["required"] == ["query"]
    assert tools["search"].input_schema["properties"]["k"]["maximum"] == 50
    assert set(tools["answer"].output_schema["properties"]) == {"text", "sources", "cited", "unsupported"}


def test_search_returns_ranked_sections(vault, tmp_path):
    result = call(make_oracle(vault, tmp_path), "search", {"query": "redis caching", "k": 2})
    assert not result.is_error
    hits = result.structured_content["results"]
    assert [h["note"] for h in hits] == ["Redis.md", "Other.md"]
    assert hits[0]["heading"] == "Uses"
    assert "in-memory store" in hits[0]["text"]
    assert hits[0]["url"] == "obsidian://open?vault=My%20Vault&file=Redis"


@pytest.mark.parametrize("arguments", [{"query": "   "}, {"query": "redis", "k": 0}, {"query": "redis", "k": 51}])
def test_search_rejects_bad_input(vault, tmp_path, arguments):
    assert call(make_oracle(vault, tmp_path), "search", arguments).is_error


def test_answer_cites_sources(vault, tmp_path):
    oracle = make_oracle(vault, tmp_path)
    answer = call(oracle, "answer", {"question": "What is Redis used for?"}).structured_content
    assert answer["text"] == "Redis is used for caching [1]."
    assert answer["sources"][0]["note"] == "Redis.md"
    assert answer["cited"] == [1]
    assert answer["unsupported"] == []
    assert "in-memory store used for caching" in oracle.generate.prompts[0]  # the note was the context


def test_answer_removes_details_not_in_the_notes(vault, tmp_path):
    oracle = make_oracle(vault, tmp_path, answer_text="Redis listens on port 6379 [1].")
    answer = call(oracle, "answer", {"question": "What port does Redis use?"}).structured_content
    assert answer["text"] == REFUSAL  # strict grounding: the only sentence was unsupported
    assert "6379" in answer["unsupported"]


def test_reindex_picks_up_new_notes(vault, tmp_path):
    oracle = make_oracle(vault, tmp_path)
    (vault / "Redis Cluster.md").write_text("# Redis Cluster\nShards Redis keys across nodes.", encoding="utf-8")
    stats = call(oracle, "reindex").structured_content
    assert stats == {"updated": 1, "unchanged": 2, "removed": 0, "chunks": 3}
    hits = call(oracle, "search", {"query": "redis shards", "k": 3}).structured_content["results"]
    assert "Redis Cluster.md" in [h["note"] for h in hits]


def test_tools_wait_for_the_first_index(vault, tmp_path):
    oracle = make_oracle(vault, tmp_path, index=False)
    result = call(oracle, "search", {"query": "redis"})
    assert result.is_error
    assert "indexing the vault for the first time" in result.content[0].text
    oracle.start_indexing().join()
    assert not call(oracle, "search", {"query": "redis"}).is_error


def test_failed_startup_index_is_reported(vault, tmp_path):
    oracle = make_oracle(vault, tmp_path, index=False, embed=down)
    oracle.start_indexing().join()
    result = call(oracle, "search", {"query": "redis"})
    assert result.is_error
    assert "Indexing the vault failed" in result.content[0].text


def test_ollama_down_gives_a_clear_message(vault, tmp_path):
    result = call(make_oracle(vault, tmp_path, embed=down), "search", {"query": "redis"})
    assert result.is_error
    assert OLLAMA_DOWN in result.content[0].text


def test_default_index_is_per_vault_and_not_the_plugins(tmp_path):
    assert slug("My Notes!") == "my-notes"
    db = default_db(tmp_path / "Main")
    assert db.name == "chroma-main-mcp"  # the plugin's server uses chroma-main
    assert db.parent == SCRIPT.parent.parent


def test_script_writes_only_protocol_messages_to_stdout(tmp_path):
    """The real script, started the way a client starts it. Stdout carries the protocol, so every line must
    be a JSON-RPC message; the SDK's own client skips other lines, so this reads the raw output instead.
    The vault is empty, so startup indexing makes no Ollama calls."""
    empty = tmp_path / "Empty"
    empty.mkdir()
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": LATEST_PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "test", "version": "0"},
        }},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    process = subprocess.Popen(
        [sys.executable, str(SCRIPT), "--vault", str(empty), "--db", str(tmp_path / "db")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    replies = []
    try:
        for message in messages:
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()
            if "id" in message:  # wait for the reply before sending more
                line = process.stdout.readline()
                replies.append(json.loads(line))  # fails on anything that isn't a protocol message
        process.stdin.close()
        rest = process.stdout.read()
    finally:
        process.wait(timeout=30)
    assert [r["id"] for r in replies] == [1, 2]
    assert {t["name"] for t in replies[1]["result"]["tools"]} == {"search", "answer", "reindex"}
    assert rest.strip() == ""
