/** Split `text` into [before, match, after] around the first case/whitespace-insensitive occurrence of `quote`. */
export function locateQuote(text: string, quote?: string | null): [string, string, string] | null {
  if (!quote) return null;
  const esc = quote.trim().split(/\s+/).filter(Boolean).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+");
  if (!esc) return null;
  const m = new RegExp(esc, "i").exec(text);
  return m ? [text.slice(0, m.index), m[0], text.slice(m.index + m[0].length)] : null;
}

export const pct = (x: number | null | undefined, d = 0) => (x == null ? "—" : `${(x * 100).toFixed(d)}%`);
export const fmt = (x: number | null | undefined, d = 3) => (x == null ? "—" : x.toFixed(d));
export const ago = (iso: string) => {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
};
