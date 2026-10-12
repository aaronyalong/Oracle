# Dev Log

## 2026-10-10 — Phase 1 setup

**Done**
- Sample vault (`sample-vault/`): 18 notes across `AI/`, `Scala/`, and the vault root, with a `.obsidian/` folder like a real vault.
- `.gitignore` (venv, Chroma data, `vaults/` for real vaults), `requirements.txt`.

**Sample vault design**
- Two mostly separate topic clusters (AI/RAG and Scala) plus two hub-style notes (`Reading List`, `Project Ideas`) that link across them. Retrieval should keep the clusters apart; graph expansion can blur them, which is what the eval needs to catch.
- Notes contain specific, checkable facts (e.g. nomic-embed-text has 768 dimensions; learning rate 0.001 with Adam was most stable) so eval questions have one unambiguous source note.
- Exercises Obsidian syntax the parser must handle: frontmatter `tags` and `aliases`, inline and nested tags (`#course/cs4100`, `#ai/deep-learning`), `[[note|alias]]`, `[[note#heading]]`, `[[note#heading|alias]]`, and an embed `![[note#heading]]` in `Transformers`.
- Notes live in subfolders but links use bare note names, as Obsidian does by default — link resolution must match on file name, not path.

**Next**
- Install Ollama and models; create venv (both need sudo on this machine).
- Phase 2: `ingest.py` + tests.

## 2026-10-11 — Vault ingestion

**Done**
- `src/ingest.py`: `load_vault()` parses every note into a `Note` (title, body, frontmatter, tags, aliases, links), then resolves links into `outgoing` and `backlinks`. Links to missing notes are collected in `vault.unresolved`.
- 27 pytest tests covering link variants, tag rules, code-block skipping, and real-vault edge cases (broken YAML, duplicate note names, excluded folders).

**Decisions**
- Notes are keyed by vault-relative path, not name, because Obsidian allows duplicate names in different folders. Duplicates resolve to the same folder first, then the shortest path.
- Regex rather than a Markdown parser: the link and tag syntax is small, and code blocks/comments are blanked out first. Revisit (e.g. `markdown-it-py`) if real vaults expose edge cases.
- Aliases aren't used for link resolution, matching Obsidian; they're kept as extra search text.
- Embeds are recorded as links with `embed=True`; whether to inline embedded content is a chunking decision.
- Broken frontmatter logs a warning instead of failing the whole run.

**Known gaps:** links inside frontmatter properties, standard Markdown links `[text](note.md)`, `.canvas` files and attachments.

## 2026-10-11 — Chunking

**Done**
- `src/chunking.py`: `chunk_note()` / `chunk_vault()` turn notes into `Chunk`s with an ID, source note, heading path, raw content, and the text to embed. Sample vault: 18 notes → 58 chunks (112–527 chars).
- 16 new tests (43 total).

**Decisions**
- Named `chunking.py`, not `chunk.py`: Python ≤ 3.12 has a standard-library `chunk` module that ours would shadow.
- Split on headings up to `###`; deeper headings stay inside their section. A note's own `# Title` isn't a section.
- Sections under 100 chars merge into the next section (heading kept as bold text); sections over 1500 chars split on paragraph boundaries, keeping code blocks whole when they fit.
- Sizes are measured in characters, not tokens: no tokenizer dependency, and ~4 chars/token is close enough for a cap.
- Embedded text starts with a breadcrumb — `Title (aliases) > Heading > Subheading` — so each chunk makes sense on its own and alias searches ("RAG") match.
- The model-specific `search_document:` prefix is left to the indexer, so chunking stays model-agnostic.
- IDs are `<note path>::<n>`: deterministic, and the indexer will replace all of a note's chunks when it changes.
- Embeds (`![[...]]`) are not inlined yet — a candidate experiment once there's an eval baseline.

## 2026-10-11 — Indexing

**Done**
- `src/index.py`: embeds chunks with `nomic-embed-text` via Ollama and stores them in a persistent Chroma collection (`chroma/`, git-ignored). Sample vault: 58 chunks in 2.6s; an unchanged re-run takes 0.1s and embeds nothing.
- 8 tests using a fake embedder, so the suite runs without Ollama (51 total).
- Sanity check: "what learning rate worked best in my project?" → `Gradient Descent > Learning rate` ranked first; "how do I avoid blocking the thread pool in Scala?" → `Futures > ExecutionContext` first.

