"""Read an Obsidian vault into Note records: frontmatter, tags, links, backlinks.

Usage: python src/ingest.py --vault sample-vault
"""

import argparse
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter
import yaml

log = logging.getLogger(__name__)

# Code and Obsidian comments (%% ... %%) can contain [[...]] or #... that aren't real links/tags.
IGNORED_RE = re.compile(r"```.*?```|~~~.*?~~~|`[^`\n]*`|%%.*?%%", re.DOTALL)
# [[target]], [[target|alias]], [[target#heading]], [[target#^block]], and embeds ![[...]]
LINK_RE = re.compile(r"(!?)\[\[([^\[\]\n]+?)\]\]")
# A tag starts after whitespace or at line start, so headings ("# Title") and URLs ("a.com/#x") don't match.
TAG_RE = re.compile(r"(?<!\S)#([\w/-]+)")
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Link:
    target: str  # note name as written; "" for same-note links like [[#Heading]]
    heading: str | None = None
    block: str | None = None
    alias: str | None = None
    embed: bool = False


@dataclass
class Note:
    path: Path  # relative to the vault root
    title: str
    body: str  # markdown without frontmatter
    frontmatter: dict
    tags: set[str]
    aliases: list[str]
    links: list[Link]
    outgoing: set[str] = field(default_factory=set)  # keys of notes this one links to
    backlinks: set[str] = field(default_factory=set)  # keys of notes linking here

    @property
    def key(self) -> str:
        """Unique ID: the vault-relative path, e.g. 'AI/Embeddings.md'."""
        return self.path.as_posix()

    @property
    def name(self) -> str:
        """What [[links]] use: the file name without .md."""
        return self.path.stem


@dataclass
class Vault:
    root: Path
    notes: dict[str, Note]  # by Note.key
    unresolved: list[tuple[str, str]]  # (source key, link target) for links to missing notes


def _strip_ignored(text: str) -> str:
    return IGNORED_RE.sub(" ", text)


def parse_links(text: str) -> list[Link]:
    links = []
    for bang, inner in LINK_RE.findall(_strip_ignored(text)):
        target, _, alias = inner.partition("|")
        target, _, subpath = target.partition("#")
        heading = block = None
        if subpath.startswith("^"):
            block = subpath[1:]
        elif subpath:
            heading = subpath
        links.append(
            Link(
                target=target.strip().removesuffix(".md"),
                heading=heading.strip() if heading else None,
                block=block,
                alias=alias.strip() or None,
                embed=bang == "!",
            )
        )
    return links


def _normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#").lower()


def parse_tags(text: str) -> set[str]:
    tags = set()
    for tag in TAG_RE.findall(_strip_ignored(text)):
        tag = _normalize_tag(tag.rstrip("/"))
        # Obsidian requires at least one non-digit character, so #2024 isn't a tag.
        if tag and not tag.replace("/", "").isdigit():
            tags.add(tag)
    return tags


def _as_list(value, split_pattern: str) -> list[str]:
    """Frontmatter fields may be a list or a single string; normalize to a list."""
    if value is None:
        return []
    if isinstance(value, str):
        return [v for v in re.split(split_pattern, value) if v.strip()]
    return [str(v) for v in value if v is not None]


def parse_note(path: Path, root: Path) -> Note:
    text = path.read_text(encoding="utf-8")
    try:
        post = frontmatter.loads(text)
        meta, body = dict(post.metadata), post.content
    except yaml.YAMLError as e:
        # Real vaults have broken frontmatter; keep the note rather than crash.
        log.warning("Bad frontmatter in %s, treating it as plain text: %s", path, e)
        meta, body = {}, text

    fm_tags = _as_list(meta.get("tags", meta.get("tag")), r"[,\s]+")
    tags = {_normalize_tag(t) for t in fm_tags if _normalize_tag(t)} | parse_tags(body)
    # Aliases can contain spaces ("vector embeddings"), so only split strings on commas.
    aliases = [a.strip() for a in _as_list(meta.get("aliases", meta.get("alias")), r",")]

    h1 = H1_RE.search(_strip_ignored(body))
    title = str(meta.get("title") or (h1.group(1) if h1 else path.stem))

    return Note(
        path=path.relative_to(root),
        title=title,
        body=body,
        frontmatter=meta,
        tags=tags,
        aliases=aliases,
        links=parse_links(body),
    )


def name_index(notes: dict[str, Note]) -> dict[str, list[str]]:
    """Lower-cased note name -> keys of notes with that name (several if names repeat across folders)."""
    by_name: dict[str, list[str]] = defaultdict(list)
    for key, note in notes.items():
        by_name[note.name.lower()].append(key)
    return by_name


def resolve_link(target: str, source: Note, notes: dict[str, Note], by_name: dict[str, list[str]]) -> str | None:
    """Find the key of the note a link points to, matching Obsidian's case-insensitive rules."""
    if not target:
        return source.key
    t = target.lower()
    if "/" in t:
        # Path-style link: [[Scala/Futures]]
        candidates = [k for k in notes if k.lower().removesuffix(".md").endswith(t)]
    else:
        candidates = by_name.get(t, [])
    if len(candidates) <= 1:
        return candidates[0] if candidates else None
    # Duplicate names in different folders: prefer the source's folder, then the shortest path.
    same_folder = [k for k in candidates if notes[k].path.parent == source.path.parent]
    return (same_folder or sorted(candidates, key=lambda k: (k.count("/"), k)))[0]


def load_vault(root: str | Path, exclude: tuple[str, ...] = ()) -> Vault:
    """Parse every note under root. Hidden folders (.obsidian, .trash) are always skipped;
    `exclude` adds vault-relative folders such as 'templates'."""
    root = Path(root)
    excluded = tuple(e.strip("/") + "/" for e in exclude)

    notes: dict[str, Note] = {}
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts) or rel.as_posix().startswith(excluded):
            continue
        note = parse_note(path, root)
        notes[note.key] = note

    by_name = name_index(notes)
    unresolved = []
    for note in notes.values():
        for link in note.links:
            target_key = resolve_link(link.target, note, notes, by_name)
            if target_key is None:
                unresolved.append((note.key, link.target))
            elif target_key != note.key:
                note.outgoing.add(target_key)
                notes[target_key].backlinks.add(note.key)

    return Vault(root=root, notes=notes, unresolved=unresolved)


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse an Obsidian vault and print a summary.")
    parser.add_argument("--vault", required=True, help="path to the vault folder")
    parser.add_argument("--exclude", nargs="*", default=[], help="vault folders to skip, e.g. templates")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    vault = load_vault(args.vault, tuple(args.exclude))
    notes = vault.notes.values()
    print(f"{len(vault.notes)} notes, {sum(len(n.outgoing) for n in notes)} resolved links, "
          f"{len(vault.unresolved)} unresolved, {len(set().union(*(n.tags for n in notes)))} tags")
    print("\nMost linked-to notes:")
    for note in sorted(notes, key=lambda n: len(n.backlinks), reverse=True)[:5]:
        print(f"  {len(note.backlinks):>2}  {note.key}")
    if vault.unresolved:
        print("\nUnresolved links:")
        for source, target in vault.unresolved:
            print(f"  {source} -> [[{target}]]")


if __name__ == "__main__":
    main()
