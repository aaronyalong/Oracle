import json
from pathlib import Path

import pytest

from evaluate import Question, evaluate, load_questions, rank_notes, score, summarize
from ingest import Note, load_vault
from retrieve import Hit

ROOT = Path(__file__).parent.parent


def hits_for(*note_keys: str, texts: tuple[str, ...] = ()) -> list[Hit]:
    texts = texts or ("text",) * len(note_keys)
    return [Hit(f"{key}::{i}", key, key, "", text, 0.5) for i, (key, text) in enumerate(zip(note_keys, texts))]


def question(*expected: str, evidence: tuple[str, ...] = ()) -> Question:
    return Question("q", "?", list(expected), "direct", list(evidence))


def note(key: str, body: str) -> Note:
    return Note(Path(key), key, body, {}, set(), [], [])


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


def test_evidence_is_matched_in_chunk_text_case_insensitively():
    q = question("A.md", evidence=("learning rate 0.001", "Adam"))
    r = score(q, hits_for("A.md", "B.md", texts=("The Learning Rate 0.001 worked", "unrelated")))
    assert r.evidence == 0.5


def test_evidence_counts_even_from_an_unexpected_note():
    # The right section can live in a different note than expected; evidence still credits it.
    r = score(question("A.md", evidence=("GIN index",)), hits_for("B.md", texts=("Create a GIN index",)))
    assert (r.hit, r.evidence) == (False, 1.0)


def test_without_evidence_falls_back_to_note_hit():
    assert score(question("A.md"), hits_for("A.md")).evidence == 1.0
    assert score(question("A.md"), hits_for("B.md")).evidence == 0.0


def test_summarize_averages():
    results = [score(question("A.md"), hits_for("A.md")), score(question("A.md"), hits_for("B.md"))]
    assert summarize(results) == {"hit": 0.5, "recall": 0.5, "mrr": 0.5, "evidence": 0.5}


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
        load_questions(path, {"A.md": note("A.md", "body")})


def test_load_questions_rejects_evidence_not_in_expected_notes(tmp_path):
    path = tmp_path / "q.json"
    q = {"id": "x", "question": "?", "expected": ["A.md"], "evidence": ["only in B"], "type": "direct"}
    path.write_text(json.dumps([q]))
    with pytest.raises(ValueError, match="only in B"):
        load_questions(path, {"A.md": note("A.md", "text of A"), "B.md": note("B.md", "only in B")})


def test_sample_question_set_matches_sample_vault():
    notes = load_vault(ROOT / "sample-vault").notes
    questions = load_questions(ROOT / "eval" / "questions.json", notes)
    assert len(questions) >= 30
    assert all(q.evidence for q in questions)
    assert len({q.id for q in questions}) == len(questions)
