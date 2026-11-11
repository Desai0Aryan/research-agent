"use client";
import { AlertTriangle, CheckCircle2, ChevronDown, Copy, Download, ShieldAlert, ThumbsDown, ThumbsUp, XCircle } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { pct } from "@/lib/text";
import type { Claim, ResearchResult } from "@/lib/types";
import { Badge, Ring, Stat, cx } from "./ui";

interface Props { result: ResearchResult; selected?: { eid: string; claim?: Claim } | null; onSelect: (eid: string, claim: Claim) => void }

export function Report({ result: r, selected, onSelect }: Props) {
  const [showRemoved, setShowRemoved] = useState(false);
  const [rating, setRating] = useState<number>(0);
  const [copied, setCopied] = useState(false);
  const m = r.metrics;
  const evByN = new Map(r.citations.map((c) => [c.n, c.evidence_id]));

  async function rate(v: -1 | 1) {
    if (!r.run_id) return;
    const next = rating === v ? 0 : v;
    setRating(next);
    try { await api.rate(r.run_id, next as -1 | 0 | 1); } catch { setRating(rating); }
  }
  const download = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([r.markdown], { type: "text/markdown" }));
    a.download = `${r.title.slice(0, 50).replace(/\W+/g, "-")}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  const copy = async () => { await navigator.clipboard.writeText(r.markdown); setCopied(true); setTimeout(() => setCopied(false), 1500); };

  return (
    <article className="space-y-5 animate-fadeUp">
      <div className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="mb-1 flex flex-wrap gap-1.5"><Badge tone="violet">{r.engine}</Badge><Badge>{m.retrieval_rounds} retrieval round{m.retrieval_rounds > 1 ? "s" : ""}</Badge><Badge>{(m.latency_ms / 1000).toFixed(1)}s</Badge></div>
            <h2 className="text-xl font-semibold leading-snug tracking-tight">{r.title}</h2>
          </div>
          <div className="flex items-center gap-1.5">
            <button className="btn-ghost !p-2" title="Copy markdown" onClick={copy}>{copied ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : <Copy className="h-4 w-4" />}</button>
            <button className="btn-ghost !p-2" title="Download .md" onClick={download}><Download className="h-4 w-4" /></button>
            <button className={cx("btn-ghost !p-2", rating === 1 && "!border-emerald-500/50 !text-emerald-600")} title="Helpful" onClick={() => rate(1)}><ThumbsUp className="h-4 w-4" /></button>
            <button className={cx("btn-ghost !p-2", rating === -1 && "!border-rose-500/50 !text-rose-600")} title="Not helpful" onClick={() => rate(-1)}><ThumbsDown className="h-4 w-4" /></button>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
          <div className="card flex items-center gap-3 px-4 py-2.5 sm:col-span-1"><Ring value={m.faithfulness} label="Faithfulness" /><div className="text-xs font-semibold uppercase leading-tight tracking-wider text-slate-500">Faith-<br />fulness</div></div>
          <Stat label="Citation coverage" value={pct(m.citation_coverage)} tone={m.citation_coverage === 1 ? "green" : "amber"} />
          <Stat label="Supported" value={`${m.supported}/${m.claims_total}`} hint={m.partial ? `${m.partial} partial` : undefined} tone="green" />
          <Stat label="Unsupported" value={m.unsupported} hint={m.removed ? `${m.removed} removed` : "none"} tone={m.unsupported ? "red" : "green"} />
          <Stat label="Evidence" value={m.evidence_count} hint={`${m.documents_used} document${m.documents_used === 1 ? "" : "s"}`} />
        </div>
      </div>

      {r.warnings.length > 0 && (
        <div className="flex gap-2 rounded-xl border border-amber-300/50 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
          <AlertTriangle className="h-4 w-4 shrink-0" /><div>{r.warnings.map((w, i) => <div key={i}>{w}</div>)}</div>
        </div>
      )}

      {r.sections.length === 0 && (
        <div className="card flex gap-3 p-5 text-sm"><ShieldAlert className="h-5 w-5 shrink-0 text-amber-500" />
          <div><div className="font-medium">The agent abstained.</div><div className="text-slate-500">Your library has no sufficiently relevant evidence for this question, so it chose not to guess.</div></div></div>
      )}

      {r.sections.map((s) => (
        <section key={s.heading} className="card p-5">
          <h3 className="mb-3 text-base font-semibold">{s.heading}</h3>
          <ul className="space-y-2.5">
            {s.claims.map((c) => {
              const active = selected?.claim?.id === c.id;
              return (
                <li key={c.id} className={cx("group flex gap-2.5 rounded-xl p-2 transition", active ? "bg-brand-500/10 ring-1 ring-brand-500/30" : "hover:bg-slate-100/70 dark:hover:bg-white/5")}>
                  <span className="mt-0.5 shrink-0" title={`${c.verdict} (${pct(c.support_score)})`}>
                    {c.verdict === "supported" ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : c.verdict === "partial" ? <AlertTriangle className="h-4 w-4 text-amber-500" /> : <XCircle className="h-4 w-4 text-rose-500" />}
                  </span>
                  <p className="text-[15px] leading-relaxed">
                    {c.text}{" "}
                    {c.citations.map((n) => (
                      <button key={n} onClick={() => { const eid = evByN.get(n); if (eid) onSelect(eid, c); }}
                        className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-md bg-brand-500/10 px-1 align-baseline text-[11px] font-semibold text-brand-700 transition hover:bg-brand-500 hover:text-white dark:text-brand-400">
                        {n}
                      </button>
                    ))}
                    {c.verdict === "partial" && <Badge tone="amber" className="ml-1">partially supported</Badge>}
                  </p>
                </li>
              );
            })}
          </ul>
        </section>
      ))}

      {r.gaps.length > 0 && (
        <section className="card border-amber-300/50 p-5">
          <h3 className="mb-2 flex items-center gap-2 text-base font-semibold"><AlertTriangle className="h-4 w-4 text-amber-500" /> Gaps in the evidence</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-300">{r.gaps.map((g, i) => <li key={i}>{g}</li>)}</ul>
        </section>
      )}

      {r.removed_claims.length > 0 && (
        <section className="card p-4">
          <button className="flex w-full items-center justify-between text-left text-sm font-medium" onClick={() => setShowRemoved((v) => !v)}>
            <span className="flex items-center gap-2"><XCircle className="h-4 w-4 text-rose-500" /> {r.removed_claims.length} claim{r.removed_claims.length > 1 ? "s" : ""} removed by the verifier</span>
            <ChevronDown className={cx("h-4 w-4 transition", showRemoved && "rotate-180")} />
          </button>
          {showRemoved && (
            <ul className="mt-3 space-y-2">
              {r.removed_claims.map((c) => (
                <li key={c.id} className="rounded-lg bg-rose-500/5 p-2.5 text-sm">
                  <div className="line-through decoration-rose-400/60">{c.text}</div>
                  <div className="mt-1 text-xs text-slate-500">{c.reason ?? "Not supported by the cited passage."} (support {pct(c.support_score)})</div>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="card p-5">
        <h3 className="mb-3 text-base font-semibold">References</h3>
        <ol className="space-y-1.5 text-sm">
          {r.citations.map((c) => (
            <li key={c.n} className="flex gap-2">
              <button onClick={() => { const cl = r.sections.flatMap((s) => s.claims).find((x) => x.citations.includes(c.n)); if (cl) onSelect(c.evidence_id, cl); }}
                className="w-6 shrink-0 text-right font-semibold text-brand-600 hover:underline dark:text-brand-400">[{c.n}]</button>
              <span>{c.document_title}, <span className="text-slate-500">p. {c.page}</span>
                <span className="block truncate text-xs text-slate-400">“{(r.evidence.find((e) => e.id === c.evidence_id)?.text ?? "").slice(0, 90)}…”</span></span>
            </li>
          ))}
        </ol>
      </section>
    </article>
  );
}
