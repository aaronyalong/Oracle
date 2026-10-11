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
