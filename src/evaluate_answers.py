"""Score answer quality: correct facts, wrong refusals, made-up answers, and citation accuracy.

Usage: python src/evaluate_answers.py [--questions eval/answers.json] [--model llama3.2] [--prompt v1] [--k 5]

Question kinds:
- answerable:   the notes contain the answer. `facts` lists what a correct answer must mention; each fact
                is a list of acceptable spellings, matched case-insensitively.
- topic:        a broad subject the notes cover. The answer should summarize, not refuse.
- unanswerable: the notes don't say. The answer should refuse rather than guess. `forbidden` lists
                outside-knowledge answers (e.g. a real default port) that count as made up even
                when the answer also says the notes don't mention it.

On answerable questions, `forbidden` lists details of a superseded plan: mentioning them counts as
*outdated* unless the answer also says the plan changed.
"""

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import ollama

from index import DEFAULT_DB, EMBED_MODEL, get_collection, ollama_embedder
from query import DEFAULT_K, DEFAULT_PROMPT, LLM_MODEL, PROMPTS, Answer, GenerateFn, answer, ollama_generator
from retrieve import Retriever, vector_retriever

DEFAULT_QUESTIONS = Path("eval/answers.json")
TOPIC_REFUSAL_MAX_CHARS = 200
# Words showing an answer presents old information as old ("originally emailed, now pushed").
CHANGE_MARKERS = ("supersed", "original", "previous", "earlier", "initial", "first plan", "no longer", "dropped", "replaced", "changed", "instead", "used to")
KINDS = ("answerable", "topic", "unanswerable")

# The prompt asks for an exact refusal sentence, but models paraphrase it, so match the common forms.
REFUSAL_RE = re.compile(
    r"couldn['’]t find|could not find|can['’]t find|cannot find|"
    r"(?:notes|excerpts|context) (?:do not|don['’]t|does not|doesn['’]t) (?:mention|contain|say|include|provide|specify)|"
    r"no (?:information|mention) (?:about|of|on)|"
    r"(?:is|are) not (?:explicitly )?(?:stated|mentioned|specified|given)|"
    r"(?:isn['’]t|aren['’]t) (?:explicitly )?(?:stated|mentioned|specified|given)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AnswerQuestion:
    id: str
    question: str
    kind: str
    facts: list[list[str]] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)


@dataclass
class AnswerResult:
    id: str
    kind: str
    question: str
    answer: str
    refused: bool
    facts_found: float | None  # fraction of facts mentioned; None for questions without facts
    made_up: bool | None  # unanswerable questions only: answered anyway, or used forbidden outside knowledge
    outdated: bool | None  # answerable questions with `forbidden`: presented a superseded plan as current
    cited: list[int]
    citation_supported: bool | None  # does a cited excerpt contain a fact? None without facts or citations
    sources: list[str]  # "note > heading" for each excerpt, in prompt order
    seconds: float


def load_answer_questions(path: Path) -> list[AnswerQuestion]:
    questions = [AnswerQuestion(**q) for q in json.loads(path.read_text(encoding="utf-8"))]
    for q in questions:
        if q.kind not in KINDS:
            raise ValueError(f"Question {q.id!r} has kind {q.kind!r}; expected one of {KINDS}")
        if q.kind == "answerable" and not q.facts:
            raise ValueError(f"Answerable question {q.id!r} needs at least one fact")
    if len({q.id for q in questions}) != len(questions):
        raise ValueError(f"Duplicate question ids in {path}")
    return questions


def is_refusal(text: str) -> bool:
    return bool(REFUSAL_RE.search(text))


def _mentions(text: str, alternatives: list[str]) -> bool:
    lowered = text.lower()
    return any(alt.lower() in lowered for alt in alternatives)


def grade(question: AnswerQuestion, result: Answer, seconds: float) -> AnswerResult:
    facts_found = None
    if question.facts:
        facts_found = sum(_mentions(result.text, alts) for alts in question.facts) / len(question.facts)
    # "Your notes don't say X, but they do say Y" is a partial answer, not a refusal: for answerable
    # questions when Y contains the facts, for topics when the answer cites excerpts.
    refused = is_refusal(result.text)
    if question.kind == "answerable":
        refused = refused and not facts_found
    elif question.kind == "topic":
        # A long summary that forgot [n] citations is "uncited", not a refusal.
        refused = refused and not result.cited and len(result.text) < TOPIC_REFUSAL_MAX_CHARS

    made_up = outdated = None
    if question.kind == "unanswerable":
        made_up = not refused or _mentions(result.text, question.forbidden)
    elif question.kind == "answerable" and question.forbidden:
        outdated = _mentions(result.text, question.forbidden) and not _mentions(result.text, list(CHANGE_MARKERS))

    cited = result.cited
    citation_supported = None
    if question.facts and cited:
        cited_text = "\n".join(result.sources[n - 1].text for n in cited)
        citation_supported = any(_mentions(cited_text, alts) for alts in question.facts)

    return AnswerResult(
        id=question.id,
        kind=question.kind,
        question=question.question,
        answer=result.text,
        refused=refused,
        facts_found=facts_found,
        made_up=made_up,
        outdated=outdated,
        cited=cited,
        citation_supported=citation_supported,
        sources=[f"{h.note_key} > {h.heading}" if h.heading else h.note_key for h in result.sources],
        seconds=round(seconds, 2),
    )


