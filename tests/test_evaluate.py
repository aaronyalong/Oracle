import json
from pathlib import Path

import pytest

from evaluate import Question, evaluate, load_questions, rank_notes, score, summarize
from ingest import load_vault
from retrieve import Hit

ROOT = Path(__file__).parent.parent


def hits_for(*note_keys: str) -> list[Hit]:
    return [Hit(f"{key}::{i}", key, key, "", "text", 0.5) for i, key in enumerate(note_keys)]


def question(*expected: str) -> Question:
    return Question("q", "?", list(expected), "direct")


def test_rank_notes_dedupes_keeping_best_rank():
    assert rank_notes(hits_for("A.md", "B.md", "A.md", "C.md")) == ["A.md", "B.md", "C.md"]


def test_score_first_place_hit():
    r = score(question("A.md"), hits_for("A.md", "B.md"))
    assert (r.hit, r.recall, r.reciprocal_rank) == (True, 1.0, 1.0)


def test_score_rank_uses_notes_not_chunks():
    # Two chunks of B come first, but B is one note, so A is note #2.
    r = score(question("A.md"), hits_for("B.md", "B.md", "A.md"))
    assert r.reciprocal_rank == 0.5


def test_score_partial_recall_for_multi_note_questions():
    r = score(question("A.md", "B.md"), hits_for("C.md", "B.md"))
    assert (r.hit, r.recall, r.reciprocal_rank) == (True, 0.5, 0.5)


def test_score_miss():
    r = score(question("A.md"), hits_for("B.md", "C.md"))
    assert (r.hit, r.recall, r.reciprocal_rank) == (False, 0.0, 0.0)


def test_summarize_averages():
    results = [score(question("A.md"), hits_for("A.md")), score(question("A.md"), hits_for("B.md"))]
    assert summarize(results) == {"hit": 0.5, "recall": 0.5, "mrr": 0.5}


def test_evaluate_passes_k_to_retriever():
    seen = []

    def retrieve(q, k):
        seen.append(k)
        return hits_for("A.md")

    evaluate(retrieve, [question("A.md")], k=3)
    assert seen == [3]


def test_load_questions_rejects_unknown_notes(tmp_path):
    path = tmp_path / "q.json"
    path.write_text(json.dumps([{"id": "x", "question": "?", "expected": ["Nope.md"], "type": "direct"}]))
    with pytest.raises(ValueError, match="Nope.md"):
        load_questions(path, {"A.md"})


def test_sample_question_set_matches_sample_vault():
    notes = set(load_vault(ROOT / "sample-vault").notes)
    questions = load_questions(ROOT / "eval" / "questions.json", notes)
    assert len(questions) >= 10
    assert len({q.id for q in questions}) == len(questions)
