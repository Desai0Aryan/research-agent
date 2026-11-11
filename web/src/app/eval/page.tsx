"use client";
import { FlaskConical, Play, Sparkles, Upload } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { GroupedBars } from "@/components/Charts";
import { Badge, Empty, ErrorBox, PageHeader, Spinner, Stat, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { ago, fmt, pct } from "@/lib/text";
import type { EvalRun, EvalRunMeta, EvalSet } from "@/lib/types";

const METRICS = ["recall@1", "recall@3", "recall@5", "recall@10", "mrr", "ndcg@10"];
const MODE_ORDER = ["hybrid", "vector", "keyword"];

export default function EvalPage() {
  const [sets, setSets] = useState<EvalSet[]>([]);
  const [runs, setRuns] = useState<EvalRunMeta[]>([]);
  const [setId, setSetId] = useState("");
  const [opts, setOpts] = useState({ e2e: true, split: "all", use_expansions: true });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [run, setRun] = useState<EvalRun | null>(null);
  const [cmp, setCmp] = useState<{ a: string; b: string; rows: { metric: string; a: number | null; b: number | null; delta: number | null }[] } | null>(null);
  const [cmpA, setCmpA] = useState(""); const [cmpB, setCmpB] = useState("");
  const file = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([api.evalSets(), api.evalRuns()]);
      setSets(s); setRuns(r); setSetId((cur) => cur || s[0]?.id || "");
    } catch (e) { setError((e as Error).message); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const guard = async (label: string, fn: () => Promise<void>) => {
    setBusy(label); setError(null);
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  };
  const importFile = (f: File) => guard("import", async () => { const s = await api.importSet(f.name.replace(/\.jsonl?$/, ""), await f.text()); await refresh(); setSetId(s.id); });
  const generate = () => guard("generate", async () => { const s = await api.generateSet(`synthetic-${new Date().toISOString().slice(0, 16)}`, 20); await refresh(); setSetId(s.id); });
  const start = () => guard("run", async () => {
    const r = await api.startEval({ set_id: setId, name: `${opts.split} · ${opts.e2e ? "e2e" : "retrieval"}${opts.use_expansions ? "" : " · no-exp"}`, ...opts });
    setRun(r); await refresh();
  });
  const open = (id: string) => guard("open", async () => setRun(await api.evalRun(id)));
  const compare = () => guard("compare", async () => { const c = await api.compare(cmpA, cmpB); setCmp({ a: cmpA, b: cmpB, rows: c.deltas }); });

  const modes = run ? MODE_ORDER.filter((m) => run.report.retrieval.modes[m]) : [];
  const ans = run?.report.answers;
  return (
    <div className="space-y-6">
      <PageHeader title="Evaluation" subtitle="Measure retrieval (recall@k, MRR, nDCG), answer correctness, faithfulness and abstention against a golden set — then compare runs to prove a change helped." />
      <ErrorBox error={error} onClose={() => setError(null)} />

      <section className="card grid gap-4 p-5 md:grid-cols-[1fr_auto]">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <select value={setId} onChange={(e) => setSetId(e.target.value)} className="input !w-auto min-w-64" aria-label="Golden set">
              {sets.length === 0 && <option value="">No golden sets yet</option>}
              {sets.map((s) => <option key={s.id} value={s.id}>{s.name} — {s.n_cases} cases ({s.n_answerable} answerable)</option>)}
            </select>
            <input ref={file} type="file" accept=".jsonl,.json" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) importFile(f); e.target.value = ""; }} />
            <button className="btn-ghost" onClick={() => file.current?.click()} disabled={!!busy}>{busy === "import" ? <Spinner /> : <Upload className="h-4 w-4" />} Import JSONL</button>
            <button className="btn-ghost" onClick={generate} disabled={!!busy}>{busy === "generate" ? <Spinner /> : <Sparkles className="h-4 w-4" />} Generate synthetic</button>
          </div>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
            <label className="flex items-center gap-2"><input type="checkbox" className="accent-brand-600" checked={opts.e2e} onChange={(e) => setOpts({ ...opts, e2e: e.target.checked })} /> End-to-end answers</label>
            <label className="flex items-center gap-2"><input type="checkbox" className="accent-brand-600" checked={opts.use_expansions} onChange={(e) => setOpts({ ...opts, use_expansions: e.target.checked })} /> Use approved expansions</label>
            <label className="flex items-center gap-2">Split
              <select className="input !w-auto !py-1.5" value={opts.split} onChange={(e) => setOpts({ ...opts, split: e.target.value })}>
                <option value="all">all cases</option><option value="train">train half</option><option value="test">held-out test half</option></select></label>
          </div>
        </div>
        <button className="btn-primary self-end" onClick={start} disabled={!setId || !!busy}>{busy === "run" ? <><Spinner /> Running…</> : <><Play className="h-4 w-4" /> Run evaluation</>}</button>
      </section>

      <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <div className="card p-3">
            <h2 className="mb-2 px-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Runs</h2>
            {runs.length === 0 ? <div className="px-2 py-6 text-center text-sm text-slate-500">No runs yet</div> : (
              <ul className="max-h-96 space-y-0.5 overflow-auto">
                {runs.map((r) => (
                  <li key={r.id}><button onClick={() => open(r.id)} className={cx("w-full rounded-lg px-2.5 py-2 text-left text-sm transition hover:bg-slate-100 dark:hover:bg-white/5", run?.id === r.id && "bg-brand-500/10")}>
                    <div className="truncate font-medium">{r.name}</div>
                    <div className="flex items-center gap-2 text-xs text-slate-500"><span>{ago(r.created_at)}</span><span>R@5 {fmt(r.summary["retrieval.hybrid.recall@5"], 2)}</span></div></button></li>
                ))}
              </ul>
            )}
          </div>
          {runs.length >= 2 && (
            <div className="card space-y-2 p-3">
              <h2 className="px-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Compare runs</h2>
              {[["Baseline", cmpA, setCmpA], ["Candidate", cmpB, setCmpB]].map(([label, val, set]) => (
                <select key={label as string} className="input !py-1.5 text-xs" value={val as string} onChange={(e) => (set as (v: string) => void)(e.target.value)} aria-label={label as string}>
                  <option value="">{label as string}…</option>{runs.map((r) => <option key={r.id} value={r.id}>{r.name} · {ago(r.created_at)}</option>)}</select>
              ))}
              <button className="btn-ghost w-full" disabled={!cmpA || !cmpB || !!busy} onClick={compare}>Compare</button>
            </div>
          )}
        </aside>

        <div className="min-w-0 space-y-5">
          {busy === "run" && <div className="card flex items-center gap-3 p-5 text-sm"><Spinner className="text-brand-500" /> Evaluating every case across all retrieval modes{opts.e2e ? " and running the full agent on each question" : ""}…</div>}
          {cmp && <CompareTable cmp={cmp} onClose={() => setCmp(null)} />}
          {!run && busy !== "run" && <div className="card"><Empty icon={<FlaskConical className="h-5 w-5" />} title="No run selected" hint="Import a golden set (see samples/golden_sample.jsonl) or generate a synthetic one, then run an evaluation." /></div>}
          {run && (
            <>
              <div className="flex flex-wrap items-center gap-1.5">
                <Badge tone="violet">{run.name}</Badge>
                {Object.entries(run.config).filter(([k]) => ["n_cases", "engine", "embedding", "chunk", "reranker", "split", "use_expansions"].includes(k)).map(([k, v]) => <Badge key={k}>{k}: {String(v)}</Badge>)}
              </div>
              {ans && (
                <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                  <Stat label="Answer correctness" value={pct(ans.answer_correctness)} tone={ans.answer_correctness >= 0.7 ? "green" : "amber"} hint="key facts present" />
                  <Stat label="Faithfulness" value={pct(ans.faithfulness)} tone={ans.faithfulness >= 0.9 ? "green" : "amber"} />
                  <Stat label="Unsupported claims" value={pct(ans.unsupported_claim_rate, 1)} tone={ans.unsupported_claim_rate <= 0.05 ? "green" : "red"} />
                  <Stat label="Gold cited" value={pct(ans.gold_citation_rate)} hint="cites the right page" />
                  <Stat label="Abstention" value={pct(ans.abstention_accuracy)} hint="on unanswerable Qs" tone={(ans.abstention_accuracy ?? 1) >= 0.9 ? "green" : "red"} />
                </div>
              )}
              <div className="card p-5">
                <h2 className="mb-3 font-semibold">Retrieval quality by search mode <span className="text-xs font-normal text-slate-500">({run.report.retrieval.n_cases} answerable cases)</span></h2>
                <GroupedBars groups={METRICS} series={modes.map((m) => ({ name: m, values: METRICS.map((k) => run.report.retrieval.modes[m][k] ?? 0) }))} />
                <div className="mt-4 overflow-x-auto"><table className="w-full"><thead><tr><th className="th">mode</th>{METRICS.map((k) => <th key={k} className="th text-right">{k}</th>)}</tr></thead>
                  <tbody className="divide-y divide-slate-200/60 dark:divide-white/5">{modes.map((m) => {
                    const best = Object.fromEntries(METRICS.map((k) => [k, Math.max(...modes.map((x) => run.report.retrieval.modes[x][k] ?? 0))]));
                    return <tr key={m}><td className="td font-medium">{m}</td>{METRICS.map((k) => { const v = run.report.retrieval.modes[m][k] ?? 0; return <td key={k} className={cx("td text-right tabular-nums", v === best[k] && v > 0 && "font-semibold text-emerald-600 dark:text-emerald-400")}>{v.toFixed(3)}</td>; })}</tr>;
                  })}</tbody></table></div>
              </div>
              <div className="card p-5">
                <h2 className="mb-1 font-semibold">Failure analysis <span className="text-xs font-normal text-slate-500">({run.report.failure_summary.total} failing)</span></h2>
                {run.report.failure_summary.total === 0 ? <p className="text-sm text-emerald-600">No failures — every case passed.</p> : (
                  <>
                    <ul className="mt-3 space-y-2">{run.report.failure_summary.recommendations.map((r) => (
                      <li key={r.label} className="flex gap-3 rounded-xl bg-slate-50 p-3 text-sm dark:bg-white/5"><Badge tone="amber" className="h-fit shrink-0">{r.count}× {r.label}</Badge><span className="text-slate-600 dark:text-slate-300">{r.action}</span></li>))}</ul>
                    <details className="mt-3"><summary className="cursor-pointer text-sm font-medium text-brand-600">Show failing questions</summary>
                      <ul className="mt-2 space-y-1.5 text-sm">{run.report.failures.map((f, i) => <li key={i} className="flex gap-2"><Badge tone={f.kind === "retrieval" ? "red" : "violet"}>{f.label}</Badge><span>{f.question}</span></li>)}</ul></details>
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function CompareTable({ cmp, onClose }: { cmp: { rows: { metric: string; a: number | null; b: number | null; delta: number | null }[] }; onClose: () => void }) {
  const lowerBetter = (m: string) => m.includes("unsupported");
  const rows = cmp.rows.filter((r) => r.delta !== null);
  return (
    <div className="card p-5">
      <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Run comparison</h2><button onClick={onClose} className="text-xs text-slate-500 underline">close</button></div>
      <div className="max-h-80 overflow-auto"><table className="w-full"><thead><tr><th className="th">metric</th><th className="th text-right">baseline</th><th className="th text-right">candidate</th><th className="th text-right">Δ</th></tr></thead>
        <tbody className="divide-y divide-slate-200/60 dark:divide-white/5">{rows.map((r) => {
          const d = r.delta ?? 0, good = lowerBetter(r.metric) ? d < 0 : d > 0;
          return <tr key={r.metric}><td className="td font-mono text-xs">{r.metric}</td><td className="td text-right tabular-nums">{fmt(r.a)}</td><td className="td text-right tabular-nums">{fmt(r.b)}</td>
            <td className={cx("td text-right font-medium tabular-nums", d === 0 ? "text-slate-400" : good ? "text-emerald-600" : "text-rose-600")}>{d > 0 ? "+" : ""}{d.toFixed(3)}</td></tr>;
        })}</tbody></table></div>
    </div>
  );
}