**Decisions**
- Incremental by note: each chunk stores a hash of its note's chunk texts + model name. Unchanged hash → skip; changed → delete all of that note's chunks and add the new ones; note gone from the vault → delete. Simpler than diffing individual chunks, and notes are small.
- Embed first, then delete/add, so if Ollama fails mid-run the old index survives.
- The link graph is not stored in Chroma. Backlinks change when *other* notes change, so stored copies would go stale; retrieval will rebuild the graph from the vault with `load_vault()` (milliseconds).
- Cosine distance, and the embedding model is recorded on the collection; switching models refuses to run until `--rebuild`, since vectors from different models aren't comparable.
- `search_document: ` prefix added here (nomic-embed-text's convention); queries will use `search_query: `.
- Embedding function is injected (`embed` parameter) — tests pass a fake, and it's the seam for trying other embedding models later.

## 2026-10-11 — Retrieval and answers (first end-to-end run)

**Done**
- `src/retrieve.py`: `vector_retriever()` — embeds the question with the `search_query: ` prefix and returns the top-k chunks as `Hit`s with cosine similarity scores.
- `src/query.py`: `answer(question, retrieve, generate, k)` returns an `Answer` (text + numbered sources); CLI prints the answer and marks which sources were actually cited.
- 9 tests with fake embedding/generation (60 total).

**First results (llama3.2, k=5)**
| Question | Top hit | Answer |
|---|---|---|
| what learning rate worked best in my project? | Gradient Descent > Learning rate (0.76) | Correct, cited [1] |
| how do I avoid blocking the thread pool in Scala? | Futures > ExecutionContext (0.68) | Correct, cited [1] |
| what is my favorite pizza topping? | Futures > Pitfall (0.50) | Correctly declined |

Latency 5–10s on CPU (the first call includes loading the model).

**Decisions**
- A retriever is just a function `(question, k) -> list[Hit]`, so graph expansion and hybrid search can be swapped in and compared by the eval script without touching `answer()`.
- `answer()` takes its retriever and generator as arguments: tests use fakes, and swapping LLMs is a flag (`--model`).
- Prompt: numbered excerpts, "use only these", cite as `[n]`, and an exact refusal phrase. `Answer.cited` parses the citations, which sets up a later check for unsupported citations.
- Temperature 0 so the same question gives the same answer — needed for repeatable evaluation.
- If nothing is retrieved, the LLM isn't called at all.

**Observations to follow up**
- Similarity scores are compressed: relevant ~0.65–0.76, irrelevant ~0.47–0.50. A minimum-score cutoff might drop junk context; worth testing once the eval set exists.
- Only 1 of 5 retrieved chunks was cited in each answer; the other 4 are noise. Lower k vs. reranking is another eval question.
- No streaming yet — the whole answer appears at once.

## 2026-10-11 — Evaluation harness and baseline

**Done**
- `eval/questions.json`: 15 questions, each with the note(s) that contain the answer, tagged by type: direct (5), paraphrase (5), alias (2), multi-hop (3).
- `src/evaluate.py`: runs each retrieval strategy at several k and reports hit@k, recall@k, and MRR, overall and per type, plus every miss. `--save` writes per-question results to JSON.
- 9 tests (69 total), including one that fails if a question names a note that doesn't exist.

**Baseline: vector search**
| k | hit | recall | MRR |
|---|---|---|---|
| 1 | 1.00 | 0.87 | 1.00 |
| 3 | 1.00 | 1.00 | 1.00 |
| 5 | 1.00 | 1.00 | 1.00 |

At k=1 the only misses are the multi-note questions (each found one of its two notes). By k=3 everything is found.

**Finding: the eval is saturated.** With 18 notes and 58 chunks, k=3 already covers ~5% of the whole vault, so almost anything relevant gets retrieved. Graph expansion can't show an improvement over a perfect score. Before Phase 3 the benchmark needs to be harder — more notes, near-duplicate distractor topics, multi-hop questions whose second note isn't similar to the question, and/or section-level (chunk) scoring instead of note-level.

**Decisions**
- Scoring is note-level: several chunks from one note count once, so a strategy can't look better just by returning more chunks of the same note.
- Questions are typed so results can show *where* a strategy helps or hurts (e.g. graph expansion should help multi-hop and might hurt direct questions).
- Questions were written before seeing results and not tuned afterwards.

## 2026-10-12 — Harder benchmark

**Why:** the first baseline was perfect at k=3 (see 2026-10-11), leaving nothing for graph expansion to improve.

**Changes**
- Sample vault grown from 18 to 59 notes (158 chunks), adding:
  - **Distractors** next to existing answers: Adam Optimizer and Learning Rate Schedules beside Gradient Descent; HNSW beside Vector Databases; Cats Effect, ZIO, and Akka beside Futures; Type Classes beside Implicits and Givens.
  - A **Databases** cluster (PostgreSQL, Indexes, SQLite, Transactions, Redis, Full-Text Search).
  - **Personal notes** — a course (CS4100), a project (Study Planner), and daily notes — whose facts are spread across linked notes.
- 31 questions (was 15): 10 direct, 9 paraphrase, 3 alias, 9 multi-hop. Six new multi-hop questions are *link-only*: the second note doesn't mention the subject of the question (e.g. "blocking calls in the effect library my Study Planner uses" → Study Planner links to ZIO; the ZIO note never mentions Study Planner).
- New **evidence** metric: each question lists short phrases that answer it, and the score is the fraction found in the retrieved chunk text. It checks the right *section* was retrieved, independent of chunking settings. Questions fail to load if a phrase isn't in one of their expected notes.

**Baseline (vector search, 59 notes)**
| k | hit | recall | MRR | evidence |
|---|---|---|---|---|
| 1 | 0.74 | 0.63 | 0.74 | 0.56 |
| 3 | 1.00 | 0.97 | 0.87 | 0.89 |
| 5 | 1.00 | 1.00 | 0.87 | 0.97 |

By type at k=3, multi-hop is the weakest on evidence (0.83) along with paraphrase (0.78). Link-only misses at k=3: `planner-search-index` (Full-Text Search not found), `cs4100-professor` (Gradient Descent not found).

**Findings**
- k=5 is still close to saturated; k=1 and k=3 are where strategies can be told apart. Graph expansion adds chunks, so comparisons must hold the total number of chunks given to the LLM fixed, or a strategy can win just by retrieving more.
- `auto-args` finds the right note but never the right section, even at k=5: the note's one-line intro was merged forward into the *Scala 2* section, and that chunk matches the question best. The Scala 3 `given`/`using` section isn't in the top 5. A chunking side effect to revisit (e.g. merge the intro into every section's breadcrumb instead of the first section).

## 2026-10-12 — Graph expansion, first attempt: it hurts

**Done**
- `graph_retriever(collection, embed, notes, seeds, boost)` in `src/retrieve.py`: keep the top `seeds` vector hits, collect their notes' 1-hop neighbours (outgoing links + backlinks), fetch those notes' best chunks, and fill the remaining slots by similarity with `boost` added to linked chunks. Always returns at most k chunks, so it's compared with vector search at the same context budget.
- `evaluate.py` sweeps seeds ∈ {1, 2} × boost ∈ {0.03, 0.05, 0.1, 1.0}; `--strategies` and `--by-type` flags.
- 8 tests with hand-placed fake embeddings (81 total).

**Results (evidence score)**
| strategy | k=3 | k=5 |
|---|---|---|
| vector | **0.89** | **0.97** |
| graph, 1 seed, boost 0.05 | 0.84 | 0.90 |
| graph, 1 seed, boost 1.0 | 0.76 | 0.81 |
| graph, 2 seeds, boost 0.05 | 0.87 | 0.92 |

Every graph variant is at or below the baseline, and more boost is worse. Full sweep in `eval/results/graph-sweep.json`.

**Why (per-question diff at k=3)**
- *Helps* when the top hit is the question's subject note: `oracle-reranker` (Project Ideas → Reranking), `planner-search-index` with 2 seeds (Study Planner → Full-Text Search).
- *Hurts* when the top hit is a **distractor** — `planner-blocking` seeds from Cats Effect, so its links lead away from ZIO and push the correct ZIO chunk out.
- *Hurts* when the top hit is a **hub** — the RAG note links to 6+ notes, so its neighbours are loosely related and displace good rank-2/3 hits (`merge-rankings`, `slow-first-answer`).
- With a fixed budget every linked chunk added is a vector hit removed, so expansion only pays off if the linked chunk is more useful than what it replaces.

**Ideas for a second attempt**
1. **Follow links from the retrieved chunk, not the whole note.** The Study Planner "Stack" section links exactly ZIO, sbt, PostgreSQL, and Full-Text Search; note-level neighbours also include everything else the note links to. This is closer to how a person follows links while reading.
2. **Down-weight hub notes** (e.g. boost ÷ number of links), like IDF for links.
3. **Only expand from confident seeds** (top score clearly above the rest).

**Caution:** all of this is tuned on the same 31 questions. Before claiming a win, confirm on questions written *after* the strategy is fixed (a held-out set).
