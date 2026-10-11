from pathlib import Path

import pytest

from chunking import chunk_note, chunk_vault
from ingest import Note, load_vault

SAMPLE_VAULT = Path(__file__).parent.parent / "sample-vault"


def make_note(body: str, title: str = "Note", aliases: list[str] | None = None) -> Note:
    return Note(
        path=Path(f"{title}.md"),
        title=title,
        body=body,
        frontmatter={},
        tags=set(),
        aliases=aliases or [],
        links=[],
    )


def paths(chunks):
    return [c.heading_path for c in chunks]


# --- Splitting on headings ---


def test_no_headings_is_one_chunk():
    chunks = chunk_note(make_note("Just a paragraph."), min_chars=0)
    assert paths(chunks) == [()]
    assert chunks[0].content == "Just a paragraph."


def test_heading_paths_and_title_h1_skipped():
    body = "# Note\nIntro.\n## A\nText A.\n### A1\nText A1.\n## B\nText B."
    chunks = chunk_note(make_note(body), min_chars=0)
    assert paths(chunks) == [(), ("A",), ("A", "A1"), ("B",)]
    assert [c.content for c in chunks] == ["Intro.", "Text A.", "Text A1.", "Text B."]


def test_headings_deeper_than_split_level_stay_in_content():
    body = "## A\nText.\n#### Detail\nMore."
    chunks = chunk_note(make_note(body), min_chars=0, split_level=3)
    assert paths(chunks) == [("A",)]
    assert "#### Detail" in chunks[0].content


def test_hash_lines_in_code_are_not_headings():
    body = "## Script\n```python\n# a comment, not a heading\nx = 1\n```"
    chunks = chunk_note(make_note(body), min_chars=0)
    assert paths(chunks) == [("Script",)]
    assert "# a comment" in chunks[0].content


def test_empty_sections_are_dropped():
    body = "## Parent\n### Child\nOnly the child has text."
    assert paths(chunk_note(make_note(body), min_chars=0)) == [("Parent", "Child")]


def test_tag_lines_are_not_headings():
    body = "## A\nText.\n#ai #scala"
    chunks = chunk_note(make_note(body), min_chars=0)
    assert paths(chunks) == [("A",)]


# --- Merging small sections ---


def test_small_sections_merge_forward_keeping_heading():
    body = "## Tiny\nShort.\n## Big\n" + "Long text. " * 20
    chunks = chunk_note(make_note(body), min_chars=50)
    assert paths(chunks) == [("Big",)]
    assert chunks[0].content.startswith("**Tiny**\nShort.")


def test_small_last_section_merges_backward():
    body = "## Big\n" + "Long text. " * 20 + "\n## Tiny\nShort."
    chunks = chunk_note(make_note(body), min_chars=50)
    assert paths(chunks) == [("Big",)]
    assert chunks[0].content.endswith("**Tiny**\nShort.")


def test_whole_note_smaller_than_min_still_produces_a_chunk():
    chunks = chunk_note(make_note("## Only\nShort."), min_chars=50)
    assert len(chunks) == 1


# --- Size cap ---


def test_long_sections_are_split_under_the_cap():
    paragraphs = "\n\n".join(f"Paragraph {i}. " + "word " * 40 for i in range(10))
    chunks = chunk_note(make_note(f"## Long\n{paragraphs}"), max_chars=500, min_chars=0)
    assert len(chunks) > 1
    assert all(len(c.content) <= 500 for c in chunks)
    assert all(c.heading_path == ("Long",) for c in chunks)


def test_single_huge_paragraph_is_hard_wrapped():
    chunks = chunk_note(make_note("word " * 1000), max_chars=300, min_chars=0)
    assert all(len(c.content) <= 300 for c in chunks)
    assert sum(c.content.count("word") for c in chunks) == 1000


def test_code_block_with_blank_lines_is_not_split_when_it_fits():
    code = "```scala\nval a = 1\n\nval b = 2\n```"
    body = "## Code\n" + "Intro text. " * 30 + "\n\n" + code
    chunks = chunk_note(make_note(body), max_chars=400, min_chars=0)
    assert any(code in c.content for c in chunks)


# --- Embedding text and IDs ---


def test_text_has_breadcrumb_with_aliases():
    note = make_note("## Pipeline\nSteps.", title="Retrieval-Augmented Generation", aliases=["RAG"])
    chunk = chunk_note(note, min_chars=0)[0]
    assert chunk.text == "Retrieval-Augmented Generation (RAG) > Pipeline\n\nSteps."


def test_ids_are_unique_and_deterministic():
    body = "## A\nText A.\n## B\nText B."
    first, second = chunk_note(make_note(body), min_chars=0), chunk_note(make_note(body), min_chars=0)
    assert [c.id for c in first] == ["Note.md::0", "Note.md::1"]
    assert [c.id for c in first] == [c.id for c in second]


# --- Sample vault ---


@pytest.fixture(scope="module")
def sample_chunks():
    return chunk_vault(load_vault(SAMPLE_VAULT))


def test_every_note_is_chunked_within_limits(sample_chunks):
    assert {c.note_key for c in sample_chunks} == set(load_vault(SAMPLE_VAULT).notes)
    assert all(0 < len(c.content) <= 1500 for c in sample_chunks)
    assert len({c.id for c in sample_chunks}) == len(sample_chunks)


def test_fact_lands_in_the_right_section(sample_chunks):
    [chunk] = [c for c in sample_chunks if "0.001 with Adam" in c.content]
    assert chunk.note_key == "AI/Gradient Descent.md"
    assert chunk.heading_path == ("Learning rate",)
    assert chunk.text.startswith("Gradient Descent > Learning rate\n")
