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

## 2026-10-12 — Graph expansion, second attempt: chunk-level links + held-out test

**Done**
- `graph_retriever(..., links=...)` now supports three ways of choosing linked notes:
  - `note` — every outgoing link and backlink of the seed notes (v1).
  - `chunk` — only links written inside the retrieved seed chunks.
  - `chunk+back` — chunk links plus the seed notes' backlinks.
- `ingest.resolve_link()` / `name_index()` made public so retrieval resolves links found in chunk text the same way ingestion does.
- 10 **held-out questions** (`eval/questions-holdout.json`), written *before* implementing v2 and run once, after picking the strategy on the 31 dev questions.
- 4 new tests (85 total).

**Dev set (31 questions), evidence score**
| strategy | k=3 | k=5 |
|---|---|---|
| vector | 0.89 | **0.97** |
| note links, 2 seeds, boost 0.05 | 0.87 | 0.92 |
| **chunk links, 2 seeds, boost 0.05** | **0.90** | 0.92 |
| chunk+back, 2 seeds, boost 0.05 | 0.87 | 0.92 |

Chunk-level links clearly beat note-level links and backlinks hurt, but nothing beats vector at k=5. Picked `chunk-s2-b0.05` for the held-out run: tied-best at k=3 and stable across boost values.

**Held-out set (10 questions), evidence score**
| strategy | k=3 | k=5 |
|---|---|---|
| vector | 0.75 | 0.95 |
| note links, 2 seeds, boost 0.05 | 0.80 | 1.00 |
| chunk links, 2 seeds, boost 0.05 (chosen) | 0.75 | 0.95 |

The chosen strategy is **identical to vector** on held-out. Note-level links did one question better here, after being worse on dev — differences are 1–2 questions in either direction, i.e. noise at this sample size.

**Conclusion: at a fixed context budget, graph expansion doesn't reliably beat vector search on this vault.**

**Why (from inspecting misses)**
- Linked notes are usually *also* semantically similar to the question, so vector search already finds them; the link rarely adds information the embedding didn't have.
- When a fact truly is link-only, expansion depends on the right *section* being a seed. In `h-cs4100-optimizer` the seed was CS4100 > *Topics* (links to Machine Learning, a dead end); the *Final project* section that links to Gradient Descent ranked 3rd.
- When expansion does find the right note (`h-planner-build`: Study Planner > Stack → sbt), the small boost often isn't enough to beat ranks 2–3, and a large boost hurts elsewhere.

**What this means for Oracle**
- Keep vector search as the default retriever; keep graph expansion as an option.
- Better uses of the link graph that don't compete for the same k slots: show linked notes as "related notes" in the UI; or give the model the k vector chunks *plus* a few linked chunks, and judge that on answer quality (it costs longer prompts).
- Bigger likely wins are elsewhere: hybrid keyword search (paraphrase misses), the chunk-merging bug (`auto-args`), and answer quality (false refusals).

## 2026-10-12 — Answer-quality benchmark and baseline

**Done**
- `eval/answers.json` (42 dev questions) and `eval/answers-holdout.json` (15): the retrieval questions plus **key facts** a correct answer must mention (each with acceptable spellings), 7 broad **topic** questions that should be summarized, and 9 **unanswerable** questions that should be refused — some tempting, like Redis's default port, which the model knows but the notes don't say (`forbidden: ["6379"]`).
- `src/evaluate_answers.py`: runs the full pipeline per question and reports facts found, fully-correct answers, wrong refusals, citation support (does a cited excerpt contain a fact?), correct refusals, made-up answers, and latency. `--show` prints every answer; `--save` keeps them.
- Prompts are now versioned (`PROMPTS` in `query.py`, `--prompt` flag) so prompt changes can be compared.
- 20 tests (105 total).

**Grader fixes after reading the first run.** Three "failures" were grading mistakes, not model mistakes, and were fixed: two answerable questions required a specific word when the answer was correct without it (`hnsw-ef-search`, `warmup`), and a good topic summary ending in a caveat ("I couldn't find general characteristics…") was counted as a refusal. Topic answers now only count as refusals if they cite nothing. Model mistakes were left as failures.

**Baseline: prompt v1, llama3.2, k=5 (dev)**
| | |
|---|---|
| Answerable: facts found | 0.92 |
| Answerable: fully correct | 0.87 (27/31) |
| Answerable: wrong refusals | 0.00 |
| Citations supported | 0.97 |
| Topic: wrong refusals | 0.00 |
| Unanswerable: correctly refused | 1.00 (6/6, including Redis port) |
| Average latency | 3.1 s (model warm) |

