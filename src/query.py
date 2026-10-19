"""Answer a question from your notes, with sources.

Usage: python src/query.py "what learning rate worked best?" [--k 5] [--show-context]
"""

import argparse
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import ollama

from index import DEFAULT_DB, EMBED_MODEL, get_collection, ollama_embedder
from retrieve import Hit, Retriever, vector_retriever

LLM_MODEL = "llama3.2"
DEFAULT_K = 5

REFUSAL = "I couldn't find that in your notes."

# Versioned so answer quality can be compared across prompts (see src/evaluate_answers.py).
PROMPTS = {
    "v1": f"""You answer questions using only the user's notes, which are given as numbered excerpts.
- Base every statement on the excerpts. Do not use outside knowledge.
- Cite the excerpts you used with their numbers in square brackets, e.g. [2] or [1][3].
- If the excerpts don't contain the answer, say "{REFUSAL}" and stop.
- Be concise.""",
    # v2 targets v1's failures: answering only part of a question, and not combining excerpts.
    "v2": f"""You answer questions using only the user's notes, which are given as numbered excerpts.
- Base every statement on the excerpts. Do not use outside knowledge, even if you know the answer.
- Answer every part of the question. If it asks two things, answer both.
- The answer may be spread across excerpts: one may name something and another explain it. Combine them.
- If the question is a broad topic rather than a question, summarize what the excerpts say about it.
- Cite the excerpts you used with their numbers in square brackets, e.g. [2] or [1][3].
- If the excerpts don't contain the answer, say "{REFUSAL}" and stop.
- Be concise.""",
    # v3 keeps v1's strictness (v2 led to uncited answers and a fabricated citation) and adds what
    # real notes needed: superseded plans, and citations on every fact in longer answers.
    "v3": f"""You answer questions using only the user's notes, which are given as numbered excerpts.
- Base every statement on the excerpts. Do not use outside knowledge, even if you know the answer.
- Cite every fact with the number of its excerpt in square brackets, e.g. [2] or [1][3].
- If excerpts disagree, trust the one that is newer or not marked as superseded, outdated, or wrong, and say that the earlier plan changed.
- If the excerpts don't contain the answer, say "{REFUSAL}" and stop.
- Be concise.""",
}
DEFAULT_PROMPT = "v1"
SYSTEM_PROMPT = PROMPTS[DEFAULT_PROMPT]

NO_RESULTS = "I couldn't find anything in your notes. Has the vault been indexed? Run src/index.py first."

GenerateFn = Callable[[str, str], str]  # (system prompt, user prompt) -> answer text

# Short inputs like "Kafka" are topics, not questions; strict prompts make models refuse them.
MAX_TOPIC_WORDS = 4
QUESTION_WORDS = {
    "what", "how", "why", "who", "when", "where", "which", "is", "are", "was", "were", "do", "does", "did",
    "can", "could", "should", "would", "will", "list", "compare", "explain", "summarize", "describe", "find",
}
# "tell me everything about X", "tell me about X", "everything about X", "all about X"
EVERYTHING_ABOUT_RE = re.compile(
    r"^(?:please\s+)?(?:(?:tell|give|show) me\s+)?(?:everything\s+|all\s+)?about\s+(.+?)[.!?]*$", re.IGNORECASE
)


@dataclass
class Answer:
    text: str
    sources: list[Hit]  # in the order they were numbered in the prompt

    @property
    def cited(self) -> list[int]:
        """1-based source numbers the answer actually cites, ignoring numbers that don't exist."""
        numbers = {int(n) for n in re.findall(r"\[(\d+)\]", self.text)}
        return sorted(n for n in numbers if 1 <= n <= len(self.sources))


def rewrite_query(question: str) -> str:
    """Turn topic-style input into an explicit request; real questions are returned unchanged.

    "Kafka" -> "Summarize what my notes say about Kafka."
    "tell me everything about Scala" -> "Summarize everything my notes say about Scala."
    """
    q = question.strip()
    if match := EVERYTHING_ABOUT_RE.match(q):
        return f"Summarize everything my notes say about {match.group(1).strip()}."
    words = q.rstrip(".!").split()
    if 0 < len(words) <= MAX_TOPIC_WORDS and "?" not in q and words[0].lower() not in QUESTION_WORDS:
        return f"Summarize what my notes say about {q.rstrip('.!')}."
    return question


def _drop_trailing_refusal(text: str, hits: list[Hit]) -> str:
    """Models sometimes answer with citations, then append the refusal sentence anyway; remove it."""
    if REFUSAL not in text or text.strip() == REFUSAL:
        return text
    cleaned = text.replace(REFUSAL, "").strip()
    return cleaned if Answer(cleaned, hits).cited else text


def build_prompt(question: str, hits: list[Hit]) -> str:
    excerpts = "\n\n".join(f"[{i}] (from {hit.note_key})\n{hit.text}" for i, hit in enumerate(hits, 1))
    return f"Notes:\n\n{excerpts}\n\nQuestion: {question}"


def ollama_generator(model: str = LLM_MODEL) -> GenerateFn:
    def generate(system: str, prompt: str) -> str:
        response = ollama.chat(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            options={"temperature": 0},  # repeatable answers, which matters for evaluation
        )
        return response.message.content

    return generate


def answer(
    question: str,
    retrieve: Retriever,
    generate: GenerateFn,
    k: int = DEFAULT_K,
    system: str = SYSTEM_PROMPT,
    rewrite: bool = True,
) -> Answer:
    # Search with the user's own words; the rewrite only changes what the LLM is asked.
    hits = retrieve(question, k)
    if not hits:
        return Answer(NO_RESULTS, [])
    asked = rewrite_query(question) if rewrite else question
    text = generate(system, build_prompt(asked, hits)).strip()
    return Answer(_drop_trailing_refusal(text, hits), hits)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask a question about your notes.")
    parser.add_argument("question")
    parser.add_argument("--k", type=int, default=DEFAULT_K, help="number of chunks to retrieve")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="index location")
    parser.add_argument("--embed-model", default=EMBED_MODEL)
    parser.add_argument("--model", default=LLM_MODEL, help="Ollama model that writes the answer")
    parser.add_argument("--prompt", choices=PROMPTS, default=DEFAULT_PROMPT, help="system prompt version")
    parser.add_argument("--show-context", action="store_true", help="print the retrieved excerpts")
    args = parser.parse_args()

    try:
        collection = get_collection(args.db, args.embed_model)
        retrieve = vector_retriever(collection, ollama_embedder(args.embed_model))
        result = answer(args.question, retrieve, ollama_generator(args.model), args.k, PROMPTS[args.prompt])
    except ValueError as e:
        sys.exit(str(e))
    except ConnectionError:
        sys.exit("Can't reach Ollama. Start it with `ollama serve` (or the Ollama app) and try again.")
    except ollama.ResponseError as e:
        sys.exit(f"Ollama error: {e.error}. Did you `ollama pull` the model?")

    print(result.text)
    if args.show_context:
        print(f"\n{build_prompt(args.question, result.sources)}")
    if result.sources:
        print("\nSources:")
        cited = set(result.cited)
        for i, hit in enumerate(result.sources, 1):
            marker = "*" if i in cited else " "
            location = f"{hit.note_key} > {hit.heading}" if hit.heading else hit.note_key
            print(f" {marker}[{i}] {location}  ({hit.score:.2f})")
        print("  (* = cited in the answer)")


if __name__ == "__main__":
    main()
