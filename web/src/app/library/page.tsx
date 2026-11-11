"use client";
import { CheckCircle2, FileText, Library, Trash2, UploadCloud, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Badge, Empty, ErrorBox, PageHeader, Spinner, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { ago } from "@/lib/text";
import type { Doc } from "@/lib/types";

export default function LibraryPage() {
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const refresh = useCallback(() => api.docs().then(setDocs).catch((e) => setError(e.message)), []);
  useEffect(() => { refresh(); }, [refresh]);
  const busy = docs?.some((d) => d.status === "pending" || d.status === "processing");
  useEffect(() => { if (!busy) return; const id = setInterval(refresh, 1500); return () => clearInterval(id); }, [busy, refresh]);

  async function upload(files: FileList | File[]) {
    const list = Array.from(files);
    if (!list.length) return;
    setUploading(true); setError(null);
    try { await api.upload(list); await refresh(); } catch (e) { setError((e as Error).message); } finally { setUploading(false); }
  }
  async function remove(d: Doc) {
    if (!confirm(`Delete “${d.title}” and its ${d.num_chunks} chunks?`)) return;
    try { await api.deleteDoc(d.id); await refresh(); } catch (e) { setError((e as Error).message); }
  }

  const ready = docs?.filter((d) => d.status === "ready") ?? [];
  return (
    <div>
      <PageHeader title="Document library" subtitle="PDF, Markdown and text files are split into page-aware passages, embedded, and indexed for hybrid search. Re-uploading the same file is a no-op.">
        {docs && <div className="flex gap-2 text-xs"><Badge tone="green">{ready.length} ready</Badge><Badge>{ready.reduce((a, d) => a + d.num_pages, 0)} pages</Badge><Badge>{ready.reduce((a, d) => a + d.num_chunks, 0)} chunks</Badge></div>}
      </PageHeader>
      <ErrorBox error={error} onClose={() => setError(null)} />
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files); }}
        onClick={() => input.current?.click()} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && input.current?.click()}
        className={cx("card mb-6 mt-4 flex cursor-pointer flex-col items-center gap-2 border-2 border-dashed px-6 py-10 text-center transition", drag ? "border-brand-500 bg-brand-500/5 shadow-glow" : "border-slate-300 hover:border-brand-400 dark:border-white/15")}>
        <input ref={input} type="file" multiple hidden accept=".pdf,.md,.markdown,.txt,.rst" onChange={(e) => { if (e.target.files) upload(e.target.files); e.target.value = ""; }} />
        {uploading ? <Spinner className="h-8 w-8 text-brand-500" /> : <UploadCloud className="h-8 w-8 text-brand-500" />}
        <div className="font-medium">{uploading ? "Uploading…" : "Drop files here, or click to browse"}</div>
        <div className="text-xs text-slate-500">PDF · MD · TXT · RST — up to 50 MB each</div>
      </div>
      {docs === null && !error && <div className="space-y-2">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-16" />)}</div>}
      {docs && docs.length === 0 && <div className="card"><Empty icon={<Library className="h-5 w-5" />} title="Your library is empty" hint="Upload a few documents to start researching. Try the files in the samples/ folder." /></div>}
      {docs && docs.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead className="border-b border-slate-200/70 dark:border-white/10"><tr><th className="th">Document</th><th className="th hidden sm:table-cell">Pages</th><th className="th hidden sm:table-cell">Chunks</th><th className="th">Status</th><th className="th hidden md:table-cell">Added</th><th className="th" /></tr></thead>
            <tbody className="divide-y divide-slate-200/60 dark:divide-white/5">
              {docs.map((d) => (
                <tr key={d.id} className="transition hover:bg-slate-50 dark:hover:bg-white/[0.03]">
                  <td className="td"><div className="flex items-center gap-2.5"><FileText className="h-4 w-4 shrink-0 text-slate-400" />
                    <div className="min-w-0"><div className="truncate font-medium">{d.title}</div><div className="truncate text-xs text-slate-500">{d.filename}</div></div></div>
                    {d.error && <div className="mt-1 text-xs text-rose-600">{d.error}</div>}</td>
                  <td className="td hidden tabular-nums sm:table-cell">{d.num_pages || "—"}</td>
                  <td className="td hidden tabular-nums sm:table-cell">{d.num_chunks || "—"}</td>
                  <td className="td">{d.status === "ready" ? <Badge tone="green"><CheckCircle2 className="h-3 w-3" /> ready</Badge> : d.status === "failed" ? <Badge tone="red"><XCircle className="h-3 w-3" /> failed</Badge> : <Badge tone="amber"><Spinner className="h-3 w-3" /> {d.status}</Badge>}</td>
                  <td className="td hidden text-xs text-slate-500 md:table-cell">{ago(d.created_at)}</td>
                  <td className="td text-right"><button onClick={() => remove(d)} className="rounded-lg p-1.5 text-slate-400 transition hover:bg-rose-500/10 hover:text-rose-600" aria-label={`Delete ${d.title}`}><Trash2 className="h-4 w-4" /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