**Findings**
- The "artificial intelligence" wrong refusal from the 18-note vault no longer happens: the CS4100 note now literally says "Artificial Intelligence", and with that excerpt the model answers. Wrong refusals are 0 on this vault — the strict prompt isn't the problem it looked like.
- The remaining errors are **reasoning and completeness**, not refusals:
  - `planner-blocking` — had both the Study Planner (uses ZIO) and ZIO excerpts but answered with Cats Effect's `IO.blocking`. A 3B model failing to connect two excerpts.
  - `oracle-metric`, `softmax-attention` — answered only one part of a two-part question.
  - `auto-args` — retrieval issue (the chunk-merging bug), not generation.
- Next experiments should target these: a larger model, and a prompt that asks the model to answer every part of the question and to connect excerpts.

## 2026-10-19 — Answer quality: model × prompt experiment

**Done**
- Prompt **v2** (`PROMPTS["v2"]` in `query.py`): v1 plus "answer every part of the question", "combine excerpts when one names something and another explains it", and "summarize broad topics". Worded generally, not around specific questions.
- Ran {llama3.2, qwen2.5:7b} × {v1, v2} on the 42 dev questions, k=5.
- Grader fixes (classification only, found by reading answers): "X is not explicitly stated" now counts as a refusal; a long topic summary that forgot `[n]` citations counts as *uncited*, not as a refusal. 3 tests added (108 total).

**Selection rule, fixed before seeing the grid:** most fully-correct answers with **zero** made-up answers — a made-up answer with a fake citation is worse than a missing one.

**Dev results**
| setup | fully correct | wrong refusals | made up | avg time |
|---|---|---|---|---|
| llama3.2 + v1 | 0.87 | 0 | 0 | 6.0 s |
| llama3.2 + v2 | **0.97** | 0 | **1/6** | 7.9 s |
| qwen2.5:7b + v1 | 0.94 | 1/31 | 0 | 12.9 s |
| qwen2.5:7b + v2 | 0.94 | 1/31 | 0 | 14.6 s |

- v2 fixed llama3.2's incomplete and unconnected answers (`planner-blocking` now correct) but it **invented Redis's default port and cited the Redis note for it** ("According to excerpt [1], Redis listens on port 6379"). Ruled out.
- qwen2.5:7b is more accurate with either prompt; v2 added nothing for it. Picked **qwen2.5:7b + v1** (tie with v2, broken on speed).

**Held-out (15 questions, run once)**
| setup | fully correct | wrong refusals | made up | avg time |
|---|---|---|---|---|
| llama3.2 + v1 | 0.90 | 1/10 | 0/3 | 6.4 s |
| qwen2.5:7b + v1 | **1.00** | 0/10 | **1/3** | 12.9 s |

qwen2.5:7b answered "BRIN stands for Block Range INdex [1]" — true, but not in the notes, and the citation is fabricated.

**Conclusion**
- qwen2.5:7b is the more accurate model (0.94–1.00 fully correct), at about 2× the latency.
- **Both models sometimes answer from their own training knowledge and cite a note that doesn't support it** — llama3.2 with v2, qwen2.5:7b on held-out. The prompt alone can't reliably prevent this; the failure moves around rather than disappearing.
- The two fabrications share a pattern a simple check can catch: the key detail ("6379", "Block Range") does **not** appear in the cited excerpt. Next step: a **grounding check** that flags answers whose specific details (numbers, names, quoted terms) aren't in the excerpts they cite.
- Default stays llama3.2 + v1 until the grounding check exists; then re-evaluate qwen2.5:7b with it.

## 2026-10-19 — Real-vault test, topic rewrite, prompt v3

**First run on a real vault** (a private work vault; content not shared or committed). Retrieval worked well: right notes, nested heading paths intact. Generation exposed problems the sample vault hadn't:
1. **One-word topic queries are refused** ("X" → "I couldn't find that in your notes") by llama3.2 + v1, even with perfect excerpts.
2. **Long answers drop their citations** (llama3.2 + v2).
3. **Contradictory trailing refusal**: qwen2.5:7b answered with citations, then appended the refusal sentence.
4. **Superseded content**: real notes contain sections marked as old or wrong theories that the model may present as current.

