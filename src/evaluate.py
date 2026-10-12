"""Score retrieval strategies against a set of questions with known source notes.

Usage: python src/evaluate.py --vault sample-vault [--k 1 3 5] [--save eval/results/baseline.json]

Metrics are at the note level (several chunks from one note count once), averaged over questions:
- hit@k:    did any expected note appear in the top k?
- recall@k: what fraction of the expected notes appeared in the top k?
- MRR:      mean of 1 / rank of the first expected note (0 if none appeared)
- evidence: what fraction of the question's evidence phrases appear in the retrieved chunk text?
            This checks the right *section* was found, and doesn't depend on how notes are chunked.
"""

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

import ollama

from index import DEFAULT_DB, EMBED_MODEL, get_collection, ollama_embedder
from ingest import Note, load_vault
from retrieve import Hit, Retriever, graph_retriever, vector_retriever

DEFAULT_QUESTIONS = Path("eval/questions.json")


def build_strategies(collection, embed, notes: dict[str, Note]) -> dict[str, Retriever]:
    """Every strategy to compare. Graph variants differ in seed count and how much linked notes are favoured."""
    strategies: dict[str, Retriever] = {"vector": vector_retriever(collection, embed)}
    for links in ("note", "chunk", "chunk+back"):
        for seeds in (1, 2):
            for boost in (0.05, 1.0):
                name = f"{links}-s{seeds}-b{boost:g}"
                strategies[name] = graph_retriever(collection, embed, notes, seeds, boost, links)
    return strategies


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    expected: list[str]  # note keys that contain the answer
    type: str  # direct, paraphrase, alias, multi-hop
    evidence: list[str] = field(default_factory=list)  # phrases from the expected notes that answer it


@dataclass
class QuestionResult:
    id: str
    type: str
    expected: list[str]
    retrieved: list[str]  # note keys in rank order, deduplicated
    hit: bool
    recall: float
    reciprocal_rank: float
    evidence: float  # fraction of evidence phrases found in retrieved chunks


def load_questions(path: Path, notes: dict[str, Note]) -> list[Question]:
    questions = [Question(**q) for q in json.loads(path.read_text(encoding="utf-8"))]
    # Catch typos, renamed notes, and edited text, which would otherwise silently score as misses.
    for q in questions:
        missing = set(q.expected) - set(notes)
        if missing:
            raise ValueError(f"Question {q.id!r} expects notes that aren't in the vault: {sorted(missing)}")
        for phrase in q.evidence:
            if not any(phrase.lower() in notes[key].body.lower() for key in q.expected):
                raise ValueError(f"Question {q.id!r}: evidence {phrase!r} isn't in any of its expected notes")
    return questions


def rank_notes(hits: list[Hit]) -> list[str]:
    """Note keys in order of their best-ranked chunk."""
    return list(dict.fromkeys(hit.note_key for hit in hits))


def score(question: Question, hits: list[Hit]) -> QuestionResult:
    retrieved = rank_notes(hits)
    found = [note for note in retrieved if note in question.expected]
    first_rank = next((i for i, note in enumerate(retrieved, 1) if note in question.expected), None)
    retrieved_text = "\n".join(hit.text for hit in hits).lower()
    evidence_found = sum(phrase.lower() in retrieved_text for phrase in question.evidence)
    return QuestionResult(
        id=question.id,
        type=question.type,
        expected=question.expected,
        retrieved=retrieved,
        hit=bool(found),
        recall=len(found) / len(question.expected),
        reciprocal_rank=1 / first_rank if first_rank else 0.0,
        evidence=evidence_found / len(question.evidence) if question.evidence else float(bool(found)),
    )


def summarize(results: list[QuestionResult]) -> dict[str, float]:
    n = len(results)
    return {
        "hit": sum(r.hit for r in results) / n,
        "recall": sum(r.recall for r in results) / n,
        "mrr": sum(r.reciprocal_rank for r in results) / n,
        "evidence": sum(r.evidence for r in results) / n,
    }


def evaluate(retrieve: Retriever, questions: list[Question], k: int) -> list[QuestionResult]:
    return [score(q, retrieve(q.question, k)) for q in questions]


def _format(s: dict[str, float]) -> str:
    return f"hit {s['hit']:.2f} | recall {s['recall']:.2f} | MRR {s['mrr']:.2f} | evidence {s['evidence']:.2f}"


def _print_report(strategy: str, k: int, results: list[QuestionResult], show_misses: bool, by_type: bool) -> None:
    print(f"{strategy:<18} k={k}  {_format(summarize(results))}")
    if by_type:
        groups = defaultdict(list)
        for r in results:
            groups[r.type].append(r)
        for qtype, group in groups.items():
            print(f"  {qtype:<11} (n={len(group):>2})  {_format(summarize(group))}")
    if show_misses:
        for r in results:
            if r.recall < 1 or r.evidence < 1:
                missing = [e for e in r.expected if e not in r.retrieved]
                print(f"  miss: {r.id} — notes missing {missing}, evidence {r.evidence:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval against eval/questions.json.")
    parser.add_argument("--vault", required=True, help="vault the questions are about (used to check note names)")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--embed-model", default=EMBED_MODEL)
    parser.add_argument("--k", type=int, nargs="+", default=[1, 3, 5], help="cutoffs to report")
    parser.add_argument("--save", type=Path, help="write per-question results as JSON")
    parser.add_argument("--misses", action="store_true", help="list every question that wasn't fully answered")
    parser.add_argument("--strategies", nargs="+", help="only run these strategies (default: all)")
    parser.add_argument("--by-type", action="store_true", help="break results down by question type")
    args = parser.parse_args()

    try:
        notes = load_vault(args.vault).notes
        questions = load_questions(args.questions, notes)
        collection = get_collection(args.db, args.embed_model)
        strategies = build_strategies(collection, ollama_embedder(args.embed_model), notes)
        if args.strategies:
            unknown = set(args.strategies) - set(strategies)
            if unknown:
                raise ValueError(f"Unknown strategies {sorted(unknown)}; choose from {list(strategies)}")
            strategies = {name: strategies[name] for name in args.strategies}

        report = {"questions": str(args.questions), "embed_model": args.embed_model, "runs": []}
        for k in args.k:
            print()
            for name, retrieve in strategies.items():
                results = evaluate(retrieve, questions, k)
                _print_report(name, k, results, args.misses, args.by_type)
                report["runs"].append(
                    {"strategy": name, "k": k, "summary": summarize(results), "results": [asdict(r) for r in results]}
                )
    except ValueError as e:
        sys.exit(str(e))
    except ConnectionError:
        sys.exit("Can't reach Ollama. Start it with `ollama serve` (or the Ollama app) and try again.")
    except ollama.ResponseError as e:
        sys.exit(f"Ollama error: {e.error}")

    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nSaved to {args.save}")


if __name__ == "__main__":
    main()
