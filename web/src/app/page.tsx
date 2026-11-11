"use client";
import { ArrowUp, History, Sparkles, Square, FileSearch } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Report } from "@/components/Report";
import { SourcePanel } from "@/components/SourcePanel";
import { Timeline } from "@/components/Timeline";
import { Badge, Empty, ErrorBox, cx } from "@/components/ui";
import { api, streamResearch } from "@/lib/api";
import { ago, pct } from "@/lib/text";
import type { AgentEvent, Claim, ResearchResult, RunSummary } from "@/lib/types";

const EXAMPLES = [
  "How does reciprocal rank fusion work, and how is hallucination measured in RAG?",
  "Why should chunks not cross page boundaries, and what is chunk overlap for?",
  "Compare dense and keyword retrieval, and explain how query expansion helps",
  "What should a research assistant do when the sources contradict each other?",
];

export default function ResearchPage() {
  const [q, setQ] = useState("");
  const [strict, setStrict] = useState(true);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ResearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sel, setSel] = useState<{ eid: string; claim?: Claim } | null>(null);
  const [tab, setTab] = useState<"source" | "history">("source");
  const [history, setHistory] = useState<RunSummary[]>([]);
  const abort = useRef<AbortController | null>(null);

  const loadHistory = useCallback(() => api.runs().then(setHistory).catch(() => {}), []);
  useEffect(() => { loadHistory(); }, [loadHistory]);

  const show = useCallback((r: ResearchResult) => {
    setResult(r);
    const first = r.sections.flatMap((s) => s.claims).find((c) => c.citations.length);
    const eid = first ? r.citations.find((c) => c.n === first.citations[0])?.evidence_id : undefined;
    setSel(eid && first ? { eid, claim: first } : null);
    setTab("source");
  }, []);

  async function run(question: string) {
    if (!question.trim() || running) return;
    setQ(question); setEvents([]); setResult(null); setSel(null); setError(null); setRunning(true);
    const ctl = new AbortController();
    abort.current = ctl;
    try {
      await streamResearch(question, strict, (e) => {
        if (e.type === "error") setError(e.message);
        else if (e.type === "done") show(e.result);
        else setEvents((prev) => [...prev, e]);
      }, ctl.signal);
    } catch (err) {
      if ((err as Error).name !== "AbortError") setError(`${(err as Error).message}. Is the API running at ${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}?`);
    } finally {
      setRunning(false); abort.current = null; loadHistory();
    }
  }

  const evidence = result && sel ? result.evidence.find((e) => e.id === sel.eid) ?? null : null;
  const idle = !running && !result && !events.length;

  return (
    <div className="space-y-6">
      <section className={cx("text-center transition-all", idle ? "py-10" : "py-0")}>
        {idle && (
          <>
            <Badge tone="violet" className="mb-4"><Sparkles className="h-3 w-3" /> every claim cited · every citation verified</Badge>
            <h1 className="mx-auto max-w-3xl bg-gradient-to-br from-slate-900 via-brand-700 to-fuchsia-600 bg-clip-text text-4xl font-bold tracking-tight text-transparent sm:text-5xl dark:from-white dark:via-brand-400 dark:to-fuchsia-400">
              Research across your documents. Trust every sentence.
            </h1>
            <p className="mx-auto mt-3 max-w-xl text-slate-500 dark:text-slate-400">Ask a complex question. The agent plans, retrieves, compares sources, writes a report and checks each claim against the exact passage it cites.</p>
          </>
        )}
        <form onSubmit={(e) => { e.preventDefault(); run(q); }} className="card mx-auto mt-6 max-w-3xl p-2 text-left shadow-glow">
          <textarea value={q} onChange={(e) => setQ(e.target.value)} rows={idle ? 3 : 2} placeholder="Ask a research question…  (⌘/Ctrl + Enter to run)"
            onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); run(q); } }}
            className="w-full resize-none bg-transparent px-3 py-2 text-[15px] outline-none placeholder:text-slate-400" aria-label="Research question" />
          <div className="flex items-center justify-between gap-3 px-2 pb-1">
            <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-500" title="Remove claims the verifier cannot support">
              <input type="checkbox" checked={strict} onChange={(e) => setStrict(e.target.checked)} className="accent-brand-600" /> Strict citations
            </label>
            {running
              ? <button type="button" className="btn-ghost" onClick={() => abort.current?.abort()}><Square className="h-3.5 w-3.5" /> Stop</button>
              : <button type="submit" className="btn-primary" disabled={q.trim().length < 5}><ArrowUp className="h-4 w-4" /> Research</button>}
          </div>
        </form>
        {idle && (
          <div className="mx-auto mt-5 flex max-w-3xl flex-wrap justify-center gap-2">
            {EXAMPLES.map((x) => <button key={x} className="btn-ghost !py-1.5 text-xs" onClick={() => run(x)}>{x}</button>)}
          </div>
        )}
      </section>

      <ErrorBox error={error} onClose={() => setError(null)} />

      {!idle && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_420px]">
          <div className="min-w-0 space-y-5">
            {(running || (!result && events.length > 0)) && <Timeline events={events} running={running} />}
            {result && <Report result={result} selected={sel} onSelect={(eid, claim) => { setSel({ eid, claim }); setTab("source"); }} />}
            {running && !result && <div className="space-y-3"><div className="skeleton h-28" /><div className="skeleton h-40" /></div>}
          </div>
          <aside className="lg:sticky lg:top-20 lg:self-start">
            <div className="card overflow-hidden">
              <div className="flex border-b border-slate-200/70 text-sm dark:border-white/10">
                {(["source", "history"] as const).map((t) => (
                  <button key={t} onClick={() => setTab(t)} className={cx("flex flex-1 items-center justify-center gap-1.5 py-2.5 font-medium transition", tab === t ? "border-b-2 border-brand-500 text-brand-700 dark:text-brand-400" : "text-slate-500")}>
                    {t === "source" ? <FileSearch className="h-4 w-4" /> : <History className="h-4 w-4" />}{t === "source" ? "Source" : "History"}
                  </button>
                ))}
              </div>
              <div className="max-h-[calc(100vh-9rem)] overflow-auto p-4">
                {tab === "source" ? <SourcePanel evidence={evidence} claim={sel?.claim} /> : <HistoryList runs={history} onPick={(id) => api.run(id).then((r) => { setEvents([]); setQ(r.question); show(r); }).catch((e) => setError(e.message))} />}
              </div>
            </div>
          </aside>
        </div>
      )}
      {idle && history.length > 0 && (
        <section className="mx-auto max-w-3xl"><h2 className="mb-2 text-sm font-semibold text-slate-500">Recent research</h2>
          <div className="card p-2"><HistoryList runs={history.slice(0, 5)} onPick={(id) => api.run(id).then((r) => { setQ(r.question); show(r); }).catch((e) => setError(e.message))} /></div></section>
      )}
    </div>
  );
}

function HistoryList({ runs, onPick }: { runs: RunSummary[]; onPick: (id: string) => void }) {
  if (!runs.length) return <Empty icon={<History className="h-5 w-5" />} title="No research yet" hint="Your past reports appear here." />;
  return (
    <ul className="divide-y divide-slate-200/60 dark:divide-white/5">
      {runs.map((r) => (
        <li key={r.id}>
          <button disabled={r.status !== "done"} onClick={() => onPick(r.id)} className="w-full rounded-lg px-2 py-2.5 text-left transition hover:bg-slate-100 disabled:opacity-50 dark:hover:bg-white/5">
            <div className="line-clamp-2 text-sm">{r.question}</div>
            <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
              <span>{ago(r.created_at)}</span>
              {r.status !== "done" && <Badge tone={r.status === "failed" ? "red" : "amber"}>{r.status}</Badge>}
              {r.metrics && <Badge tone={r.metrics.faithfulness >= 0.9 ? "green" : "amber"}>faithfulness {pct(r.metrics.faithfulness)}</Badge>}
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}