**Changes**
- `rewrite_query()` in `query.py`: topic-style input (≤ 4 words, no `?`, no leading question word, or "tell me (everything) about X") is rewritten to "Summarize what my notes say about X." for the LLM only; retrieval still uses the original words. `--no-rewrite` disables it.
- `_drop_trailing_refusal()`: removes the refusal sentence from an answer that still cites sources without it.
- Prompt **v3** = v1 + "cite every fact" + "if excerpts disagree, trust the newer / non-superseded one and say the plan changed".
- Sample vault: a superseded plan in Study Planner (reminders first planned as cron + email, now push notifications). Grader: `forbidden` on answerable questions flags *outdated* answers unless they say the plan changed.
- Benchmark: +3 dev topic questions phrased like real usage ("Scala", "PostgreSQL", "tell me everything about Scala"), +1 superseded question; +2 held-out topic questions. Written before any run.
- 20 tests added (125 total). Work-vault terms that slipped into test examples were replaced with neutral ones.
- The vault change shifted held-out *retrieval* scores slightly (vector k=3 0.75→0.80, k=5 0.95→0.90); README table re-run and updated, conclusion unchanged.

**Results (46 dev / 17 held-out questions, k=5)**
| setup | dev fully correct | held-out fully correct | topic refusals | topic answers cited (dev) | made up (dev + held-out) | avg time |
|---|---|---|---|---|---|---|
| llama3.2 + v1 | 0.88 | — | **2/8** | 0.62 | 0/6 | 5.9 s |
| **llama3.2 + v1 + rewrite** | 0.88 | 0.80 | **0** | 0.62 | **0/9** | 5.7 s |
| qwen2.5:7b + v1 | 0.91 | 0.90 | 0 | **1.00** | 2/9 | 12.6 s |
| qwen2.5:7b + v1 + rewrite | 0.91 | — | 0 | 0.88 | 0/6 | 8.7 s |
| qwen2.5:7b + v3 + rewrite | **0.94** | 0.90 | 0 | 0.50 | 1/9 | 13.5 s |

- The rewrite fixes the small model's topic refusals (2 → 0) without changing anything else; qwen2.5:7b doesn't need it, and the "Summarize…" wording slightly reduces its citations.
- Every setup handled the superseded plan correctly (0 outdated answers), so v3's conflict rule wasn't needed here.
- v3's "cite every fact" backfired on topics: half its summaries had no citations at all.
- qwen2.5:7b fabricated "BRIN stands for Block Range INdex [1]" on held-out **under both prompts**, citing a note that doesn't say it — the third fabricated citation across experiments, all from outside knowledge.
- `hu-calendar-date` (qwen + v1, counted as made up) answered "calendar sync is next", which the notes do say. It's a too-strict label rather than a fabrication.

**Selection.** The pre-set rule (zero made-up, zero topic refusals, zero outdated, then most fully correct) picked qwen + v3 + rewrite on dev. It didn't consider citations, and that setup left half its topic summaries uncited, so "topic answers cited" was added **after seeing the results**. Held-out then disqualified both qwen setups anyway (BRIN).

**Default: llama3.2 + v1 + rewrite** — the only setup with zero made-up answers across all dev and held-out runs, and twice as fast. qwen2.5:7b stays available (`--model qwen2.5:7b`) as the more accurate but less trustworthy option.

**Next:** a grounding check — verify that the specific details in an answer (numbers, names, expansions like "Block Range") appear in the excerpts it cites. All three fabrications so far would have failed it. Then re-evaluate qwen2.5:7b with the check on. Smaller follow-up: make the rewrite ask for citations ("…, citing the excerpts").

## 2026-10-19 — Grounding check

**Why:** three fabricated citations across experiments (Redis port, BRIN expansion ×2), all from the model's own knowledge, all citing a note that doesn't say it. Prompting moved the failure around but didn't remove it.

**Done**
- `src/grounding.py`: deterministic check. Splits the answer into sentences, extracts checkable **details** — numbers (multi-digit), code that looks like code, short quotes (≤ 5 words), and multi-word capitalized names — and looks for each in the excerpts the sentence cites (all excerpts if it cites none). Details in the question count as supported.
  - **unsupported** = in no excerpt → likely outside knowledge.
  - **miscited** = in a different excerpt than the one cited → fact is in the notes, citation is sloppy; not a warning.
- Modes in `answer()` / `--grounding`: `off`, `warn` (default: keep the answer, report details; CLI prints ⚠), `strict` (drop sentences with unsupported details; refuse if nothing cited remains).
- Evaluator records unsupported details per answer and reports flagged rates.
- 19 tests, including the three real fabrications and correct answers that must not be flagged (144 total).

**Measured on every saved answer** (~470 across all runs; excerpts reconstructed by re-running deterministic retrieval; 10 answers from before the index change skipped):
| version | fabrications caught | good answers flagged |
|---|---|---|
| first draft | 3 / 3 | 24 / 296 (8.1%) |
| + miscited level, heading/possessive/plain-code/long-quote handling | 3 / 3 | 12 / 296 (4.1%) |

