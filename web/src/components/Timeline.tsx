import { CheckCircle2, CircleDot, GitBranch, Layers, ListTree, RefreshCcw, Search, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import type { AgentEvent } from "@/lib/types";
import { Spinner, cx } from "./ui";

interface Step { icon: ReactNode; title: string; detail?: ReactNode; tone?: "default" | "warn" }

function toSteps(events: AgentEvent[]): Step[] {
  const steps: Step[] = [];
  for (const e of events) {
    switch (e.type) {
      case "status":
        if (e.message.startsWith("Verifying")) steps.push({ icon: <ShieldCheck className="h-4 w-4" />, title: e.message });
        else if (e.message.startsWith("Writing")) steps.push({ icon: <Layers className="h-4 w-4" />, title: e.message });
        break;
      case "plan":
        steps.push({
          icon: <ListTree className="h-4 w-4" />, title: `Planned ${e.sub_questions.length} sub-question${e.sub_questions.length > 1 ? "s" : ""}`,
          detail: <ol className="mt-1 list-decimal space-y-0.5 pl-5 text-xs text-slate-500 dark:text-slate-400">{e.sub_questions.map((q, i) => <li key={i}>{q}</li>)}</ol>,
        });
        break;
      case "retrieve":
        steps.push({ icon: <Search className="h-4 w-4" />, title: `Sub-question ${e.sub_question + 1} · round ${e.round}`, detail: <span className="text-xs text-slate-500 dark:text-slate-400">{e.hits} candidates for “{e.query.length > 80 ? e.query.slice(0, 80) + "…" : e.query}”</span> });
        break;
      case "rerank":
        steps.push({ icon: <GitBranch className="h-4 w-4" />, title: `Reranked, kept ${e.kept}`, detail: <span className="text-xs text-slate-500 dark:text-slate-400">best relevance {e.best_score.toFixed(2)}</span> });
        break;
      case "gap":
        steps.push({ icon: <RefreshCcw className="h-4 w-4" />, title: "Evidence looked thin — reformulating", tone: "warn", detail: <span className="text-xs">{e.queries.join(" · ")}</span> });
        break;
      case "evidence":
        steps.push({ icon: <CheckCircle2 className="h-4 w-4" />, title: `${e.count} passages from ${e.documents} document${e.documents === 1 ? "" : "s"} selected` });
        break;
    }
  }
  return steps;
}

export function Timeline({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const steps = toSteps(events);
  if (!steps.length && !running) return null;
  return (
    <ol className="card relative space-y-0 p-4" aria-live="polite">
      {steps.map((s, i) => {
        const last = i === steps.length - 1;
        return (
          <li key={i} className="relative flex gap-3 pb-3 animate-fadeUp last:pb-0">
            {!last && <span className="absolute left-[15px] top-8 h-[calc(100%-1.5rem)] w-px bg-slate-200 dark:bg-white/10" />}
            <span className={cx("z-10 grid h-8 w-8 shrink-0 place-items-center rounded-full ring-1 ring-inset", s.tone === "warn" ? "bg-amber-500/10 text-amber-600 ring-amber-500/30" : "bg-brand-500/10 text-brand-600 ring-brand-500/25 dark:text-brand-400")}>
              {running && last ? <Spinner /> : s.icon}
            </span>
            <div className="min-w-0 pt-1"><div className="text-sm font-medium">{s.title}</div>{s.detail}</div>
          </li>
        );
      })}
      {running && !steps.length && <li className="flex items-center gap-2 text-sm text-slate-500"><CircleDot className="h-4 w-4 animate-pulse" /> Starting…</li>}
    </ol>
  );
}
