"""Local HTTP server: the web page and the Obsidian plugin talk to Oracle through it.

Usage: python src/server.py --vault sample-vault [--port 8000]   then open http://localhost:8000

Endpoints (all JSON unless noted):
  GET  /                    the web page
  GET  /api/health          index size and models
  GET  /api/search?q=&k=    ranked sections, hybrid search, no LLM (fast)
  GET  /api/ask?q=&k=       streamed answer as Server-Sent Events (text/event-stream):
                              event: token  data: "text piece"   (repeated, as the model writes)
                              event: done   data: {text, sources, cited, unsupported}
  POST /api/index           re-index the vault (only changed notes are re-embedded)
"""

import argparse
import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import ollama
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from index import DEFAULT_DB, EMBED_MODEL, EmbedFn, get_collection, index_vault, ollama_embedder
from ingest import load_vault
from query import (
    DEFAULT_K, LLM_MODEL, NO_RESULTS, SYSTEM_PROMPT, Answer, StreamFn, finish, ollama_streamer, prepare,
)
from retrieve import Hit, Retriever, hybrid_retriever, vector_retriever

WEB_PAGE = Path(__file__).parent.parent / "web" / "index.html"
SEARCH_K = 10
# Obsidian desktop pages run at this origin; allowing it lets the plugin call the server.
ALLOWED_ORIGINS = ["app://obsidian.md", "capacitor://localhost", "http://localhost", "http://127.0.0.1"]


@dataclass
class State:
    """What the endpoints share. Retrievers are rebuilt after indexing: BM25 keeps a snapshot of the chunks."""

    vault: Path
    collection: object
    embed: EmbedFn
    stream: StreamFn
    search: Retriever
    ask_retrieve: Retriever
    embed_model: str
    llm_model: str


def obsidian_url(vault: Path, note_key: str) -> str:
    """Link that opens the note in Obsidian, assuming the vault is open under its folder name."""
    return f"obsidian://open?vault={quote(vault.resolve().name)}&file={quote(note_key.removesuffix('.md'))}"


def _hit_json(hit: Hit, vault: Path) -> dict:
    return {
        "note": hit.note_key,
        "title": hit.note_title,
        "heading": hit.heading,
        "text": hit.text,
        "score": round(hit.score, 4),
        "via": hit.via,
        "url": obsidian_url(vault, hit.note_key),
    }


def _sse(event: str, data) -> str:
    # JSON-encode the payload so newlines in the text can't break the event format.
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _build_retrievers(state: State) -> None:
    state.search = hybrid_retriever(state.collection, state.embed)
    state.ask_retrieve = vector_retriever(state.collection, state.embed)  # what the answer benchmarks measured


def create_app(
    vault: Path,
    collection,
    embed: EmbedFn,
    stream: StreamFn,
    embed_model: str = EMBED_MODEL,
    llm_model: str = LLM_MODEL,
) -> FastAPI:
    state = State(vault, collection, embed, stream, None, None, embed_model, llm_model)
    _build_retrievers(state)

    app = FastAPI(title="Oracle", description="Local RAG over an Obsidian vault")
    app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["GET", "POST"])

    @app.get("/", include_in_schema=False)
    def web_page():
        return FileResponse(WEB_PAGE)

    @app.get("/api/health")
    def health():
        return {
            "ok": True,
            "vault": state.vault.resolve().name,
            "chunks": state.collection.count(),
            "embed_model": state.embed_model,
            "llm_model": state.llm_model,
        }

    @app.get("/api/search")
    def search(q: str, k: int = SEARCH_K):
        if not q.strip():
            raise HTTPException(400, "Empty query")
        return {"results": [_hit_json(h, state.vault) for h in state.search(q, k)]}

    @app.get("/api/ask")
    def ask(q: str, k: int = DEFAULT_K):
        if not q.strip():
            raise HTTPException(400, "Empty question")

        def events() -> Iterator[str]:
            hits, prompt = prepare(q, state.ask_retrieve, k)
            if not hits:
                result = Answer(NO_RESULTS, [])
            else:
                pieces = []
                for piece in state.stream(SYSTEM_PROMPT, prompt):
                    pieces.append(piece)
                    yield _sse("token", piece)
                # "warn": text already on screen can't be taken back, so flag details instead of removing them.
                result = finish("".join(pieces), hits, q, grounding="warn")
            yield _sse(
                "done",
                {
                    "text": result.text,
                    "sources": [_hit_json(h, state.vault) for h in result.sources],
                    "cited": result.cited,
                    "unsupported": result.unsupported,
                },
            )

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.post("/api/index")
    def reindex():
        stats = index_vault(load_vault(state.vault), state.collection, state.embed, state.embed_model)
        _build_retrievers(state)
        return {
            "updated": stats.updated,
            "unchanged": stats.unchanged,
            "removed": stats.removed,
            "chunks": state.collection.count(),
        }

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Oracle's local server.")
    parser.add_argument("--vault", required=True, type=Path, help="path to the vault folder")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="index location")
    parser.add_argument("--embed-model", default=EMBED_MODEL)
    parser.add_argument("--model", default=LLM_MODEL, help="Ollama model that writes answers")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    import uvicorn

    try:
        collection = get_collection(args.db, args.embed_model)
        embed = ollama_embedder(args.embed_model)
        stats = index_vault(load_vault(args.vault), collection, embed, args.embed_model)
    except ValueError as e:
        sys.exit(str(e))
    except ConnectionError:
        sys.exit("Can't reach Ollama. Start it with `ollama serve` (or the Ollama app) and try again.")
    except ollama.ResponseError as e:
        sys.exit(f"Ollama error: {e.error}")
    print(f"Index ready: {collection.count()} chunks ({stats.updated} notes re-embedded). "
          f"Open http://localhost:{args.port}", flush=True)

    app = create_app(args.vault, collection, embed, ollama_streamer(args.model), args.embed_model, args.model)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
