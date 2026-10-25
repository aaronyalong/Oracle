"""MCP server: lets Claude Code, Claude Desktop, or any MCP client search and ask questions of the vault.

Usage: python src/mcp_server.py --vault /path/to/vault   (normally started by the client, over stdin/stdout)

Tools:
  search(query, k)     ranked sections, hybrid search, no LLM (fast). Note text goes to the client's model.
  answer(question, k)  cited answer written by the local model, with the grounding check (strict).
  reindex()            re-embed changed notes.

The tools are thin wrappers around the same functions as the CLI and the HTTP server. The vault is
indexed in the background on startup, so the client doesn't time out waiting for a first index.
"""

import argparse
import re
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, TypedDict

import ollama
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from index import EMBED_MODEL, EmbedFn, get_collection, index_vault, ollama_embedder
from ingest import load_vault
from query import DEFAULT_K, LLM_MODEL, GenerateFn, ollama_generator
from query import answer as answer_question
from server import SEARCH_K, build_retrievers, hit_json

REPO = Path(__file__).parent.parent
MAX_K = 50
OLLAMA_DOWN = "Can't reach Ollama. Start it with `ollama serve` (or the Ollama app) and try again."

INSTRUCTIONS = """Oracle gives access to the user's Obsidian notes.
- `search` returns the most relevant note sections, fast and without an LLM: read them and answer yourself.
- `answer` has a local model write a short answer from the notes, with numbered citations and a check that
  removes details not found in them. Slower (10-20 s); use it when the user asks for Oracle's own answer.
When you use the notes, say which note and heading each point comes from."""


class Section(TypedDict):
    note: str  # vault-relative path, e.g. "AI/Gradient Descent.md"
    title: str
    heading: str  # "Results" or "Training > Results"; "" for text before the first heading
    text: str
    score: float
    via: str  # vector, keyword, or both
    url: str  # obsidian:// link that opens the note


class SearchResults(TypedDict):
    results: list[Section]


class AnswerResult(TypedDict):
    text: str
    sources: list[Section]  # numbered from 1, as cited in the text
    cited: list[int]
    unsupported: list[str]  # details found in no cited note; their sentences were removed


class IndexResult(TypedDict):
    updated: int
    unchanged: int
    removed: int
    chunks: int


def slug(name: str) -> str:
    """Same as the plugin's: "My Notes!" -> "my-notes"."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "vault"


def default_db(vault: Path) -> Path:
    # Not the plugin's chroma-<vault>: Chroma's files aren't safe for two processes writing at once.
    return REPO / f"chroma-{slug(vault.resolve().name)}-mcp"


@contextmanager
def ollama_errors():
    """Turn Ollama failures into messages the client shows, instead of a stack trace."""
    try:
        yield
    except ConnectionError:
        raise ToolError(OLLAMA_DOWN) from None
    except ollama.ResponseError as e:
        raise ToolError(f"Ollama error: {e.error}") from None


class Oracle:
    """What the tools share. Retrievers are rebuilt after indexing: BM25 keeps a snapshot of the chunks."""

    def __init__(self, vault: Path, collection, embed: EmbedFn, generate: GenerateFn, embed_model: str = EMBED_MODEL):
        self.vault = vault
        self.collection = collection
        self.embed = embed
        self.generate = generate
        self.embed_model = embed_model
        self.search_retrieve, self.ask_retrieve = build_retrievers(collection, embed)
        # An index left from a previous run is usable while it's brought up to date; an empty one isn't.
        self.ready = collection.count() > 0
        self.startup_error: str | None = None
        self._lock = threading.Lock()  # one re-index at a time

    def reindex(self) -> IndexResult:
        with self._lock, ollama_errors():
            stats = index_vault(load_vault(self.vault), self.collection, self.embed, self.embed_model)
            self.search_retrieve, self.ask_retrieve = build_retrievers(self.collection, self.embed)
        self.ready, self.startup_error = True, None
        return {
            "updated": stats.updated,
            "unchanged": stats.unchanged,
            "removed": stats.removed,
            "chunks": self.collection.count(),
        }

    def start_indexing(self) -> threading.Thread:
        def run():
            try:
                stats = self.reindex()
                print(f"Index ready: {stats['chunks']} chunks ({stats['updated']} notes re-embedded).", file=sys.stderr)
            except Exception as e:  # shown by the next tool call
                self.startup_error = f"Indexing the vault failed: {e}"
                print(self.startup_error, file=sys.stderr)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def _check_ready(self):
        if self.ready:
            return
        if self.startup_error:
            raise ToolError(f"{self.startup_error} Fix it, then call reindex.")
        raise ToolError("Oracle is indexing the vault for the first time. Try again in a minute.")

    def search(self, query: str, k: int) -> SearchResults:
        if not query.strip():
            raise ToolError("Empty query")
        self._check_ready()
        with ollama_errors():
            hits = self.search_retrieve(query, k)
        return {"results": [hit_json(h, self.vault) for h in hits]}

    def answer(self, question: str, k: int) -> AnswerResult:
        if not question.strip():
            raise ToolError("Empty question")
        self._check_ready()
        with ollama_errors():
            result = answer_question(question, self.ask_retrieve, self.generate, k)  # strict grounding, as in the CLI
        return {
            "text": result.text,
            "sources": [hit_json(h, self.vault) for h in result.sources],
            "cited": result.cited,
            "unsupported": result.unsupported,
        }


def create_server(oracle: Oracle) -> MCPServer:
    server = MCPServer("oracle", instructions=INSTRUCTIONS, log_level="WARNING")  # INFO logs every Ollama request

    @server.tool()
    def search(query: str, k: Annotated[int, Field(ge=1, le=MAX_K)] = SEARCH_K) -> SearchResults:
        """Search the user's Obsidian notes. Returns the k most relevant sections (keyword + semantic
        search), each with its note path, heading, and text. Fast; no LLM involved."""
        return oracle.search(query, k)

    @server.tool()
    def answer(question: str, k: Annotated[int, Field(ge=1, le=MAX_K)] = DEFAULT_K) -> AnswerResult:
        """Answer a question from the user's notes with a local model (10-20 s). The text cites
        `sources` as [1], [2], ...; sentences with details found in no note are removed and listed in
        `unsupported`. Says so when the notes don't contain the answer."""
        return oracle.answer(question, k)

    @server.tool()
    def reindex() -> IndexResult:
        """Re-index the vault after notes changed. Only changed notes are re-embedded."""
        return oracle.reindex()

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Oracle as an MCP server over stdin/stdout.")
    parser.add_argument("--vault", required=True, type=Path, help="path to the vault folder")
    parser.add_argument("--db", type=Path, help="index location (default: chroma-<vault name>-mcp in this repository)")
    parser.add_argument("--embed-model", default=EMBED_MODEL)
    parser.add_argument("--model", default=LLM_MODEL, help="Ollama model that writes answers")
    args = parser.parse_args()

    vault = args.vault.expanduser().resolve()
    if not vault.is_dir():
        sys.exit(f"No vault folder at {vault}")
    try:
        collection = get_collection(args.db or default_db(vault), args.embed_model)
    except ValueError as e:
        sys.exit(str(e))

    oracle = Oracle(vault, collection, ollama_embedder(args.embed_model), ollama_generator(args.model), args.embed_model)
    oracle.start_indexing()
    create_server(oracle).run()


if __name__ == "__main__":
    main()