def _share(values: list[bool]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize_answers(results: list[AnswerResult]) -> dict[str, dict[str, float | None]]:
    by_kind = {kind: [r for r in results if r.kind == kind] for kind in KINDS}
    answerable, topic, unanswerable = by_kind["answerable"], by_kind["topic"], by_kind["unanswerable"]
    return {
        "answerable": {
            "n": len(answerable),
            "facts": _share([r.facts_found for r in answerable]),
            "fully_correct": _share([r.facts_found == 1 for r in answerable]),
            "wrong_refusals": _share([r.refused for r in answerable]),
            "citations_supported": _share([r.citation_supported for r in answerable if r.citation_supported is not None]),
            "outdated": _share([r.outdated for r in answerable if r.outdated is not None]),
        },
        "topic": {
            "n": len(topic),
            "wrong_refusals": _share([r.refused for r in topic]),
            "cited": _share([bool(r.cited) for r in topic]),
        },
        "unanswerable": {
            "n": len(unanswerable),
            "correct_refusals": _share([not r.made_up for r in unanswerable]),
            "made_up": _share([r.made_up for r in unanswerable]),
        },
        "overall": {"n": len(results), "avg_seconds": _share([r.seconds for r in results])},
    }


def run(
    questions: list[AnswerQuestion],
    retrieve: Retriever,
    generate: GenerateFn,
    k: int,
    system: str,
    on_result=None,
    rewrite: bool = True,
) -> list[AnswerResult]:
    results = []
    for q in questions:
        start = time.perf_counter()
        result = answer(q.question, retrieve, generate, k, system, rewrite)
        graded = grade(q, result, time.perf_counter() - start)
        results.append(graded)
        if on_result:
            on_result(len(results), len(questions), graded)
    return results


def _status(r: AnswerResult) -> str:
    if r.kind == "unanswerable":
        return "MADE UP" if r.made_up else "refused (correct)"
    if r.refused:
        return "WRONG REFUSAL"
    if r.outdated:
        return "OUTDATED"
    if r.kind == "topic":
        return "answered" + ("" if r.cited else " (no citations)")
    return f"facts {r.facts_found:.0%}" + ("" if r.cited else " (no citations)")


def _fmt(value: float | None) -> str:
    return "  -  " if value is None else f"{value:.2f}"


def _print_summary(summary: dict) -> None:
    a, t, u = summary["answerable"], summary["topic"], summary["unanswerable"]
    print(f"\nanswerable   (n={a['n']:>2})  facts {_fmt(a['facts'])} | fully correct {_fmt(a['fully_correct'])} | "
          f"wrong refusals {_fmt(a['wrong_refusals'])} | citations supported {_fmt(a['citations_supported'])} | "
          f"outdated {_fmt(a['outdated'])}")
    print(f"topic        (n={t['n']:>2})  wrong refusals {_fmt(t['wrong_refusals'])} | cited {_fmt(t['cited'])}")
    print(f"unanswerable (n={u['n']:>2})  correct refusals {_fmt(u['correct_refusals'])} | made up {_fmt(u['made_up'])}")
    print(f"average {summary['overall']['avg_seconds']:.1f}s per answer")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate answer quality against eval/answers.json.")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--embed-model", default=EMBED_MODEL)
    parser.add_argument("--model", default=LLM_MODEL, help="Ollama model that writes the answers")
    parser.add_argument("--prompt", choices=PROMPTS, default=DEFAULT_PROMPT, help="system prompt version")
    parser.add_argument("--k", type=int, default=DEFAULT_K, help="chunks given to the model")
    parser.add_argument("--no-rewrite", action="store_true", help="don't rewrite topic-style questions")
    parser.add_argument("--limit", type=int, help="only run the first N questions (quick checks)")
    parser.add_argument("--show", action="store_true", help="print every answer")
    parser.add_argument("--save", type=Path, help="write per-question results as JSON")
    args = parser.parse_args()

    def progress(i: int, n: int, r: AnswerResult) -> None:
        print(f"[{i:>2}/{n}] {r.id:<24} {_status(r):<26} {r.seconds:>5.1f}s")
        if args.show:
            print(f"        {r.answer}\n")

    try:
        questions = load_answer_questions(args.questions)[: args.limit]
        collection = get_collection(args.db, args.embed_model)
        retrieve = vector_retriever(collection, ollama_embedder(args.embed_model))
        rewrite = not args.no_rewrite
        print(f"{len(questions)} questions | model {args.model} | prompt {args.prompt} | k={args.k} | rewrite {rewrite}\n")
        results = run(questions, retrieve, ollama_generator(args.model), args.k, PROMPTS[args.prompt], progress, rewrite)
    except ValueError as e:
        sys.exit(str(e))
    except ConnectionError:
        sys.exit("Can't reach Ollama. Start it with `ollama serve` (or the Ollama app) and try again.")
    except ollama.ResponseError as e:
        sys.exit(f"Ollama error: {e.error}. Did you `ollama pull {args.model}`?")

    summary = summarize_answers(results)
    _print_summary(summary)
    if args.save:
        config = {
            "questions": str(args.questions), "model": args.model, "prompt": args.prompt, "k": args.k, "rewrite": rewrite,
        }
        report = {"config": config, "summary": summary, "results": [asdict(r) for r in results]}
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Saved to {args.save}")


if __name__ == "__main__":
    main()
