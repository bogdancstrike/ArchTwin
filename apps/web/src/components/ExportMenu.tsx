import { ChevronDown, Download, FileArchive, FileCode2, FileText, FileType2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button, cn } from "@/components/ui";
import { download } from "@/lib/api";

export type ExportResource = "architecture" | "flows" | "drift" | "decisions" | "docs";
const FORMATS = [
  { key: "md", label: "Markdown", hint: ".md · diagrams as Mermaid", icon: FileCode2 },
  { key: "docx", label: "Word", hint: ".docx", icon: FileText },
  { key: "pdf", label: "PDF", hint: ".pdf", icon: FileType2 },
  { key: "zip", label: "ZIP bundle", hint: "every item + all formats + manifest", icon: FileArchive },
] as const;

/** Export a page (or one item of it) as Markdown, DOCX, PDF or a ZIP bundle — server-rendered, audited. */
export function ExportMenu({ projectId, resource, id, params, label = "Export", size = "sm", className }: {
  projectId: string; resource: ExportResource; id?: string | null; params?: Record<string, string | undefined>; label?: string;
  size?: "sm" | "md"; className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", close); window.addEventListener("keydown", close);
    return () => { window.removeEventListener("mousedown", close); window.removeEventListener("keydown", close); };
  }, [open]);
  const run = async (fmt: string) => {
    setBusy(fmt); setOpen(false);
    const q = new URLSearchParams(Object.entries({ format: fmt, id: id ?? undefined, ...params }).filter((e): e is [string, string] => !!e[1]));
    try {
      await download(`/projects/${projectId}/export/${resource}?${q}`, `${resource}${id ? `-${id.slice(0, 24)}` : ""}.${fmt}`);
    } catch (e) { toast.error((e as Error).message); } finally { setBusy(null); }
  };
  return <div ref={ref} className={cn("relative inline-block", className)}>
    <Button type="button" size={size} disabled={!!busy} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}>
      <Download size={13} /> {busy ? `Exporting ${busy}…` : label} <ChevronDown size={12} /></Button>
    {open && <div role="menu" className="absolute right-0 z-40 mt-1 w-60 rounded-lg border border-rule bg-card p-1 shadow-lift">
      {FORMATS.map((f) => <button key={f.key} role="menuitem" type="button" onClick={() => void run(f.key)}
        className="flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-paper-2">
        <f.icon size={14} className="mt-0.5 shrink-0 text-soft" /><span><span className="block">{f.label}</span>
          <span className="block text-[11px] text-soft">{f.hint}</span></span></button>)}
    </div>}
  </div>;
}
