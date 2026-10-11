"""Split notes into heading-based, size-capped chunks ready for embedding.

Usage: python src/chunking.py --vault sample-vault [--show 3]
"""

import argparse
import re
from dataclasses import dataclass

from ingest import Note, Vault, load_vault

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")

DEFAULT_MAX_CHARS = 1500  # ~375 tokens; well under nomic-embed-text's limit, small enough to stay focused
DEFAULT_MIN_CHARS = 100  # smaller sections are merged into the next one
DEFAULT_SPLIT_LEVEL = 3  # split on #, ##, ###; deeper headings stay inside their section


@dataclass(frozen=True)
class Chunk:
    id: str  # "<note key>::<n>"; stable as long as the note is unchanged
    note_key: str
    heading_path: tuple[str, ...]  # e.g. ("Remedies",), or () for text before the first heading
    content: str  # the section's markdown
    text: str  # what gets embedded: a breadcrumb line, then the content


def _split_sections(body: str, title: str, split_level: int) -> list[tuple[tuple[str, ...], str]]:
    """Split a note body at headings into (heading path, content) pairs."""
    sections: list[tuple[tuple[str, ...], list[str]]] = [((), [])]
    stack: list[tuple[int, str]] = []  # (level, heading) for the current position
    in_fence = False
    for line in body.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
        match = None if in_fence else HEADING_RE.match(line)
        if not match or len(match.group(1)) > split_level:
            sections[-1][1].append(line)
            continue
        level, heading = len(match.group(1)), match.group(2)
        if level == 1 and heading == title:
            continue  # the note's own title is already in the breadcrumb
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, heading))
        sections.append((tuple(h for _, h in stack), []))
    return [(path, "\n".join(lines).strip()) for path, lines in sections]


def _merge_small(sections: list[tuple[tuple[str, ...], str]], min_chars: int) -> list[tuple[tuple[str, ...], str]]:
    """Fold sections shorter than min_chars into the following section (or the previous one, at the end)."""
    merged: list[tuple[tuple[str, ...], str]] = []
    carry = ""
    for path, content in sections:
        if not content:
            continue  # heading with nothing under it before the next heading
        if carry:
            content = f"{carry}\n\n{content}"
            carry = ""
        if len(content) < min_chars:
            # Keep the heading as bold text so its meaning survives the merge.
            carry = f"**{path[-1]}**\n{content}" if path else content
        else:
            merged.append((path, content))
    if carry:
        if merged:
            path, content = merged[-1]
            merged[-1] = (path, f"{content}\n\n{carry}")
        else:
            merged.append(((), carry))
    return merged


def _blocks(content: str) -> list[str]:
    """Split into paragraphs on blank lines, keeping fenced code blocks whole."""
    blocks, current, in_fence = [], [], False
    for line in content.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
        if not line.strip() and not in_fence:
            if current:
                blocks.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def _hard_wrap(block: str, max_chars: int) -> list[str]:
    """Last resort for a single paragraph over the limit: split by line, then by word."""
    units = []
    for line in block.splitlines():
        if len(line) <= max_chars:
            units.append(line)
            continue
        words, current = line.split(" "), ""
        for word in words:
            if current and len(current) + 1 + len(word) > max_chars:
                units.append(current)
                current = word
            else:
                current = f"{current} {word}" if current else word
        units.append(current)
    pieces, current = [], ""
    for unit in units:
        if current and len(current) + 1 + len(unit) > max_chars:
            pieces.append(current)
            current = unit
        else:
            current = f"{current}\n{unit}" if current else unit
    return pieces + [current] if current else pieces


def _split_long(content: str, max_chars: int) -> list[str]:
    """Pack paragraphs into pieces of at most max_chars."""
    if len(content) <= max_chars:
        return [content]
    pieces, current = [], ""
    for block in _blocks(content):
        for part in _hard_wrap(block, max_chars):
            if current and len(current) + 2 + len(part) > max_chars:
                pieces.append(current)
                current = part
            else:
                current = f"{current}\n\n{part}" if current else part
    return pieces + [current] if current else pieces


def _breadcrumb(note: Note, path: tuple[str, ...]) -> str:
    title = f"{note.title} ({', '.join(note.aliases)})" if note.aliases else note.title
    return " > ".join((title, *path))


def chunk_note(
    note: Note,
    max_chars: int = DEFAULT_MAX_CHARS,
    min_chars: int = DEFAULT_MIN_CHARS,
    split_level: int = DEFAULT_SPLIT_LEVEL,
) -> list[Chunk]:
    sections = _merge_small(_split_sections(note.body, note.title, split_level), min_chars)
    chunks = []
    for path, content in sections:
        for piece in _split_long(content, max_chars):
            chunks.append(
                Chunk(
                    id=f"{note.key}::{len(chunks)}",
                    note_key=note.key,
                    heading_path=path,
                    content=piece,
                    text=f"{_breadcrumb(note, path)}\n\n{piece}",
                )
            )
    return chunks


def chunk_vault(vault: Vault, **kwargs) -> list[Chunk]:
    return [chunk for note in vault.notes.values() for chunk in chunk_note(note, **kwargs)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Chunk an Obsidian vault and print a summary.")
    parser.add_argument("--vault", required=True, help="path to the vault folder")
    parser.add_argument("--exclude", nargs="*", default=[], help="vault folders to skip, e.g. templates")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--min-chars", type=int, default=DEFAULT_MIN_CHARS)
    parser.add_argument("--show", type=int, default=0, help="print the first N chunks in full")
    args = parser.parse_args()

    vault = load_vault(args.vault, tuple(args.exclude))
    chunks = chunk_vault(vault, max_chars=args.max_chars, min_chars=args.min_chars)
    sizes = [len(c.content) for c in chunks]
    print(f"{len(vault.notes)} notes -> {len(chunks)} chunks "
          f"(content chars: min {min(sizes)}, avg {sum(sizes) // len(sizes)}, max {max(sizes)})")
    for chunk in chunks[: args.show]:
        print(f"\n--- {chunk.id} ---\n{chunk.text}")


if __name__ == "__main__":
    main()