Of the remaining 12 flags, ~10 are genuinely outside knowledge but harmless — mostly spelled-out acronyms the notes don't expand ("Multi-Version Concurrency Control" ×7, "Large Language Model"), an invented example (`myFunction`), an invented version ("3.0"). ~2 are true false alarms. `hu-calendar-date` ("calendar sync is next") isn't flagged, consistent with judging it grounded.

**Caveat:** the checker's rules were refined while looking at these same answers, including held-out ones, so 3/3 and 4.1% are optimistic. Its real test is new answers.

**Strict mode, simulated on saved answers** (strict only edits generated text, so this equals a live run)
| setup | mode | fully correct dev / held-out | made up | topic refusals | topics cited |
|---|---|---|---|---|---|
| llama3.2 + v1 + rewrite | off = strict | 0.88 / 0.80 | 0/9 | 0/12 | 8/12 |
| qwen2.5:7b + v1 | off | 0.91 / 0.90 | 2/9 | 0/12 | 12/12 |
| qwen2.5:7b + v1 | **strict** | **0.91 / 0.90** | **1/9** (calendar, judged grounded) | 0/12 | **12/12** |
| qwen2.5:7b + v3 + rewrite | strict | 0.94 / 0.90 | 0/9 | 2/12 | 8/12 |

- Strict removes qwen2.5:7b + v1's real fabrication (BRIN) with no loss in accuracy, topics, or citations.
- With v3, strict turns uncited topic summaries into refusals — it depends on the model citing.
- **Best setup: qwen2.5:7b + v1 + strict grounding.** Cost: ~2× latency vs llama3.2 (~13 s vs ~6 s on CPU).

**Design tension for the UI:** strict mode needs the whole answer before showing anything, which conflicts with streaming. Warn mode streams fine (warnings appear at the end). Likely UI design: stream, then mark unsupported sentences.

## 2026-10-19 — Keyword, Obsidian-like, and hybrid search

**Why:** Obsidian already has a search bar (lexical). How does Oracle's retrieval compare, and does adding keyword matching fix vector search's weakness on exact terms?

