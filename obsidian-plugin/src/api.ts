// Client for the Oracle server (src/server.py). JSON calls use Obsidian's requestUrl; the streamed
// answer uses the browser's EventSource, which reads Server-Sent Events as they arrive.
import { requestUrl } from "obsidian";
import type { AskResult, Hit } from "./format.ts";

export interface Health {
  ok: boolean;
  vault: string;
  chunks: number;
  embed_model: string;
  llm_model: string;
}

export interface ReindexResult {
  updated: number;
  unchanged: number;
  removed: number;
  chunks: number;
}

export interface AskHandlers {
  onToken: (piece: string) => void;
  onDone: (result: AskResult) => void;
  onError: () => void;
}

export class OracleClient {
  constructor(private readonly baseUrl: () => string) {}

  private url(path: string, params: Record<string, string | number> = {}): string {
    const query = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]));
    const base = this.baseUrl().replace(/\/+$/, "");
    return `${base}${path}${query.size ? `?${query}` : ""}`;
  }

  async health(): Promise<Health> {
    return (await requestUrl({ url: this.url("/api/health") })).json;
  }

  async search(q: string, k = 10): Promise<Hit[]> {
    return (await requestUrl({ url: this.url("/api/search", { q, k }) })).json.results;
  }

  async reindex(): Promise<ReindexResult> {
    return (await requestUrl({ url: this.url("/api/index"), method: "POST" })).json;
  }

  /** Stream an answer. Returns a function that cancels the stream. */
  ask(q: string, handlers: AskHandlers): () => void {
    const source = new EventSource(this.url("/api/ask", { q }));
    let finished = false;
    source.addEventListener("token", (e) => handlers.onToken(JSON.parse((e as MessageEvent).data)));
    source.addEventListener("done", (e) => {
      finished = true;
      source.close();
      handlers.onDone(JSON.parse((e as MessageEvent).data));
    });
    // EventSource reconnects on its own after an error; for a one-shot answer, stop instead.
    source.onerror = () => {
      if (finished) return;
      finished = true;
      source.close();
      handlers.onError();
    };
    return () => {
      finished = true;
      source.close();
    };
  }
}
