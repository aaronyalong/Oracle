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