**Done** (`src/retrieve.py`)
- `BM25` (Okapi, k1=1.5, b=0.75) implemented directly (~25 lines, no dependency) over the same chunks the vector index holds; simple tokenizer with an English stopword list.
- `keyword_retriever` — BM25 ranking.
- `obsidian_like_retriever` — approximates the search bar: a note matches only if it contains *every* term (case-insensitive substring, as Obsidian does); matching chunks ranked by BM25. Drops stopwords, which the real search bar doesn't, so it's an upper bound on typing the question in.
- `hybrid_retriever` — vector + BM25 merged with Reciprocal Rank Fusion (score = Σ 1/(60 + rank), each list's top 30). Rank-based, so no score scaling and no weights to tune. Hits record `via` = vector / keyword / both.
- 11 tests (155 total). One caught a real bug: the Obsidian-like matcher accepted "expire" ⊂ "expired" but then ranked by whole-word BM25 and dropped it; ranking is now substring-aware too.

**Results (evidence score)**
| strategy | dev k=1 | dev k=3 | dev k=5 | held-out k=1 | held-out k=3 | held-out k=5 |
|---|---|---|---|---|---|---|
| Obsidian-like (question typed into search) | 0.15 | 0.15 | 0.15 | 0.00 | 0.00 | 0.10 |
| keyword (BM25) | 0.50 | 0.85 | 0.90 | 0.55 | 0.75 | 0.90 |
| vector | 0.56 | **0.89** | **0.97** | 0.55 | 0.80 | 0.90 |
| **hybrid** | **0.60** | **0.89** | 0.92 | **0.65** | **0.90** | **1.00** |

By type (dev, k=3): keyword matches vector on direct questions (1.00) but trails on paraphrases (0.67 vs 0.78); hybrid is ≥ vector on every type. Obsidian-like scores 0.00 on paraphrases.

**Findings**
- Typing a natural-language question into an all-terms-must-match search finds the answer section for ~15% of questions. Caveat: people type keywords into a search bar, not questions — this measures the question-answering use case, not the search bar at its own job.
- BM25 alone is a strong baseline (top-1 note hit 0.77 dev vs vector's 0.74) — the questions often share exact terms with the notes.
- Hybrid is best for the **top results** (k=1 on both sets, k=3 on held-out), which is what a search UI shows first. At k=5 it's mixed: worse on dev (0.92 vs 0.97; lost `train-vs-new`, `cs4100-professor`), better on held-out (1.00 vs 0.90). Differences are 1–2 questions.

**Decisions**
- **Search mode** (ranked sections, no LLM) will use **hybrid**.
- **Ask mode** keeps **vector** at k=5: tied overall, and the answer-quality results were measured with it. Re-testing answers with hybrid is an optional follow-up.

## 2026-10-19 — Local server and web UI

**Done**
- `src/server.py` (FastAPI), listening on `127.0.0.1` only:
  - `GET /api/search` — hybrid search, ranked sections with `obsidian://open` links (~0.1–0.5 s, no LLM).
  - `GET /api/ask` — streams the answer as Server-Sent Events (`token` events as the model writes, then a `done` event with final text, sources, citations, and unsupported details).
  - `POST /api/index` — incremental re-index; retrievers are rebuilt afterwards because BM25 holds a snapshot of the chunks.
  - Indexes incrementally on startup, so the index always matches the vault.
  - CORS allows Obsidian's app origin, ready for the plugin.
- `query.answer()` split into `prepare()` (retrieve + prompt) and `finish()` (cleanup + grounding) so the server can stream generation in between; `ollama_streamer()` added. Behaviour unchanged (all existing tests pass).
- `web/index.html`: one file, plain JavaScript, no build step. Ask tab (streamed answer, clickable `[n]` citations, cited sources highlighted, ⚠ for unsupported details) and Search tab (results as you type, debounced). All note text is inserted with `textContent`, never parsed as HTML.
- 9 server tests with FastAPI's test client and fake models (164 total).

**Decisions**
- **Ask uses `warn` grounding, not `strict`:** streamed text is already on screen, so unsupported details are flagged at the end rather than removed. The CLI keeps `strict`.
- **Search uses hybrid, Ask uses vector** — per the keyword/hybrid evaluation.
- **Server-Sent Events over WebSockets:** one-directional streaming is all that's needed, it's plain HTTP, and browsers support it natively (`EventSource`).
- **GET for `/api/ask`:** `EventSource` only supports GET; questions fit in a URL.

**Smoke test (real models):** search for "thread pool blocking" returned Cats Effect / Futures / ZIO blocking sections, all found by both vector and keyword search; "What learning rate worked best?" streamed 38 chunks, then the final answer citing Gradient Descent with no unsupported details.

## 2026-10-19 — Obsidian plugin v0.1

**Done** (`obsidian-plugin/`, TypeScript, built with esbuild)
- **Sidebar panel** with Ask (streamed answer, clickable `[n]` citations, ⚠ unsupported details) and Search (results as you type) tabs, calling the same server endpoints as the web page.
- **Open at section:** sources and citations open the note at the cited heading with Obsidian's `openLinkText` (Ctrl/Cmd-click for a new tab) — better than `obsidian://` links, which only open the file.
- **Automatic re-indexing:** listens to vault modify/create/delete/rename events for Markdown files and calls `POST /api/index` after a quiet period (default 5 s). Listeners are registered after layout-ready, because Obsidian reports every existing file as "created" while loading.
- **Safety checks:** the status line warns if the server is indexing a different vault than the one open; if the server isn't running, the panel shows the exact command to start it for this vault.
- **Settings tab:** server address, auto re-index on/off, delay.
- Code split into `format.ts` (pure logic: citation parsing, link text, labels — unit tested with `node --test`, no Obsidian needed), `api.ts` (server client: `requestUrl` for JSON, `EventSource` for the stream), `main.ts` (plugin, view, settings).
- Server test confirms CORS allows Obsidian's `app://obsidian.md` origin and rejects others (165 Python tests, 4 plugin tests).

**Decisions**
- **Plain DOM, no React/Svelte:** the panel is small; Obsidian's `createEl` helpers are enough and avoid a framework dependency.
- **Theme variables only** in `styles.css`, so the panel matches any Obsidian theme.
- **Build output goes into the vault's plugin folder** (`OBSIDIAN_PLUGIN_DIR`, default the sample vault), which is git-ignored; only source is committed.
- **Desktop only** (`isDesktopOnly`): it needs a local server.

**Not verified here:** the panel's behaviour inside Obsidian — the build type-checks and the logic is unit tested, but the UI needs a manual check in the app.

**First manual test found a bug:** the view's helper `open(hit, event)` overrode `ItemView.open()`, an undocumented internal method Obsidian calls when it opens the panel, so opening the panel crashed (`Cannot read properties of undefined (reading 'replace')`). TypeScript couldn't catch it because `open` isn't in Obsidian's published type definitions. Renamed to `openHit`. Lesson: prefix plugin-specific method names on classes that extend Obsidian's.
