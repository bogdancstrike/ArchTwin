import { Check, ChevronDown, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState, type TextareaHTMLAttributes } from "react";
import Markdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { Button, ErrorBox, Input, Textarea, cn } from "@/components/ui";
import { usd } from "@/components/charts";
import { api } from "@/lib/api";

type Mode = "extend" | "improve" | "concise";
const MODES: [Mode, string, string][] = [["extend", "Extend my text", "keep it, make it richer"], ["improve", "Improve wording", "same meaning, clearer"],
  ["concise", "Make concise", "shorter, same points"]];

/** A textarea with "Extend with AI": the model suggests, the user reviews and decides (never applied automatically). */
export function AiTextarea({ projectId, value, onChange, field, title, ...rest }: Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "onChange" | "value"> & {
  projectId: string; value: string; onChange: (v: string) => void; field: string; title?: string;
}) {
  const [menu, setMenu] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [instruction, setInstruction] = useState("");
  const [grounded, setGrounded] = useState(true);
  const [sugg, setSugg] = useState<{ text: string; cost_usd: number; model: string; citations: string[] } | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!menu) return;
    const h = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setMenu(false); };
    window.addEventListener("mousedown", h);
    return () => window.removeEventListener("mousedown", h);
  }, [menu]);
  const run = async (mode: Mode) => {
    setMenu(false); setBusy(true); setErr(null);
    try {
      setSugg(await api(`/projects/${projectId}/assistant/extend`, { method: "POST", json: { text: value, mode, field, title: title ?? "", instruction, grounded } }));
    } catch (e) { setErr(e); } finally { setBusy(false); }
  };
  return <div>
    <div className="relative">
      <Textarea {...rest} value={value} onChange={(e) => onChange(e.target.value)} />
      <div ref={ref} className="absolute bottom-1.5 right-1.5">
        <button type="button" disabled={busy || !value.trim()} onClick={() => setMenu((m) => !m)} aria-haspopup="menu" aria-expanded={menu}
          title={value.trim() ? "Extend with AI" : "Write something first"} aria-label={`Extend ${field} with AI`}
          className="flex items-center gap-1 rounded-md border border-rule bg-card px-1.5 py-0.5 text-[11px] text-link shadow-card hover:border-link disabled:opacity-40">
          <Sparkles size={11} />{busy ? "Writing…" : "AI"}<ChevronDown size={10} /></button>
        {menu && <div role="menu" className="absolute bottom-full right-0 z-30 mb-1 w-72 rounded-lg border border-rule bg-card p-2 shadow-lift">
          {MODES.map(([m, l, h]) => <button type="button" role="menuitem" key={m} onClick={() => void run(m)} className="flex w-full flex-col rounded px-2 py-1.5 text-left hover:bg-paper-2">
            <span className="text-sm">{l}</span><span className="text-[11px] text-soft">{h}</span></button>)}
          <Input className="mt-1 text-xs" placeholder="Optional instruction (e.g. focus on cost)" aria-label="Instruction for the AI" value={instruction} onChange={(e) => setInstruction(e.target.value)} />
          <label className="mt-1.5 flex items-center gap-1.5 px-1 text-[11px] text-muted"><input type="checkbox" checked={grounded} onChange={(e) => setGrounded(e.target.checked)} />
            Use this project's evidence (cited)</label>
        </div>}
      </div>
    </div>
    <ErrorBox error={err} />
    {sugg && <div className="mt-1.5 rounded-lg border border-link/40 bg-link/5 p-2" aria-label="AI suggestion">
      <div className="mb-1 flex items-center gap-2 text-[11px] text-muted"><Sparkles size={11} className="text-link" /> Suggestion · {sugg.model} · est. {usd(sugg.cost_usd)}
        {sugg.citations.length > 0 && <span>· cites {sugg.citations.join(" ")}</span>}
        <span className="ml-auto flex gap-1"><Button type="button" size="sm" variant="primary" onClick={() => { onChange(sugg.text); setSugg(null); }}><Check size={12} /> Use this</Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => setSugg(null)}><X size={12} /> Discard</Button></span></div>
      <article className={cn("prose-at max-h-64 overflow-auto text-sm")}><Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>{sugg.text}</Markdown></article>
    </div>}
  </div>;
}
