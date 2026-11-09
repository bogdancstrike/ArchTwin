import { useQueryClient } from "@tanstack/react-query";
import { Bot, Check, Copy, Database, FileSignature, MessageSquare, PanelLeftClose, PanelLeftOpen, Plus, Send, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Badge, Button, ErrorBox, Select, ago, cn } from "@/components/ui";
import { usd } from "@/components/charts";
import { RichMarkdown } from "@/components/RichMarkdown";
import { api } from "@/lib/api";
import { useApi, useMe } from "@/lib/hooks";
import type { View } from "@/lib/types";
import { MiniDiagram } from "@/diagram/MiniDiagram";

type Scope = "general" | "data";
interface Ev { id: string; type: string; key: string; text: string; source: string; revision: string; span: { line_start?: number } }
interface Meta { diagram?: View | null; model: string; grounded: boolean; citations: string[]; invalid_citations?: string[]; evidence: Ev[]; latency_ms: number; cost_usd?: number; scope: Scope }
interface Turn { role: "user" | "assistant"; content: string; scope: Scope; meta?: Meta }
interface Conv { id: string; title: string; scope: Scope; sources: string[]; turns: number; updated_at: string }
interface Source { id: string; name: string; kind: string }

/** Model picker (AT-LLM_GATEWAY): Luna default, Terra, Sol — validated server-side. */
export function ModelPicker({ value, onChange }: { value: string; onChange: (m: string) => void }) {
  const models = useApi<{ default: string; models: { alias: string; label: string }[] }>(["models"], "/ai/models");
  return <Select aria-label="Model" value={value || models.data?.default || ""} onChange={(e) => onChange(e.target.value)}>
    {models.data?.models.map((m) => <option key={m.alias} value={m.alias}>{m.label}</option>)}</Select>;
}

const SUGGEST: Record<string, string[]> = {
  data: ["Which containers write to the main database?", "How does the web app reach the API?", "Which external systems does this depend on, and through what?",
    "What do the ADRs say about data storage?"],
  design: ["How do I connect the worker to a new search service?", "How should a new notification service integrate with the platform?"],
  general: ["Explain the trade-offs of event sourcing vs CRUD", "When should I split a monolith into services?", "Write a checklist for an architecture review"],
};
const SCOPE_TAG: Record<Scope, string> = { general: "General · no project data", data: "Data · project evidence" };

function SourcePicker({ projectId, value, onChange }: { projectId: string; value: string[]; onChange: (v: string[]) => void }) {
  const [open, setOpen] = useState(false);
  const src = useApi<Source[]>(["ai-sources", projectId], `/projects/${projectId}/assistant/sources`);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    window.addEventListener("mousedown", h);
    return () => window.removeEventListener("mousedown", h);
  }, [open]);
  return <div className="relative" ref={ref}>
    <Button size="sm" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="listbox"><Database size={13} /> {value.length ? `${value.length} source(s)` : "All project sources"}</Button>
    {open && <div role="listbox" aria-multiselectable="true" aria-label="Datasources for this answer" className="absolute right-0 z-20 mt-1 w-72 rounded-lg border border-rule bg-card p-1.5 shadow-lift">
      <button className={cn("mb-1 flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm", !value.length ? "bg-paper-2 font-medium" : "hover:bg-paper-2")}
        onClick={() => onChange([])}>{!value.length && <Check size={14} className="text-ok" />}<span className="flex-1">All datasources in this project</span></button>
      {(src.data ?? []).map((s) => { const on = value.includes(s.id);
        return <button key={s.id} role="option" aria-selected={on} onClick={() => onChange(on ? value.filter((x) => x !== s.id) : [...value, s.id])}
          className={cn("flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-paper-2", on && "bg-paper-2")}>
          <Database size={13} className="shrink-0 text-soft" /><span className="min-w-0 flex-1 truncate">{s.name}</span><span className="text-[10px] text-soft">{s.kind}</span>
          {on && <Check size={14} className="text-ok" />}</button>; })}
      {src.data && src.data.length <= 2 && <p className="p-2 text-xs text-soft">Add datasources in the Datasources tab.</p>}
    </div>}
  </div>;
}

