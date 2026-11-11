"use client";
import { Check, MessageSquareWarning, Sparkles, ThumbsUp, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Empty, ErrorBox, PageHeader, Spinner, Stat, cx } from "@/components/ui";
import { api } from "@/lib/api";
import type { EvalRunMeta, Expansion, ProdFailures } from "@/lib/types";

const TONE = { proposed: "amber", enabled: "green", rejected: "slate" } as const;

export default function FeedbackPage() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<ProdFailures | null>(null);
  const [exps, setExps] = useState<Expansion[]>([]);
  const [runs, setRuns] = useState<EvalRunMeta[]>([]);
  const [runId, setRunId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [f, e, r] = await Promise.all([api.failures(days), api.expansions(), api.evalRuns()]);
      setData(f); setExps(e); setRuns(r.filter((x) => x.config.split !== "test")); setRunId((c) => c || r.find((x) => x.config.split !== "test")?.id || "");
    } catch (e) { setError((e as Error).message); }
  }, [days]);
  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<unknown>) => { setError(null); try { await fn(); await load(); } catch (e) { setError((e as Error).message); } };
  const propose = async () => { setBusy(true); await act(() => api.propose(runId)); setBusy(false); };
  const up = data?.ratings["1"] ?? 0, down = data?.ratings["-1"] ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader title="Feedback loop" subtitle="Find the questions your system fails on, understand why, and approve the fixes. Nothing learned here changes search until you enable it.">
        <select className="input !w-auto" value={days} onChange={(e) => setDays(+e.target.value)} aria-label="Time window">{[7, 30, 90, 365].map((d) => <option key={d} value={d}>last {d} days</option>)}</select>
      </PageHeader>
      <ErrorBox error={error} onClose={() => setError(null)} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Runs analysed" value={data?.runs_considered ?? "—"} />
        <Stat label="Failing" value={data?.failures.length ?? "—"} tone={data && data.failures.length ? "red" : "green"} />
        <Stat label="Helpful 👍" value={up} tone="green" />
        <Stat label="Not helpful 👎" value={down} tone={down ? "red" : undefined} />
      </div>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="card p-5">
          <h2 className="mb-3 flex items-center gap-2 font-semibold"><MessageSquareWarning className="h-4 w-4 text-amber-500" /> Failure clusters</h2>
          {!data ? <div className="skeleton h-32" /> : data.clusters.length === 0 ? <Empty icon={<ThumbsUp className="h-5 w-5" />} title="No failing queries" hint="Thumbs-down ratings, empty answers and low-faithfulness runs will show up here." /> : (
            <ul className="space-y-3">{data.clusters.map((c, i) => (
              <li key={i} className="rounded-xl bg-slate-50 p-3 dark:bg-white/5">
                <div className="mb-1.5 flex flex-wrap items-center gap-1.5"><Badge tone="red">{c.size} quer{c.size > 1 ? "ies" : "y"}</Badge>{Object.keys(c.labels).map((l) => <Badge key={l}>{l}</Badge>)}{c.top_terms.map((t) => <Badge key={t} tone="violet">{t}</Badge>)}</div>
                <ul className="list-disc space-y-0.5 pl-5 text-sm">{c.examples.map((x, j) => <li key={j}>{x}</li>)}</ul>
              </li>))}</ul>
          )}
          {data && data.summary.recommendations.length > 0 && <div className="mt-4 space-y-2 border-t border-slate-200/60 pt-3 dark:border-white/10">{data.summary.recommendations.map((r) => <div key={r.label} className="text-sm"><Badge tone="amber">{r.count}× {r.label}</Badge> <span className="text-slate-600 dark:text-slate-300">{r.action}</span></div>)}</div>}
        </div>
        <div className="card p-5">
          <h2 className="mb-1 font-semibold">Out-of-vocabulary terms</h2>
          <p className="mb-3 text-sm text-slate-500">Words in failed questions that appear nowhere in your documents — candidates for missing content or synonyms.</p>
          {!data || data.out_of_vocabulary_terms.length === 0 ? <p className="text-sm text-slate-400">None found.</p> : <div className="flex flex-wrap gap-2">{data.out_of_vocabulary_terms.map(([t, n]) => <Badge key={t} tone="red">{t} · {n}</Badge>)}</div>}
        </div>
      </section>

      <section className="card p-5">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div><h2 className="font-semibold">Query expansions</h2><p className="text-sm text-slate-500">Learned from evaluation failures. Review each one; only <b>enabled</b> expansions widen keyword search.</p></div>
          <div className="flex items-center gap-2">
            <select className="input !w-auto !py-1.5 text-sm" value={runId} onChange={(e) => setRunId(e.target.value)} aria-label="Eval run to learn from">
              {runs.length === 0 && <option value="">No train/all eval runs</option>}{runs.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select>
            <button className="btn-ghost" disabled={!runId || busy} onClick={propose}>{busy ? <Spinner /> : <Sparkles className="h-4 w-4" />} Propose from run</button>
          </div>
        </div>
        {exps.length === 0 ? <Empty icon={<Sparkles className="h-5 w-5" />} title="No expansions yet" hint="Run an evaluation on the train half (or all cases), then propose expansions from its failures. Held-out test runs are never used for learning." /> : (
          <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">term</th><th className="th">expands to</th><th className="th text-right">support</th><th className="th">status</th><th className="th" /></tr></thead>
            <tbody className="divide-y divide-slate-200/60 dark:divide-white/5">{exps.map((e) => (
              <tr key={e.id}><td className="td font-medium">{e.term}</td>
                <td className="td"><div className="flex flex-wrap gap-1">{e.expansions.map((x) => <Badge key={x} tone="blue">{x}</Badge>)}</div></td>
                <td className="td text-right tabular-nums">{e.support}</td>
                <td className="td"><Badge tone={TONE[e.status]}>{e.status}</Badge></td>
                <td className="td"><div className="flex justify-end gap-1">
                  <button title="Enable" onClick={() => act(() => api.setExpansion(e.id, "enabled"))} className={cx("rounded-lg p-1.5 hover:bg-emerald-500/10 hover:text-emerald-600", e.status === "enabled" && "text-emerald-600")}><Check className="h-4 w-4" /></button>
                  <button title="Reject" onClick={() => act(() => api.setExpansion(e.id, "rejected"))} className="rounded-lg p-1.5 hover:bg-amber-500/10 hover:text-amber-600"><X className="h-4 w-4" /></button>
                  <button title="Delete" onClick={() => act(() => api.deleteExpansion(e.id))} className="rounded-lg p-1.5 hover:bg-rose-500/10 hover:text-rose-600"><Trash2 className="h-4 w-4" /></button></div></td></tr>))}</tbody></table></div>
        )}
      </section>
    </div>
  );
}
