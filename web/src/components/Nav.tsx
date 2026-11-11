"use client";
import { FlaskConical, Library, MessageSquareWarning, Sparkles, Telescope } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ThemeToggle } from "./ThemeToggle";
import { cx } from "./ui";

const LINKS = [
  { href: "/", label: "Research", icon: Telescope },
  { href: "/library", label: "Library", icon: Library },
  { href: "/eval", label: "Evaluation", icon: FlaskConical },
  { href: "/feedback", label: "Feedback", icon: MessageSquareWarning },
];

export function Nav() {
  const path = usePathname();
  const [h, setH] = useState<{ documents: number; chunks: number; embedding_provider: string } | null | "down">(null);
  useEffect(() => {
    let live = true;
    const tick = () => api.health().then((x) => live && setH(x)).catch(() => live && setH("down"));
    tick();
    const id = setInterval(tick, 15000);
    return () => { live = false; clearInterval(id); };
  }, []);
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/70 bg-white/70 backdrop-blur-xl dark:border-white/10 dark:bg-[#0b0d17]/70">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-brand-500 to-fuchsia-500 text-white shadow-glow"><Sparkles className="h-4 w-4" /></span>
          <span className="hidden sm:inline">Research Agent</span>
        </Link>
        <nav className="flex flex-1 items-center gap-1">
          {LINKS.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? path === "/" : path.startsWith(href);
            return (
              <Link key={href} href={href} className={cx("flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition", active ? "bg-brand-500/10 font-medium text-brand-700 dark:text-brand-100" : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-white/5")}>
                <Icon className="h-4 w-4" /><span className="hidden md:inline">{label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="hidden items-center gap-2 text-xs text-slate-500 sm:flex" title="Backend status">
          <span className={cx("h-2 w-2 rounded-full", h === "down" ? "bg-rose-500" : h ? "bg-emerald-500" : "animate-pulse bg-slate-400")} />
          {h === "down" ? "API offline" : h ? `${h.documents} docs · ${h.chunks} chunks · ${h.embedding_provider}` : "connecting…"}
        </div>
        <ThemeToggle />
      </div>
    </header>
  );
}
