import { ChevronDown, ChevronRight, MessageSquare, Send, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Badge, Button, ErrorBox, cn } from "@/components/ui";
import { CostEstimate, modelLabel } from "@/components/CostEstimate";
import { RichMarkdown } from "@/components/RichMarkdown";
import { api } from "@/lib/api";

export interface AskMatch { ref: string; id: string; title: string; score: number; kind?: string; status?: string; path?: string; heading?: string;
  line_start?: number; excerpt?: string; flow?: any }
interface AskResult { page: string; question: string; answer: string; ai: boolean; cached?: boolean; reason?: string; model?: string;
  reasoning_effort?: string; cost_usd: number; matches: AskMatch[]; citations?: string[] }
type Page = "flows" | "decisions" | "docs";

const COPY: Record<Page, { title: string; placeholder: string; none: string; noun: string }> = {
  flows: { title: "Ask the flows", placeholder: "e.g. what happens when a user places an order?", none: "No recognized flow matches these words.", noun: "flows" },
  decisions: { title: "Ask the decisions", placeholder: "e.g. is caching part of any decision?", none: "No decision record mentions this — it is not covered by any ADR yet.", noun: "decisions" },
  docs: { title: "Ask the docs", placeholder: "e.g. how do I deploy the ingest service?", none: "No documentation passage matches.", noun: "passages" },
};

/** Chat-like search over one page's items. Search always runs (no tokens); a short cited AI answer is added on top. */
export function PageAsk({ projectId, page, onPick, selected }: { projectId: string; page: Page; onPick: (m: AskMatch) => void; selected?: string | null }) {
  const [open, setOpen] = useState(() => { try { return localStorage.getItem(`archtwin.ask.${page}`) !== "0"; } catch { return true; } });
  const [q, setQ] = useState("");
  const [useAi, setUseAi] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [log, setLog] = useState<AskResult[]>([]);
  const end = useRef<HTMLDivElement>(null);
  const c = COPY[page];
  useEffect(() => { try { localStorage.setItem(`archtwin.ask.${page}`, open ? "1" : "0"); } catch { /* storage unavailable */ } }, [open, page]);
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [log.length]);
  const send = async () => {
    const question = q.trim();
    if (question.length < 2 || busy) return;
    setBusy(true); setErr(null);
    try {
      const r = await api<AskResult>(`/projects/${projectId}/ask`, { method: "POST", json: { page, question, ai: useAi } });
      setLog((l) => [...l.slice(-9), r]); setQ("");
      if (r.matches[0]) onPick(r.matches[0]);
    } catch (e) { setErr(e); } finally { setBusy(false); }
  };
  return <section className="rounded-xl border border-rule bg-card shadow-card" aria-label={c.title}>
    <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
      className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm font-medium hover:bg-paper-2">
      {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}<MessageSquare size={14} className="text-link" />{c.title}
      {log.length > 0 && <span className="text-xs font-normal text-soft">· {log.length} question{log.length === 1 ? "" : "s"}</span>}</button>
    {open && <div className="space-y-3 border-t border-rule px-4 py-3">
      {log.length > 0 && <ol className="max-h-[420px] space-y-3 overflow-auto pr-1">{log.map((r, i) => <li key={i} className="space-y-1.5">
        <div className="ml-auto w-fit max-w-[90%] rounded-lg bg-paper-2 px-3 py-1.5 text-sm">{r.question}</div>
        {r.answer ? <RichMarkdown className="text-sm">{r.answer}</RichMarkdown>
          : <p className="text-sm text-muted">{r.matches.length ? `${r.matches.length} matching ${c.noun}${r.reason === "ai_off" ? " (AI is off)" : ""}:` : c.none}</p>}
        {r.matches.length > 0 && <ul className="flex flex-wrap gap-1.5">{r.matches.map((m) => <li key={m.ref}>
          <button type="button" onClick={() => onPick(m)} title={m.excerpt ?? m.title}
            className={cn("flex max-w-[22rem] items-center gap-1 rounded-md border px-2 py-0.5 text-left text-xs hover:border-link",
              selected === m.id ? "border-link bg-link/10" : "border-rule", r.citations?.includes(m.ref) && "font-medium")}>
            <span className="font-mono text-soft">{m.ref}</span><span className="truncate">{m.title}</span>
            {m.status && <Badge>{m.status}</Badge>}</button></li>)}</ul>}
        {r.ai && <div className="text-[10px] text-soft">{modelLabel(r.model ?? "")}{r.reasoning_effort ? ` · ${r.reasoning_effort}` : ""}
          {r.cached ? " · cached answer, no tokens used" : ` · $${r.cost_usd.toFixed(4)}`}</div>}
      </li>)}<div ref={end} /></ol>}
      <ErrorBox error={err} />
      <form className="flex items-end gap-2" onSubmit={(e) => { e.preventDefault(); void send(); }}>
        <textarea aria-label={c.title} rows={1} value={q} placeholder={c.placeholder} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); } }}
          className="min-h-[38px] flex-1 resize-none rounded-lg border border-rule bg-card px-3 py-2 text-sm outline-none focus:border-link" />
        <Button variant="primary" size="sm" disabled={busy || q.trim().length < 2}><Send size={13} /> {busy ? "Searching…" : "Ask"}</Button>
      </form>
      <div className="flex flex-wrap items-center gap-3 text-[11px] text-soft">
        <label className="flex items-center gap-1"><input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} />
          <Sparkles size={11} /> explain with AI</label>
        {useAi ? <CostEstimate operation={page === "flows" ? "flow_explain" : "page_ask"} text={q} /> : <span>search only · no tokens</span>}
      </div>
    </div>}
  </section>;
}
