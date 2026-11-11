const PALETTE = ["#6366f1", "#ec4899", "#14b8a6", "#f59e0b"];

/** Dependency-free grouped bar chart for 0..1 metrics. */
export function GroupedBars({ groups, series }: { groups: string[]; series: { name: string; values: number[] }[] }) {
  const W = 640, H = 240, L = 34, B = 28, T = 10, R = 8;
  const gw = (W - L - R) / groups.length, bw = Math.min(26, (gw - 14) / series.length);
  const y = (v: number) => T + (H - T - B) * (1 - Math.max(0, Math.min(1, v)));
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Retrieval metrics by search mode">
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} className="stroke-slate-200 dark:stroke-white/10" strokeDasharray={t ? "3 4" : undefined} />
            <text x={L - 6} y={y(t) + 3} textAnchor="end" className="fill-slate-400 text-[10px]">{t.toFixed(2).replace(/0$/, "")}</text>
          </g>
        ))}
        {groups.map((g, gi) => {
          const x0 = L + gi * gw + (gw - bw * series.length) / 2;
          return (
            <g key={g}>
              {series.map((s, si) => {
                const v = s.values[gi] ?? 0;
                return (
                  <g key={s.name}>
                    <rect x={x0 + si * bw} y={y(v)} width={bw - 3} height={Math.max(1, H - B - y(v))} rx={4} fill={PALETTE[si % PALETTE.length]} opacity={0.9}>
                      <title>{`${s.name} · ${g}: ${v.toFixed(3)}`}</title>
                    </rect>
                    {v > 0.05 && <text x={x0 + si * bw + (bw - 3) / 2} y={y(v) - 4} textAnchor="middle" className="fill-slate-500 text-[9px] tabular-nums dark:fill-slate-400">{v.toFixed(2)}</text>}
                  </g>
                );
              })}
              <text x={L + gi * gw + gw / 2} y={H - 9} textAnchor="middle" className="fill-slate-500 text-[11px]">{g}</text>
            </g>
          );
        })}
      </svg>
      <figcaption className="mt-1 flex flex-wrap justify-center gap-4 text-xs text-slate-500">
        {series.map((s, i) => <span key={s.name} className="flex items-center gap-1.5"><i className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: PALETTE[i % PALETTE.length] }} />{s.name}</span>)}
      </figcaption>
    </figure>
  );
}