function AnswerFooter({ t }: { t: Turn }) {
  const [copied, setCopied] = useState(false);
  return <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px] text-soft">
    <button className="flex items-center gap-1 rounded px-1 py-0.5 hover:bg-paper-2 hover:text-ink" onClick={() => { void navigator.clipboard.writeText(t.content); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
      {copied ? <Check size={11} /> : <Copy size={11} />} {copied ? "Copied" : "Copy"}</button>
    {t.meta?.cost_usd !== undefined && <span title="Estimated cost of this answer (tokens × price, LiteLLM-verified)">est. {usd(t.meta.cost_usd)}</span>}
    {t.meta?.latency_ms !== undefined && <span>{(t.meta.latency_ms / 1000).toFixed(1)} s</span>}
    {t.meta?.model && <span className="font-mono">{t.meta.model}</span>}
  </div>;
}

export function AssistantPage({ projectId }: { projectId: string }) {
  const me = useMe();
  const qc = useQueryClient();
  const [model, setModel] = useState(me.data?.preferences.preferred_model ?? "");
  const [scope, setScope] = useState<Scope>("data");
  const [mode, setMode] = useState<"ask" | "design">("ask");
  const [sources, setSources] = useState<string[]>([]);
  const [convId, setConvId] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [side, setSide] = useState(true);
  const endRef = useRef<HTMLDivElement>(null);
  const convs = useApi<Conv[]>(["conversations", projectId], `/projects/${projectId}/assistant/conversations`);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" }); }, [turns.length, busy]);

  const open = async (c: Conv) => {
    setErr(null);
    const d = await api<any>(`/projects/${projectId}/assistant/conversations/${c.id}`);
    setConvId(c.id); setScope(d.scope); setSources(d.sources ?? []);
    setTurns(d.turns.flatMap((t: any) => [{ role: "user", content: t.question, scope: t.scope ?? d.scope },
      { role: "assistant", content: t.answer, scope: t.scope ?? d.scope, meta: { model: t.model, grounded: t.grounded, citations: t.citations,
        evidence: (t.evidence ?? []).filter((e: any) => e.type !== "diagram"), diagram: (t.evidence ?? []).find((e: any) => e.type === "diagram")?.view ?? null,
        latency_ms: t.latency_ms, scope: t.scope ?? d.scope } }]));
  };
  const fresh = () => { setConvId(null); setTurns([]); setErr(null); setQ(""); };
  const remove = async (c: Conv) => {
    if (!confirm(`Delete “${c.title}”?`)) return;
    await api(`/projects/${projectId}/assistant/conversations/${c.id}`, { method: "DELETE" });
    if (convId === c.id) fresh();
    void qc.invalidateQueries({ queryKey: ["conversations", projectId] });
  };
  const send = async (question: string) => {
    setBusy(true); setErr(null);
    setTurns((t) => [...t, { role: "user", content: question, scope }]);
    try {
      const r = await api<any>(`/projects/${projectId}/assistant/ask`, { method: "POST", json: {
        question, model: model || null, mode: scope === "data" ? mode : "ask", scope, sources: scope === "data" && sources.length ? sources : null, conversation_id: convId } });
      setConvId(r.conversation_id);
      setTurns((t) => [...t, { role: "assistant", content: r.answer, scope, meta: r }]);
      void qc.invalidateQueries({ queryKey: ["conversations", projectId] });
      void qc.invalidateQueries({ queryKey: ["usage-ov"] });
    } catch (e) { setErr(e); setTurns((t) => t.slice(0, -1)); setQ(question); } finally { setBusy(false); }
  };
  const draft = async () => {
    const last = [...turns].reverse().find((t) => t.role === "user")?.content ?? q;
    if (!last) return toast.error("Ask or describe the decision first");
    setBusy(true);
    try {
      const r = await api<any>(`/projects/${projectId}/assistant/draft-adr`, { method: "POST", json: { question: last, model: model || null } });
      toast.success(`ADR-${String(r.adr.number).padStart(4, "0")} drafted as proposed — review it in Decisions`);
      void qc.invalidateQueries({ queryKey: ["adrs", projectId] });
    } catch (e) { toast.error((e as Error).message); } finally { setBusy(false); }
  };
  const suggestions = scope === "general" ? SUGGEST.general : mode === "design" ? SUGGEST.design : SUGGEST.data;

  return <div className="flex h-full min-h-[70vh]">
    {side && <aside aria-label="Conversations" className="flex w-64 shrink-0 flex-col border-r border-rule bg-card/60">
      <div className="flex items-center gap-1 p-2"><Button className="flex-1 justify-center" variant="primary" onClick={fresh}><Plus size={14} /> New chat</Button>
        <Button variant="ghost" aria-label="Hide conversations" onClick={() => setSide(false)}><PanelLeftClose size={15} /></Button></div>
      <ul className="flex-1 space-y-0.5 overflow-auto px-2 pb-2">
        {convs.data?.length === 0 && <li className="p-3 text-xs text-soft">No conversations yet.</li>}
        {convs.data?.map((c) => <li key={c.id} className="group relative">
          <button onClick={() => void open(c)} className={cn("w-full rounded-lg px-2.5 py-2 pr-8 text-left", convId === c.id ? "bg-paper-2" : "hover:bg-paper-2")}>
            <span className="block truncate text-sm">{c.title || "Untitled"}</span>
            <span className="block text-[11px] text-soft">{c.scope === "general" ? "General" : "Data"} · {c.turns} turn{c.turns === 1 ? "" : "s"} · {ago(c.updated_at)}</span></button>
          <button aria-label={`Delete ${c.title}`} onClick={() => void remove(c)} className="absolute right-1.5 top-2 rounded p-1 text-soft opacity-0 hover:bg-card hover:text-bad focus:opacity-100 group-hover:opacity-100"><Trash2 size={13} /></button>
        </li>)}
      </ul>
    </aside>}
    <section className="flex min-w-0 flex-1 flex-col">
      <header className="flex flex-wrap items-center gap-2 border-b border-rule px-4 py-2.5">
        {!side && <Button variant="ghost" aria-label="Show conversations" onClick={() => setSide(true)}><PanelLeftOpen size={15} /></Button>}
        <div role="radiogroup" aria-label="Scope" className="flex rounded-lg border border-rule bg-card p-0.5 text-sm">
          {([["general", "General", MessageSquare], ["data", "Data", Database]] as const).map(([s, l, I]) => <button key={s} role="radio" aria-checked={scope === s}
            onClick={() => setScope(s)} data-testid={`scope-${s}`} className={cn("flex items-center gap-1.5 rounded-md px-3 py-1", scope === s ? "bg-ink text-paper" : "text-muted hover:text-ink")}>
            <I size={13} />{l}</button>)}</div>
        {scope === "data" && <><SourcePicker projectId={projectId} value={sources} onChange={setSources} />
          <Select aria-label="Mode" value={mode} onChange={(e) => setMode(e.target.value as "ask" | "design")}><option value="ask">Ask</option><option value="design">Integration design</option></Select></>}
        <span className="ml-auto flex items-center gap-2"><ModelPicker value={model} onChange={(m) => { setModel(m); api("/me/preferences", { method: "PUT", json: { preferred_model: m } }).catch(() => undefined); }} />
          <Button onClick={draft} disabled={busy} title="Draft a MADR ADR from the last question and this project's evidence (proposed; another person approves)"><FileSignature size={14} /> Draft ADR</Button></span>
      </header>
      <div className="flex-1 space-y-5 overflow-auto px-4 py-5 md:px-8">
        {turns.length === 0 && <div className="mx-auto max-w-2xl pt-10 text-center">
          <Sparkles size={28} className="mx-auto text-accent" />
          <h2 className="serif mt-2 text-3xl">{scope === "general" ? "Ask anything about architecture" : "Ask this project"}</h2>
          <p className="mt-1 text-sm text-muted">{scope === "general" ? "General chat uses the model’s own knowledge — it never sees this project’s code, docs or datasources."
            : <>Answers use only this project’s evidence{sources.length ? " from the selected datasources" : ""} and cite it like <code>[E3]</code>; missing evidence is UNKNOWN, never absence.</>}</p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">{suggestions.map((s) => <button key={s} onClick={() => setQ(s)} className="rounded-full border border-rule px-3 py-1 text-xs hover:border-muted">{s}</button>)}</div>
        </div>}
        {turns.map((t, i) => t.role === "user"
          ? <div key={i} className="ml-auto max-w-[80%]"><div className="mb-0.5 text-right text-[10px] uppercase tracking-wide text-soft">{SCOPE_TAG[t.scope]}</div>
              <div className="rounded-lg bg-ink px-3 py-2 text-sm text-paper">{t.content}</div></div>
          : <div key={i} className="max-w-full">
              <div className="mb-1 flex flex-wrap items-center gap-2"><Bot size={15} className="text-accent" />
                {t.scope === "general" ? <Badge tone="muted">general · not grounded in project data</Badge> : <Badge tone={t.meta?.grounded ? "ok" : "warn"}>{t.meta?.grounded ? "grounded" : "not grounded"}</Badge>}
                {t.meta?.invalid_citations?.length ? <Badge tone="bad">{t.meta.invalid_citations.length} invalid citations removed</Badge> : null}</div>
              <RichMarkdown className="text-sm">{t.content}</RichMarkdown>
              {t.meta?.diagram && <MiniDiagram view={t.meta.diagram} projectId={projectId} />}
              {t.meta?.evidence?.length ? <details className="mt-2"><summary className="cursor-pointer text-xs text-link">Evidence ({t.meta.evidence.length})</summary>
                <ul className="mt-1 space-y-1 text-xs">{t.meta.evidence.map((e) => <li key={e.id} className="rounded border border-rule p-1.5"><b className="font-mono">[{e.id}]</b> <Badge>{e.type}</Badge> {e.text.slice(0, 220)}
                  <div className="font-mono text-[10px] text-soft">{e.source}{e.span?.line_start ? `:${e.span.line_start}` : ""} {e.revision ? `@ ${e.revision.slice(0, 10)}` : ""}</div></li>)}</ul></details> : null}
              <AnswerFooter t={t} />
            </div>)}
        {busy && <p className="text-sm text-soft">Thinking with {model || "gpt-6-luna"}…</p>}
        <ErrorBox error={err} />
        <div ref={endRef} />
      </div>
      <form className="border-t border-rule px-4 py-3" onSubmit={(e) => { e.preventDefault(); if (q.trim() && !busy) { void send(q.trim()); setQ(""); } }}>
        <div className="flex items-end gap-2">
          <textarea aria-label="Question" rows={1} value={q} onChange={(e) => { setQ(e.target.value); e.target.style.height = "auto"; e.target.style.height = `${Math.min(220, e.target.scrollHeight)}px`; }}
            placeholder={scope === "general" ? "Ask a general architecture question…" : mode === "ask" ? "Ask about this project’s architecture…" : "How do I connect A and B?"}
            className="max-h-56 min-h-[42px] flex-1 resize-none rounded-lg border border-rule bg-card px-3 py-2.5 text-sm outline-none focus:border-link"
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); (e.currentTarget.form as HTMLFormElement).requestSubmit(); } }} />
          <Button variant="primary" disabled={busy || !q.trim()}><Send size={14} /> Send</Button>
        </div>
        <p className="mt-1.5 text-[11px] text-soft">{scope === "general" ? "General: no project data is sent to the model." : "Data: only evidence you can access in this project is sent, as untrusted context."} Enter to send · Shift+Enter for a new line.</p>
      </form>
    </section>
  </div>;
}
