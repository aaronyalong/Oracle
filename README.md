# Obsidian RAG

A fully local Retrieval-Augmented Generation (RAG) system over an Obsidian vault. Ask questions in natural language and get answers grounded in your own notes — with sources — without any data leaving your machine.

What makes it *Obsidian* RAG rather than generic RAG: retrieval uses the vault's link graph (`[[wikilinks]]`) in addition to vector similarity, so related notes are pulled in the way you actually connected them.

## Goals

- **Local-first**: embeddings, vector store, and LLM all run on-device (no cloud APIs)
- **Graph-aware retrieval**: expand vector search results with linked notes
- **Grounded answers**: every answer cites the notes it came from
- **Measured, not assumed**: a small evaluation set to compare retrieval strategies

## Architecture

```mermaid
flowchart LR
    subgraph Indexing
        V[Obsidian Vault<br/>.md files] --> I[Ingest<br/>parse frontmatter,<br/>links, tags]
        I --> C[Chunk<br/>split by heading]
        C --> E1[Embed<br/>nomic-embed-text]
        E1 --> DB[(Chroma<br/>vector store)]
    end

    subgraph Querying
        Q[User question] --> E2[Embed query]
        E2 --> R[Vector search<br/>top-k chunks]
        DB --> R
        R --> G[Graph expansion<br/>add linked notes]
        G --> P[Build prompt]
        P --> L[Local LLM<br/>via Ollama]
        L --> A[Answer + sources]
    end
```

## Tech Stack

| Component | Choice | Why |
|---|---|---|
| Language | Python 3 | Best ecosystem for RAG tooling |
| Model runtime | Ollama | Simple local model serving |
| Embeddings | `nomic-embed-text` | Small, strong, runs locally |
| LLM | `llama3.2` | Fast enough on a laptop CPU |
| Vector store | Chroma | Embedded, no server to run |
| API (Phase 4) | FastAPI | Lightweight Python web server |
| UI (Phase 4) | Streamlit or Gradio | Chat UI in a few lines |

## Project Structure

```
obsidian-rag/
├── README.md
├── DEVLOG.md            # dated progress log + design decisions
├── requirements.txt
├── .gitignore
├── sample-vault/        # demo notes so anyone can run the project
├── src/
│   ├── ingest.py        # walk vault, parse notes, links, tags
│   ├── chunk.py         # heading-based chunking with metadata
│   ├── index.py         # embed chunks, store in Chroma
│   ├── retrieve.py      # vector search + graph expansion
│   └── query.py         # prompt building + LLM answer (CLI)
└── eval/
    ├── questions.json   # question → expected source note pairs
    └── evaluate.py      # retrieval hit-rate, with vs. without graph
```

## Roadmap

### Phase 1 — Setup
- [ ] Create sample vault (15–20 linked notes)
- [ ] Install Ollama, pull `nomic-embed-text` and `llama3.2`
- [ ] Python venv, dependencies, repo initialized

### Phase 2 — Minimal pipeline (CLI)
- [ ] `ingest.py`: parse notes, frontmatter, `[[links]]`, `#tags`
- [ ] `chunk.py`: split by heading, attach metadata
- [ ] `index.py`: embed + persist to Chroma
- [ ] `query.py`: retrieve top-k, generate answer with sources

### Phase 3 — Obsidian-specific
- [ ] Graph expansion: include chunks from linked/backlinked notes
- [ ] Evaluation set (10–15 questions)
- [ ] Compare retrieval with vs. without graph expansion; record results

### Phase 4 — Interface & polish
- [ ] FastAPI backend
- [ ] Streamlit/Gradio chat UI
- [ ] File watcher for automatic re-indexing
- [ ] (Stretch) Obsidian plugin via Local REST API

## Getting Started

```bash
# 1. Models
ollama pull nomic-embed-text
ollama pull llama3.2

# 2. Environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Index the sample vault and ask a question
python src/index.py --vault sample-vault
python src/query.py "your question here"
```

## Design Decisions

- **Chroma over pgvector**: single-user local app; no database server needed.
- **Heading-based chunking**: notes are written in sections, so chunks stay coherent.
- **Fully local models**: privacy is the point; also makes it safe for sensitive notes.

See `DEVLOG.md` for the reasoning behind decisions as the project evolves.

## Results

_To be filled in after Phase 3 evaluation._
