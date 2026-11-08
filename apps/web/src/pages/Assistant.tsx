import { useQueryClient } from "@tanstack/react-query";
import { Bot, FileSignature, Send, Sparkles } from "lucide-react";
import { useState } from "react";
import Markdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";
import { Badge, Button, Card, ErrorBox, Select, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi, useMe } from "@/lib/hooks";

interface Ev { id: string; type: string; key: string; text: string; source: string; revision: string; span: { line_start?: number } }
interface Turn { role: "user" | "assistant"; content: string; meta?: { model: string; grounded: boolean; citations: string[]; invalid_citations: string[]; evidence: Ev[]; latency_ms: number } }

/** Model picker (AT-LLM_GATEWAY): Luna default, Terra, Sol — validated server-side. */
export function ModelPicker({ value, onChange }: { value: string; onChange: (m: string) => void }) {
  const models = useApi<{ default: string; models: { alias: string; label: string }[] }>(["models"], "/ai/models");
  return <Select aria-label="Model" value={value || models.data?.default || ""} onChange={(e) => onChange(e.target.value)}>
    {models.data?.models.map((m) => <option key={m.alias} value={m.alias}>{m.label}</option>)}</Select>;
}

export function AssistantPage({ projectId }: { projectId: string }) {
  const me = useMe();
  const qc = useQueryClient();
  const [model, setModel] = useState(me.data?.preferences.preferred_model ?? "");
  const [mode, setMode] = useState<"ask" | "design">("ask");
  const [q, setQ] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const send = async (question: string) => {
    setBusy(true); setErr(null);
    const hist = turns.map((t) => ({ role: t.role, content: t.content }));
    setTurns((t) => [...t, { role: "user", content: question }]);
    try {
      const r = await api<any>(`/projects/${projectId}/assistant/ask`, { method: "POST", json: { question, model: model || null, mode, history: hist } });
      setTurns((t) => [...t, { role: "assistant", content: r.answer, meta: r }]);
    } catch (e) { setErr(e); } finally { setBusy(false); }
  };
  const draft = async () => {
    const last = [...turns].reverse().find((t) => t.role === "user")?.content ?? q;
    if (!last) return toast.error("Ask or describe the decision first");
    setBusy(true);
    try {
      const r = await api<any>(`/projects/${projectId}/assistant/draft-adr`, { method: "POST", json: { question: last, model: model || null } });
      toast.success(`ADR-${String(r.adr.number).padStart(4, "0")} drafted as proposed — review it in Decisions`);
      qc.invalidateQueries({ queryKey: ["adrs", projectId] });
    } catch (e) { toast.error((e as Error).message); } finally { setBusy(false); }
  };
  const SUGGEST = mode === "ask" ? ["Which containers write to the main database?", "How does the web app reach the API?", "Which external systems does this depend on, and through what?", "What does the AI gateway connect to?"]
    : ["How do I connect the worker to a new search service?", "How should a new notification service integrate with the platform?"];
  return <div className="grid h-full gap-4 p-6 xl:grid-cols-[1fr_380px]">
    <Card className="flex min-h-[70vh] flex-col" eyebrow="Grounded in this project's evidence only" title={<span className="flex items-center gap-2"><Bot size={18} /> Architecture assistant</span>}
      actions={<><Select aria-label="Mode" value={mode} onChange={(e) => setMode(e.target.value as "ask" | "design")}><option value="ask">Ask</option><option value="design">Integration design</option></Select>
        <ModelPicker value={model} onChange={(m) => { setModel(m); api("/me/preferences", { method: "PUT", json: { preferred_model: m } }).catch(() => undefined); }} /></>}>
      <div className="flex-1 space-y-4 overflow-auto">
        {turns.length === 0 && <div className="space-y-2"><p className="text-sm text-muted">Answers cite evidence like <code>[E3]</code>; missing evidence is reported as UNKNOWN, never as absence.</p>
          <div className="flex flex-wrap gap-2">{SUGGEST.map((s) => <button key={s} onClick={() => setQ(s)} className="rounded-full border border-rule px-3 py-1 text-xs hover:border-muted">{s}</button>)}</div></div>}
        {turns.map((t, i) => <div key={i} className={t.role === "user" ? "ml-auto max-w-[80%] rounded-lg bg-ink px-3 py-2 text-sm text-paper" : "max-w-full"}>
          {t.role === "user" ? t.content : <div>
            <div className="mb-1 flex flex-wrap gap-2"><Badge tone={t.meta?.grounded ? "ok" : "warn"}>{t.meta?.grounded ? "grounded" : "not grounded"}</Badge><Badge>{t.meta?.model}</Badge>
              {t.meta?.invalid_citations?.length ? <Badge tone="bad">{t.meta.invalid_citations.length} invalid citations removed</Badge> : null}<span className="text-[10px] text-soft">{t.meta?.latency_ms} ms</span></div>
            <article className="prose-at text-sm"><Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>{t.content}</Markdown></article>
            {t.meta?.evidence?.length ? <details className="mt-2"><summary className="cursor-pointer text-xs text-link">Evidence ({t.meta.evidence.length})</summary>
              <ul className="mt-1 space-y-1 text-xs">{t.meta.evidence.map((e) => <li key={e.id} className="rounded border border-rule p-1.5"><b className="font-mono">[{e.id}]</b> <Badge>{e.type}</Badge> {e.text.slice(0, 220)}
                <div className="font-mono text-[10px] text-soft">{e.source}{e.span?.line_start ? `:${e.span.line_start}` : ""} {e.revision ? `@ ${e.revision.slice(0, 10)}` : ""}</div></li>)}</ul></details> : null}
          </div>}
        </div>)}
        {busy && <p className="text-sm text-soft">Thinking with {model || "gpt-6-luna"}…</p>}
        <ErrorBox error={err} />
      </div>
      <form className="mt-3 flex items-end gap-2" onSubmit={(e) => { e.preventDefault(); if (q.trim()) { void send(q.trim()); setQ(""); } }}>
        <Textarea aria-label="Question" rows={2} value={q} onChange={(e) => setQ(e.target.value)} placeholder={mode === "ask" ? "Ask about this architecture…" : "How do I connect A and B?"}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); (e.currentTarget.form as HTMLFormElement).requestSubmit(); } }} />
        <Button variant="primary" disabled={busy || !q.trim()}><Send size={14} /> Send</Button>
      </form>
    </Card>
    <Card eyebrow="Drafting" title={<span className="flex items-center gap-2"><Sparkles size={16} /> Turn it into a decision</span>}>
      <p className="text-sm text-muted">Draft a MADR ADR from the last question and this project's evidence. The draft is <b>proposed</b> and flagged as AI-generated; a different person must approve it.</p>
      <Button className="mt-3" onClick={draft} disabled={busy}><FileSignature size={14} /> Draft ADR</Button>
    </Card>
  </div>;
}
