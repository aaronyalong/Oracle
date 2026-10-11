from pathlib import Path

import pytest

from ingest import Link, load_vault, parse_links, parse_tags

SAMPLE_VAULT = Path(__file__).parent.parent / "sample-vault"


# --- Link parsing ---


@pytest.mark.parametrize(
    "text, expected",
    [
        ("[[Scala]]", Link("Scala")),
        ("[[Machine Learning|ML overview]]", Link("Machine Learning", alias="ML overview")),
        ("[[Neural Networks#Training tricks]]", Link("Neural Networks", heading="Training tricks")),
        (
            "[[Attention Mechanism#Scaled dot-product attention|scaled attention]]",
            Link("Attention Mechanism", heading="Scaled dot-product attention", alias="scaled attention"),
        ),
        ("[[Futures#^abc123]]", Link("Futures", block="abc123")),
        ("![[Attention Mechanism#Cost]]", Link("Attention Mechanism", heading="Cost", embed=True)),
        ("[[#Pitfall]]", Link("", heading="Pitfall")),
        ("[[Scala/Futures.md]]", Link("Scala/Futures")),
    ],
)
def test_parse_links_variants(text, expected):
    assert parse_links(text) == [expected]


def test_links_in_code_are_ignored():
    text = "Use `[[wikilinks]]` here.\n```\n[[Not A Link]]\n```\n%% [[Hidden]] %%\n[[Real]]"
    assert parse_links(text) == [Link("Real")]


# --- Tag parsing ---


def test_parse_tags_inline_and_nested():
    assert parse_tags("Notes #ai and #ai/deep-learning, plus #Scala") == {"ai", "ai/deep-learning", "scala"}


@pytest.mark.parametrize(
    "text",
    [
        "# Heading",
        "## Sub heading",
        "issue#42 mid-word",
        "#2024 is just a number",
        "see https://example.com/#anchor",
        "`#not-a-tag` in code",
    ],
)
def test_parse_tags_ignores_non_tags(text):
    assert parse_tags(text) == set()


# --- Whole vault ---


@pytest.fixture(scope="module")
def vault():
    return load_vault(SAMPLE_VAULT)


def test_loads_all_notes_and_skips_hidden_folders(vault):
    assert len(vault.notes) == 18
    assert not any(k.startswith(".obsidian") for k in vault.notes)


def test_every_sample_link_resolves(vault):
    # Includes the `[[wikilinks]]` in Project Ideas, which is inside inline code.
    assert vault.unresolved == []


def test_links_resolve_across_folders(vault):
    # Reading List is at the root; Transformers is in AI/.
    assert "AI/Transformers.md" in vault.notes["Reading List.md"].outgoing


def test_backlinks(vault):
    assert vault.notes["Scala/Scala.md"].backlinks == {
        "Scala/Case Classes.md",
        "Scala/Futures.md",
        "Reading List.md",
    }


def test_embed_is_a_link(vault):
    transformers = vault.notes["AI/Transformers.md"]
    assert Link("Attention Mechanism", heading="Scaled dot-product attention", embed=True) in transformers.links


def test_frontmatter_and_inline_tags_merge(vault):
    assert vault.notes["AI/Machine Learning.md"].tags == {"ai", "hub", "course/cs4100"}


def test_aliases_and_title(vault):
    note = vault.notes["AI/Embeddings.md"]
    assert note.aliases == ["vector embeddings"]
    assert note.title == "Embeddings"
    assert note.name == "Embeddings"


# --- Edge cases in a temporary vault ---


def test_bad_frontmatter_does_not_crash(tmp_path):
    (tmp_path / "Broken.md").write_text("---\ntags: [unclosed\n---\n# Broken\n#rescued", encoding="utf-8")
    note = load_vault(tmp_path).notes["Broken.md"]
    assert note.title == "Broken"
    assert "rescued" in note.tags


def test_string_frontmatter_fields(tmp_path):
    (tmp_path / "N.md").write_text("---\ntags: a, b\naliases: one alias, two\n---\nbody", encoding="utf-8")
    note = load_vault(tmp_path).notes["N.md"]
    assert note.tags == {"a", "b"}
    assert note.aliases == ["one alias", "two"]


def test_duplicate_names_prefer_same_folder(tmp_path):
    for folder in ("a", "b"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "Index.md").write_text("x", encoding="utf-8")
    (tmp_path / "b" / "Source.md").write_text("[[Index]]", encoding="utf-8")
    assert load_vault(tmp_path).notes["b/Source.md"].outgoing == {"b/Index.md"}


def test_unresolved_and_excluded(tmp_path):
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "Daily.md").write_text("[[Ghost]]", encoding="utf-8")
    (tmp_path / "Note.md").write_text("[[Missing Note]]", encoding="utf-8")
    vault = load_vault(tmp_path, exclude=("templates",))
    assert list(vault.notes) == ["Note.md"]
    assert vault.unresolved == [("Note.md", "Missing Note")]
