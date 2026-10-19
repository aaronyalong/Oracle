"""Check that the specific details in an answer appear in the excerpts it cites.

Models sometimes answer from their own training data and cite a note that doesn't support the
claim ("Redis listens on port 6379 [1]"). This check is deterministic: it pulls out details that
are easy to verify — numbers, `code`, "quoted terms", and multi-word names — and looks for each one
in the excerpts the sentence cites. It can't judge paraphrased claims; it catches invented specifics.
"""

import re
from dataclasses import dataclass

CITATION_RE = re.compile(r"\[(\d+)\]")
LIST_MARKER_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+", re.MULTILINE)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
# Standalone numbers, dates, versions: 6379, 0.001, 2026-09-20, 1,500. Not digits inside words (CS4100).
NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:[.,:/-]\d+)*(?![\w])")
CODE_RE = re.compile(r"`([^`\n]+)`")
QUOTED_RE = re.compile(r"[\"“]([^\"”\n]{3,})[\"”]")
# Two or more capitalized words in a row: "Block Range INdex", "Read Committed", "Apache Pekko".
NAME_RE = re.compile(r"\b[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)+")
MARKDOWN_RE = re.compile(r"\*\*|__|\[\[|\]\]")
# Code spans that look like code (dots, parens, underscores, digits, camelCase), not `emphasis`.
CODE_LIKE_RE = re.compile(r"[._()/\d]|[a-z][A-Z]")
MAX_QUOTE_WORDS = 5  # longer quotes are usually paraphrased from the note, not copied


@dataclass(frozen=True)
class Claim:
    sentence: str
    citations: list[int]  # 1-based excerpt numbers the sentence cites; empty = checked against all excerpts
    details: list[str]  # specifics extracted from the sentence
    unsupported: list[str]  # details found in none of the excerpts or the question: likely outside knowledge
    miscited: list[str]  # details found in the excerpts, but not in the ones this sentence cites


def _normalize(text: str) -> str:
    text = MARKDOWN_RE.sub("", text).replace("`", "")
    return re.sub(r"\s+", " ", text).lower()


def extract_details(sentence: str) -> list[str]:
    """Specific, checkable details in one sentence, without citation markers."""
    text = MARKDOWN_RE.sub("", CITATION_RE.sub("", sentence)).strip()
    if text.endswith(":"):
        return []  # a heading the model wrote ("Development Notes:"), not a claim
    details = [c for c in CODE_RE.findall(text) if CODE_LIKE_RE.search(c)]
    details += [q.strip(" .,;") for q in QUOTED_RE.findall(text) if len(q.split()) <= MAX_QUOTE_WORDS]
    without_code = CODE_RE.sub(" ", text)
    details += [re.sub(r"['’]s$", "", name) for name in NAME_RE.findall(without_code)]
    # Single-digit integers ("3 steps", "2 excerpts") are too often paraphrase to check reliably.
    details += [n for n in NUMBER_RE.findall(without_code) if len(n) > 1]
    return list(dict.fromkeys(d.strip() for d in details if d.strip()))


def _found(detail: str, haystack: str) -> bool:
    d = _normalize(detail)
    if d in haystack or d.replace(",", "") in haystack.replace(",", ""):
        return True
    # "The Study Planner" -> also try "Study Planner": sentence-initial words get capitalized.
    words = d.split(" ", 1)
    return len(words) == 2 and NAME_RE.fullmatch(detail.strip()) is not None and words[1] in haystack


def check_grounding(answer_text: str, excerpts: list[str], question: str = "") -> list[Claim]:
    """One Claim per sentence that contains checkable details.

    Each detail is looked for in the excerpts the sentence cites (all excerpts if it cites none,
    since models often cite once per paragraph). A detail missing there but present in another
    excerpt is *miscited*; missing from every excerpt and from the question, it's *unsupported*.
    """
    everything = _normalize("\n".join(excerpts) + "\n" + question)
    claims = []
    for sentence in SENTENCE_SPLIT_RE.split(LIST_MARKER_RE.sub("", answer_text)):
        sentence = sentence.strip()
        details = extract_details(sentence)
        if not details:
            continue
        cited = sorted({int(n) for n in CITATION_RE.findall(sentence) if 1 <= int(n) <= len(excerpts)})
        cited_text = _normalize("\n".join(excerpts[n - 1] for n in cited) + "\n" + question) if cited else everything
        missing = [d for d in details if not _found(d, cited_text)]
        unsupported = [d for d in missing if not _found(d, everything)]
        miscited = [d for d in missing if d not in unsupported]
        claims.append(Claim(sentence, cited, details, unsupported, miscited))
    return claims


def unsupported_details(answer_text: str, excerpts: list[str], question: str = "") -> list[str]:
    return [d for claim in check_grounding(answer_text, excerpts, question) for d in claim.unsupported]
