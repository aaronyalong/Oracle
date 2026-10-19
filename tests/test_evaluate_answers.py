"""Answer-quality grading tests with fake retrieval and generation, so they run without Ollama."""

import json
from pathlib import Path

import pytest

from evaluate_answers import AnswerQuestion, grade, is_refusal, load_answer_questions, run, summarize_answers
from query import Answer
from retrieve import Hit

ROOT = Path(__file__).parent.parent


def hit(n: int, text: str = "text") -> Hit:
    return Hit(f"N.md::{n}", "N.md", "N", "Section", text, 0.9)


def q(kind: str = "answerable", facts=None, forbidden=None) -> AnswerQuestion:
    return AnswerQuestion("q", "?", kind, facts or [], forbidden or [])


@pytest.mark.parametrize(
    "text",
    [
        "I couldn't find that in your notes.",
        "I could not find anything about that.",
        "Your notes don't mention a favorite pizza.",
        "The excerpts do not contain this information.",
        "There is no information about GPUs.",
        "The midterm grade is not explicitly stated.",
        "Her manager isn't mentioned.",
    ],
)
def test_refusals_are_detected(text):
    assert is_refusal(text)


def test_normal_answer_is_not_a_refusal():
    assert not is_refusal("A learning rate of 0.001 with Adam worked best [1].")


def test_facts_accept_any_spelling_case_insensitively():
    result = grade(q(facts=[["0.001", "1e-3"], ["Adam"]]), Answer("Use 1E-3 with adam [1].", [hit(1)]), 1.0)
    assert result.facts_found == 1.0
    assert not result.refused


def test_partial_facts():
    result = grade(q(facts=[["0.001"], ["Adam"]]), Answer("It was 0.001.", [hit(1)]), 1.0)
    assert result.facts_found == 0.5


def test_refusal_with_the_facts_anyway_is_not_a_wrong_refusal():
    text = "Your notes don't mention the year, but the rate was 0.001 [1]."
    assert not grade(q(facts=[["0.001"]]), Answer(text, [hit(1)]), 1.0).refused


def test_refusal_without_facts_is_a_wrong_refusal():
    assert grade(q(facts=[["0.001"]]), Answer("I couldn't find that in your notes.", [hit(1)]), 1.0).refused


def test_topic_summary_with_a_caveat_is_not_a_refusal():
    text = "SQLite is embedded [1]. I couldn't find general characteristics of databases."
    assert not grade(q("topic"), Answer(text, [hit(1)]), 1.0).refused
    assert grade(q("topic"), Answer("I couldn't find that in your notes.", [hit(1)]), 1.0).refused


def test_long_uncited_topic_summary_is_not_a_refusal():
    text = "Scala has Futures, Cats Effect, ZIO, and Akka. " * 5 + "Your notes don't mention Loom."
    result = grade(q("topic"), Answer(text, [hit(1)]), 1.0)
    assert (result.refused, result.cited) == (False, [])


def test_unanswerable_refused_is_not_made_up():
    result = grade(q("unanswerable"), Answer("I couldn't find that in your notes.", [hit(1)]), 1.0)
    assert (result.refused, result.made_up) == (True, False)


def test_unanswerable_answered_is_made_up():
    assert grade(q("unanswerable"), Answer("Pepperoni [1].", [hit(1)]), 1.0).made_up


def test_forbidden_outside_knowledge_counts_as_made_up_even_with_a_refusal():
    text = "Your notes don't mention it, but Redis uses port 6379."
    assert grade(q("unanswerable", forbidden=["6379"]), Answer(text, [hit(1)]), 1.0).made_up


def test_citation_supported_when_a_cited_excerpt_contains_a_fact():
    sources = [hit(1, "unrelated"), hit(2, "rate of 0.001 with Adam")]
    assert grade(q(facts=[["0.001"]]), Answer("0.001 [2].", sources), 1.0).citation_supported is True
    assert grade(q(facts=[["0.001"]]), Answer("0.001 [1].", sources), 1.0).citation_supported is False
    assert grade(q(facts=[["0.001"]]), Answer("0.001.", sources), 1.0).citation_supported is None


def test_summary_by_kind():
    results = [
        grade(q(facts=[["zebra"]]), Answer("zebra [1]", [hit(1, "zebra")]), 2.0),
        grade(q(facts=[["zebra"]]), Answer("I couldn't find that in your notes.", [hit(1)]), 2.0),
        grade(q("topic"), Answer("Summary [1].", [hit(1)]), 2.0),
        grade(q("unanswerable"), Answer("I couldn't find that in your notes.", [hit(1)]), 2.0),
        grade(q("unanswerable"), Answer("Pepperoni.", [hit(1)]), 2.0),
    ]
    s = summarize_answers(results)
    assert s["answerable"]["facts"] == 0.5
    assert s["answerable"]["wrong_refusals"] == 0.5
    assert s["answerable"]["citations_supported"] == 1.0
    assert s["topic"] == {"n": 1, "wrong_refusals": 0.0, "cited": 1.0, "flagged": 0.0}
    assert s["unanswerable"]["made_up"] == 0.5
    assert s["overall"]["avg_seconds"] == 2.0


def test_run_passes_k_and_prompt_and_reports_progress():
    seen, progress = [], []

    def retrieve(question, k):
        seen.append(k)
        return [hit(1, "a")]

    def generate(system, prompt):
        seen.append(system)
        return "a [1]"

    results = run([q(facts=[["a"]])], retrieve, generate, k=3, system="SYS", on_result=lambda i, n, r: progress.append((i, n)))
    assert seen == [3, "SYS"]
    assert progress == [(1, 1)]
    assert results[0].facts_found == 1.0


def test_load_rejects_answerable_without_facts(tmp_path):
    path = tmp_path / "a.json"
    path.write_text(json.dumps([{"id": "x", "question": "?", "kind": "answerable"}]))
    with pytest.raises(ValueError, match="needs at least one fact"):
        load_answer_questions(path)


@pytest.mark.parametrize("name", ["answers.json", "answers-holdout.json"])
def test_sample_answer_sets_load_and_cover_every_kind(name):
    questions = load_answer_questions(ROOT / "eval" / name)
    assert {q.kind for q in questions} == {"answerable", "topic", "unanswerable"}


def test_superseded_plan_presented_as_current_is_outdated():
    question = q(facts=[["push notification"]], forbidden=["email"])
    assert grade(question, Answer("Reminders are sent by email [1].", [hit(1)]), 1.0).outdated is True


def test_superseded_plan_mentioned_as_history_is_not_outdated():
    question = q(facts=[["push notification"]], forbidden=["email"])
    text = "Reminders were originally emailed, but are now push notifications [1]."
    result = grade(question, Answer(text, [hit(1)]), 1.0)
    assert (result.outdated, result.facts_found) == (False, 1.0)


def test_outdated_is_none_without_forbidden_details():
    assert grade(q(facts=[["x"]]), Answer("x [1]", [hit(1)]), 1.0).outdated is None
