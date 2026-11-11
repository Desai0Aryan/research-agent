import { AlertTriangle, Loader2 } from "lucide-react";
import type { ReactNode } from "react";

export const cx = (...a: (string | false | null | undefined)[]) => a.filter(Boolean).join(" ");

const TONES = {
  green: "bg-emerald-500/10 text-emerald-700 ring-emerald-500/25 dark:text-emerald-300",
  amber: "bg-amber-500/10 text-amber-700 ring-amber-500/25 dark:text-amber-300",
  red: "bg-rose-500/10 text-rose-700 ring-rose-500/25 dark:text-rose-300",
  blue: "bg-sky-500/10 text-sky-700 ring-sky-500/25 dark:text-sky-300",
  violet: "bg-violet-500/10 text-violet-700 ring-violet-500/25 dark:text-violet-300",
  slate: "bg-slate-500/10 text-slate-600 ring-slate-500/20 dark:text-slate-300",
} as const;
export type Tone = keyof typeof TONES;

export function Badge({ tone = "slate", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={cx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset", TONES[tone], className)}>{children}</span>;
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cx("h-4 w-4 animate-spin", className)} />;
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: string; tone?: Tone }) {
  return (
    <div className="card px-4 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">{label}</div>
      <div className={cx("mt-1 text-2xl font-semibold tabular-nums", tone === "green" && "text-emerald-600 dark:text-emerald-400", tone === "red" && "text-rose-600 dark:text-rose-400", tone === "amber" && "text-amber-600 dark:text-amber-400")}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{hint}</div>}
    </div>
  );
}

export function ErrorBox({ error, onClose }: { error: string | null; onClose?: () => void }) {
  if (!error) return null;
  return (
    <div className="flex items-start gap-2 rounded-xl border border-rose-300/60 bg-rose-50 px-3.5 py-3 text-sm text-rose-800 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1 break-words">{error}</div>
      {onClose && <button onClick={onClose} className="text-xs underline">dismiss</button>}
    </div>
  );
}

export function Empty({ icon, title, hint }: { icon: ReactNode; title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-14 text-center text-slate-500 dark:text-slate-400">
      <div className="rounded-2xl bg-slate-100 p-3 dark:bg-white/5">{icon}</div>
      <div className="font-medium text-slate-700 dark:text-slate-200">{title}</div>
      {hint && <div className="max-w-sm text-sm">{hint}</div>}
    </div>
  );
}

export function Ring({ value, size = 76, label }: { value: number; size?: number; label: string }) {
  const r = (size - 10) / 2, c = 2 * Math.PI * r, v = Math.max(0, Math.min(1, value));
  const color = v >= 0.9 ? "#10b981" : v >= 0.7 ? "#f59e0b" : "#f43f5e";
  return (
    <div className="relative" style={{ width: size, height: size }} role="img" aria-label={`${label} ${Math.round(v * 100)}%`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={8} className="stroke-slate-200 dark:stroke-white/10" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={8} strokeLinecap="round" stroke={color}
          strokeDasharray={c} strokeDashoffset={c * (1 - v)} style={{ transition: "stroke-dashoffset .8s ease" }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-sm font-semibold tabular-nums">{Math.round(v * 100)}%</div>
    </div>
  );
}

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="bg-gradient-to-r from-slate-900 to-slate-600 bg-clip-text text-2xl font-semibold tracking-tight text-transparent dark:from-white dark:to-slate-400">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}
