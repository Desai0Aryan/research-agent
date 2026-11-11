import { SSEParser } from "./sse";
import type {
  AgentEvent, Doc, EvalRun, EvalRunMeta, EvalSet, Expansion, ProdFailures, ResearchResult, RunSummary,
} from "./types";

export const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const KEY = process.env.NEXT_PUBLIC_API_KEY;
const authHeaders = (): Record<string, string> => (KEY ? { "X-API-Key": KEY } : {});

async function explain(r: Response): Promise<string> {
  if (r.status === 401) return "401: The API requires a valid key (set NEXT_PUBLIC_API_KEY for the web app).";
  if (r.status === 429) return `429: Rate limit reached. Try again in ${r.headers.get("Retry-After") ?? "a few"} seconds.`;
  let detail = r.statusText;
  try { const j = await r.json(); detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j); } catch { /* ignore */ }
  return `${r.status}: ${detail}`;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const json = init?.body && !(init.body instanceof FormData);
  const r = await fetch(`${API}${path}`, { ...init, headers: { ...authHeaders(), ...(json ? { "Content-Type": "application/json" } : {}), ...init?.headers } });
  if (!r.ok) throw new Error(await explain(r));
  return r.status === 204 ? (undefined as T) : r.json();
}
const post = <T,>(p: string, body?: unknown) => req<T>(p, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  health: () => req<{ status: string; embedding_provider: string; documents: number; chunks: number }>("/health"),
  docs: () => req<Doc[]>("/api/documents"),
  upload: (files: File[]) => { const f = new FormData(); files.forEach((x) => f.append("files", x)); return req<Doc[]>("/api/documents", { method: "POST", body: f }); },
  deleteDoc: (id: string) => req<void>(`/api/documents/${id}`, { method: "DELETE" }),
  /** Short-lived link usable in <iframe>/<a> (which cannot send headers). Plain URL when auth is off. */
  signedFile: (docId: string) => req<{ url: string }>(`/api/documents/${docId}/signed-url`),
  runs: () => req<RunSummary[]>("/api/research?limit=30"),
  run: (id: string) => req<ResearchResult>(`/api/research/${id}`),
  rate: (id: string, rating: -1 | 0 | 1, note?: string) => post<void>(`/api/research/${id}/feedback`, { rating, note }),

  evalSets: () => req<EvalSet[]>("/api/eval/sets"),
  importSet: (name: string, jsonl: string) => post<EvalSet>("/api/eval/sets", { name, jsonl }),
  generateSet: (name: string, n_cases: number) => post<EvalSet>("/api/eval/sets/generate", { name, n_cases }),
  evalRuns: () => req<EvalRunMeta[]>("/api/eval/runs"),
  evalRun: (id: string) => req<EvalRun>(`/api/eval/runs/${id}`),
  startEval: (b: { set_id: string; name?: string; e2e: boolean; split: string; use_expansions: boolean }) => post<EvalRun>("/api/eval/runs", b),
  compare: (a: string, b: string) => req<{ deltas: { metric: string; a: number | null; b: number | null; delta: number | null }[] }>(`/api/eval/compare?a=${a}&b=${b}`),

  failures: (days: number) => req<ProdFailures>(`/api/feedback/failures?days=${days}`),
  expansions: () => req<Expansion[]>("/api/feedback/expansions"),
  setExpansion: (id: string, status: Expansion["status"]) => req<Expansion>(`/api/feedback/expansions/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),
  deleteExpansion: (id: string) => req<void>(`/api/feedback/expansions/${id}`, { method: "DELETE" }),
  propose: (eval_run_id: string) => post<Expansion[]>("/api/feedback/expansions/propose", { eval_run_id }),
};

/** Streams agent events over SSE. Resolves when the stream ends; abort via `signal`. */
export async function streamResearch(question: string, strict: boolean, onEvent: (e: AgentEvent) => void, signal?: AbortSignal) {
  const r = await fetch(`${API}/api/research/stream`, {
    method: "POST", headers: { ...authHeaders(), "Content-Type": "application/json" }, body: JSON.stringify({ question, strict }), signal,
  });
  if (!r.ok || !r.body) throw new Error(await explain(r));
  const reader = r.body.getReader(), dec = new TextDecoder(), p = new SSEParser();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    for (const d of p.push(dec.decode(value, { stream: true }))) onEvent(JSON.parse(d) as AgentEvent);
  }
}
