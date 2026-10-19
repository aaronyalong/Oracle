// Pure helpers with no Obsidian imports, so they can be unit tested with `node --test`.

/** One retrieved section, as returned by the server's /api/search and /api/ask. */
export interface Hit {
  note: string; // vault-relative path, e.g. "AI/Gradient Descent.md"
  title: string;
  heading: string; // "Remedies" or "Parent > Child"; "" for text before the first heading
  text: string;
  score: number;
  via: string; // "vector", "keyword", "both"
  url: string;
}

export interface AskResult {
  text: string;
  sources: Hit[];
  cited: number[]; // 1-based source numbers the answer cites
  unsupported: string[]; // details the grounding check found in no excerpt
}

export type Segment =
  | { kind: "text"; text: string }
  | { kind: "bold"; text: string }
  | { kind: "cite"; n: number };

/** Split answer text into plain text, **bold** runs, and [n] citations that point at real sources. */
export function segments(text: string, sourceCount: number): Segment[] {
  const out: Segment[] = [];
  for (const part of text.split(/(\[\d+\]|\*\*[^*]+\*\*)/)) {
    if (!part) continue;
    const cite = part.match(/^\[(\d+)\]$/);
    if (cite && Number(cite[1]) >= 1 && Number(cite[1]) <= sourceCount) {
      out.push({ kind: "cite", n: Number(cite[1]) });
    } else if (part.length > 4 && part.startsWith("**") && part.endsWith("**")) {
      out.push({ kind: "bold", text: part.slice(2, -2) });
    } else {
      out.push({ kind: "text", text: part });
    }
  }
  return out;
}

/** Obsidian link text that opens a hit's note at its section: "AI/Gradient Descent#Learning rate". */
export function linktext(hit: Pick<Hit, "note" | "heading">): string {
  const path = hit.note.replace(/\.md$/, "");
  const section = hit.heading.split(" > ").pop()?.trim();
  return section ? `${path}#${section}` : path;
}

/** "Learning rate" -> "Gradient Descent › Learning rate"; just the title for text before any heading. */
export function label(hit: Pick<Hit, "title" | "heading">): string {
  return hit.heading ? `${hit.title} › ${hit.heading.split(" > ").join(" › ")}` : hit.title;
}
