"""Grounding check tests. The fabrication cases are real model outputs from the evaluation runs."""

import pytest

from grounding import check_grounding, extract_details, unsupported_details

REDIS = "# Redis\nRedis is an in-memory key-value store, mostly used for caching, sessions, and queues."
BRIN = "Indexes > Types in Postgres\n- **BRIN** — tiny indexes for huge tables whose rows are physically ordered."
PLANNER = "# Study Planner\nBackend: Scala 3 with [[ZIO]]. The classifier reached 84% test accuracy."
ZIO = "# ZIO\nUse `ZIO.attemptBlocking(...)` for blocking I/O such as JDBC calls."


# --- Real fabrications are caught ---


def test_invented_number_is_unsupported():
    answer = "According to excerpt [1], Redis listens on port 6379 by default."
    assert unsupported_details(answer, [REDIS], "What port does Redis listen on by default?") == ["6379"]


def test_invented_expansion_is_unsupported():
    answer = "BRIN in BRIN index stands for Block Range INdex [1]."
    assert unsupported_details(answer, [BRIN], "What does the BRIN in BRIN index stand for?") == ["Block Range INdex"]


# --- Correct answers are not flagged ---


@pytest.mark.parametrize(
    "answer",
    [
        "The Study Planner uses ZIO [1].",  # capitalized "The" at the start of a sentence
        "Utilizes PostgreSQL's full-text search.",  # possessive; checked against all excerpts (no citation)
        "It reached 84 percent accuracy [1].",  # 84% written differently
        "Wrap calls in `ZIO.attemptBlocking(...)` [1].",  # code copied from the note
        "Development Notes:",  # a heading the model wrote
        "It returns `effects` lazily [1].",  # plain word in backticks is emphasis, not code
        "It took 3 steps [1].",  # single-digit numbers aren't checked
    ],
)
def test_supported_or_unchecked_details_are_not_flagged(answer):
    excerpts = [PLANNER + "\nSearch uses PostgreSQL full-text search.", ZIO]
    assert unsupported_details(answer, excerpts) == []


def test_details_from_the_question_count_as_supported():
    assert unsupported_details("Nothing on 2026-09-20 [1].", [REDIS], "What happened on 2026-09-20?") == []


# --- Miscited vs unsupported ---


def test_detail_in_another_excerpt_is_miscited_not_unsupported():
    [claim] = check_grounding("Use `ZIO.attemptBlocking(...)` here [1].", [PLANNER, ZIO])
    assert claim.unsupported == []
    assert claim.miscited == ["ZIO.attemptBlocking(...)"]


def test_uncited_sentence_is_checked_against_all_excerpts():
    [claim] = check_grounding("Use `ZIO.attemptBlocking(...)`.", [PLANNER, ZIO])
    assert (claim.citations, claim.unsupported, claim.miscited) == ([], [], [])


# --- Detail extraction ---


def test_extracts_numbers_code_quotes_and_names_but_not_citations():
    details = extract_details('Set `ef_search` to 128 for "high recall" in Apache Pekko [12].')
    assert details == ["ef_search", "high recall", "Apache Pekko", "128"]


def test_long_quotes_are_skipped():
    assert extract_details('It said "avoid large, unstable updates while statistics are poor".') == []


def test_digits_inside_words_are_not_numbers():
    assert "4100" not in extract_details("my CS4100 project.")
    assert unsupported_details("My CS4100 project went well [1].", ["Notes on CS4100."]) == []
