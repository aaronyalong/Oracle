"""Embed vault chunks with Ollama and store them in Chroma, re-embedding only notes that changed.

Usage: python src/index.py --vault sample-vault [--rebuild]
"""

import argparse
import hashlib
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import chromadb
import ollama

from chunking import Chunk, chunk_note
from ingest import Vault, load_vault

EMBED_MODEL = "nomic-embed-text"
DOC_PREFIX = "search_document: "  # nomic-embed-text expects a task prefix on every input
DEFAULT_DB = Path("chroma")
COLLECTION = "oracle"
BATCH_SIZE = 64

EmbedFn = Callable[[list[str]], list[list[float]]]


def ollama_embedder(model: str = EMBED_MODEL) -> EmbedFn:
    def embed(texts: list[str]) -> list[list[float]]:
        vectors = []
        for i in range(0, len(texts), BATCH_SIZE):
            vectors.extend(ollama.embed(model=model, input=texts[i : i + BATCH_SIZE]).embeddings)
        return vectors

    return embed


def get_collection(db_path: Path = DEFAULT_DB, model: str = EMBED_MODEL, rebuild: bool = False):
    client = chromadb.PersistentClient(path=str(db_path))
    if rebuild and COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION)
    collection = client.get_or_create_collection(
        COLLECTION, metadata={"hnsw:space": "cosine", "embed_model": model}
    )
    # Vectors from different models can't be compared, so refuse to mix them.
    stored_model = collection.metadata.get("embed_model")
    if stored_model != model:
        raise ValueError(f"Index was built with {stored_model!r}, not {model!r}; re-run with --rebuild.")
    return collection


def _note_hash(chunks: list[Chunk], model: str) -> str:
    """Changes whenever the note's chunk text or the embedding model changes."""
    h = hashlib.sha256(model.encode())
    for chunk in chunks:
        h.update(chunk.text.encode())
        h.update(b"\0")
    return h.hexdigest()


@dataclass
class IndexStats:
    updated: int  # notes (re-)embedded
    unchanged: int
    removed: int  # notes deleted from the vault
    chunks_embedded: int


def index_vault(vault: Vault, collection, embed: EmbedFn, model: str = EMBED_MODEL) -> IndexStats:
    stored = collection.get(include=["metadatas"])
    stored_hashes = {m["note_key"]: m["note_hash"] for m in stored["metadatas"]}

    changed: list[tuple[str, str, list[Chunk]]] = []  # (note key, hash, chunks)
    unchanged = 0
    for key, note in vault.notes.items():
        chunks = chunk_note(note)
        note_hash = _note_hash(chunks, model)
        if stored_hashes.get(key) == note_hash:
            unchanged += 1
        else:
            changed.append((key, note_hash, chunks))

    # Embed before deleting anything, so a failed run leaves the old index intact.
    new_chunks = [(c, note_hash) for _, note_hash, chunks in changed for c in chunks]
    vectors = embed([DOC_PREFIX + c.text for c, _ in new_chunks])

    removed_keys = set(stored_hashes) - set(vault.notes)
    for key in [k for k, _, _ in changed if k in stored_hashes] + sorted(removed_keys):
        collection.delete(where={"note_key": key})

    for i in range(0, len(new_chunks), BATCH_SIZE):
        batch = new_chunks[i : i + BATCH_SIZE]
        collection.add(
            ids=[c.id for c, _ in batch],
            embeddings=vectors[i : i + BATCH_SIZE],
            documents=[c.text for c, _ in batch],
            metadatas=[
                {
                    "note_key": c.note_key,
                    "note_title": vault.notes[c.note_key].title,
                    "heading": " > ".join(c.heading_path),
                    "tags": ",".join(sorted(vault.notes[c.note_key].tags)),
                    "note_hash": note_hash,
                }
                for c, note_hash in batch
            ],
        )

    return IndexStats(
        updated=len(changed), unchanged=unchanged, removed=len(removed_keys), chunks_embedded=len(new_chunks)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed an Obsidian vault into a local Chroma index.")
    parser.add_argument("--vault", required=True, help="path to the vault folder")
    parser.add_argument("--exclude", nargs="*", default=[], help="vault folders to skip, e.g. templates")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="where to store the index")
    parser.add_argument("--model", default=EMBED_MODEL, help="Ollama embedding model")
    parser.add_argument("--rebuild", action="store_true", help="delete the index and embed everything")
    args = parser.parse_args()

    start = time.perf_counter()
    try:
        collection = get_collection(args.db, args.model, args.rebuild)
        stats = index_vault(load_vault(args.vault, tuple(args.exclude)), collection, ollama_embedder(args.model), args.model)
    except ValueError as e:
        sys.exit(str(e))
    except ConnectionError:
        sys.exit("Can't reach Ollama. Start it with `ollama serve` (or the Ollama app) and try again.")
    except ollama.ResponseError as e:
        sys.exit(f"Ollama error: {e.error}. Did you run `ollama pull {args.model}`?")

    print(f"{stats.updated} notes embedded ({stats.chunks_embedded} chunks), {stats.unchanged} unchanged, "
          f"{stats.removed} removed — {collection.count()} chunks in index ({time.perf_counter() - start:.1f}s)")


if __name__ == "__main__":
    main()
