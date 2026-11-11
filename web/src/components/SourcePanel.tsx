"use client";
import { BadgeCheck, ExternalLink, FileText } from "lucide-react";
import { useEffect, useState } from "react";
import { API, api } from "@/lib/api";
import { locateQuote, pct } from "@/lib/text";
import type { Claim, Evidence } from "@/lib/types";
import { Badge, Empty } from "./ui";

export function SourcePanel({ evidence, claim }: { evidence: Evidence | null; claim?: Claim | null }) {
  const [showPdf, setShowPdf] = useState(false);
  const [signed, setSigned] = useState<string | null>(null);
  const docId = evidence?.document_id;
  useEffect(() => {
    setSigned(null);
    if (docId) api.signedFile(docId).then((r) => setSigned(r.url)).catch(() => setSigned(null));
  }, [docId]);
  if (!evidence) return <Empty icon={<FileText className="h-5 w-5" />} title="Select a citation" hint="Click any [n] marker in the report to read the exact source passage and open the page." />;
  const parts = locateQuote(evidence.text, claim?.quote);
  const isPdf = evidence.filename.toLowerCase().endsWith(".pdf");
  const base = signed ?? `/api/documents/${evidence.document_id}/file`;
  const href = `${API}${base}#page=${evidence.page}`;
  return (
    <div className="space-y-3 animate-fadeUp" key={evidence.id + (claim?.id ?? "")}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="violet">{evidence.id}</Badge>
        <Badge tone="blue">page {evidence.page}</Badge>
        <Badge>relevance {evidence.relevance.toFixed(2)}</Badge>
        {claim?.quote_verified && <Badge tone="green"><BadgeCheck className="h-3 w-3" /> quote verified verbatim</Badge>}
      </div>
      <div>
        <div className="font-medium leading-snug">{evidence.document_title}</div>
        <div className="text-xs text-slate-500">{evidence.filename}</div>
      </div>
      {claim && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm dark:border-white/10 dark:bg-white/5">
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Claim being checked</div>
          {claim.text}
          <div className="mt-2 flex gap-2 text-xs text-slate-500">
            <Badge tone={claim.verdict === "supported" ? "green" : claim.verdict === "partial" ? "amber" : "red"}>{claim.verdict}</Badge>
            <span>support score {pct(claim.support_score)}</span>
          </div>
          {claim.reason && <div className="mt-1 text-xs text-slate-500">{claim.reason}</div>}
        </div>
      )}
      <div>
        <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Source passage</div>
        <blockquote className="max-h-72 overflow-auto rounded-xl border-l-4 border-brand-500 bg-white/60 p-3 text-sm leading-relaxed dark:bg-white/5">
          {parts ? <>{parts[0]}<mark className="quote">{parts[1]}</mark>{parts[2]}</> : evidence.text}
        </blockquote>
      </div>
      <div className="flex flex-wrap gap-2">
        {isPdf && <button className="btn-ghost !py-1.5 text-xs" onClick={() => setShowPdf((v) => !v)}>{showPdf ? "Hide" : "Show"} original page</button>}
        <a className="btn-ghost !py-1.5 text-xs" href={href} target="_blank" rel="noreferrer"><ExternalLink className="h-3.5 w-3.5" /> Open source{isPdf ? ` at p.${evidence.page}` : ""}</a>
      </div>
      {isPdf && showPdf && <iframe title="Source document" src={href} className="h-[460px] w-full rounded-xl border border-slate-200 bg-white dark:border-white/10" />}
    </div>
  );
}
