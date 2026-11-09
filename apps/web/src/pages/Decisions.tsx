import { Bot, Check, Plus, Sparkles } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, Dialog, ErrorBox, Field, Input, Spinner, Textarea, ago } from "@/components/ui";
import { RichMarkdown } from "@/components/RichMarkdown";
import { api, download } from "@/lib/api";
import { useAction, useApi, useMe } from "@/lib/hooks";
import type { Adr } from "@/lib/types";
import { usd } from "@/components/charts";
import { DataTable } from "@/components/DataTable";
import { SplitLayout } from "@/components/SplitLayout";
import { CostEstimate, modelLabel } from "@/components/CostEstimate";
import { PageAsk } from "@/components/PageAsk";
import { ExportMenu } from "@/components/ExportMenu";

const TONE: Record<string, string> = { proposed: "warn", accepted: "ok", rejected: "bad", superseded: "muted" };

interface AdrOption { name: string; pros: string[]; cons: string[] }
interface AdrDraft { title: string; context: string; decision_drivers: string[]; considered_options: AdrOption[]; decision_outcome: string; consequences: string }
const FIELD_LABEL: Record<keyof AdrDraft, string> = { title: "Title", context: "Context and problem statement", decision_drivers: "Decision drivers",
  considered_options: "Considered options", decision_outcome: "Decision outcome", consequences: "Consequences" };

/** One AI pass over the whole ADR: reads every field, returns a completed MADR draft; the author picks which fields to apply. */
function CompleteWithAi({ projectId, current, onApply }: { projectId: string; current: () => Omit<AdrDraft, "considered_options"> & { considered_options: string[] };
  onApply: (d: Partial<AdrDraft>) => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [instruction, setInstruction] = useState("");
  const [grounded, setGrounded] = useState(true);
  const [res, setRes] = useState<{ fields: AdrDraft; model: string; cost_usd: number; citations: string[] } | null>(null);
  const [pick, setPick] = useState<Record<string, boolean>>({});
  const run = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await api<any>(`/projects/${projectId}/assistant/complete-adr`, { method: "POST", json: { ...current(), instruction, grounded } });
      setRes(r); setPick(Object.fromEntries(Object.keys(FIELD_LABEL).map((k) => [k, true])));
    } catch (e) { setErr(e); } finally { setBusy(false); }
  };
  const render = (k: keyof AdrDraft, v: AdrDraft[keyof AdrDraft]) => k === "considered_options"
    ? <ul className="space-y-1">{(v as AdrOption[]).map((o) => <li key={o.name}><b>{o.name}</b>
        {o.pros.length > 0 && <div className="text-ok">+ {o.pros.join("; ")}</div>}{o.cons.length > 0 && <div className="text-bad">− {o.cons.join("; ")}</div>}</li>)}</ul>
    : Array.isArray(v) ? <ul className="list-disc pl-4">{(v as string[]).map((x) => <li key={x}>{x}</li>)}</ul>
    : <div className="whitespace-pre-wrap">{v as string}</div>;
  return <div className="rounded-lg border border-link/30 bg-link/5 p-3">
    <div className="flex flex-wrap items-center gap-2">
      <Sparkles size={15} className="text-link" /><span className="text-sm font-medium">Complete with AI</span>
      <span className="text-xs text-muted">reads everything you wrote and completes every field (MADR)</span>
      <Input className="!w-64 text-xs" placeholder="Optional instruction (e.g. focus on cost)" aria-label="Instruction for the AI" value={instruction} onChange={(e) => setInstruction(e.target.value)} />
      <label className="flex items-center gap-1 text-xs text-muted"><input type="checkbox" checked={grounded} onChange={(e) => setGrounded(e.target.checked)} /> use project evidence</label>
      <Button type="button" size="sm" variant="primary" disabled={busy} onClick={run}>{busy ? "Writing…" : res ? "Regenerate" : "Complete"}</Button>
      <CostEstimate operation="adrs" text={JSON.stringify(current()) + instruction} />
    </div>
    <ErrorBox error={err} />
    {res && <div className="mt-3 space-y-2">
      <div className="text-[11px] text-soft">{modelLabel(res.model)} · cost {usd(res.cost_usd)}{res.citations.length ? ` · cites ${res.citations.join(" ")}` : ""} — choose the fields to apply</div>
      <ul className="max-h-96 space-y-2 overflow-auto">{(Object.keys(FIELD_LABEL) as (keyof AdrDraft)[]).map((k) => <li key={k} className="rounded border border-rule bg-card p-2 text-xs">
        <label className="mb-1 flex items-center gap-1.5 font-medium"><input type="checkbox" checked={!!pick[k]} onChange={(e) => setPick((p) => ({ ...p, [k]: e.target.checked }))} />{FIELD_LABEL[k]}</label>
        {render(k, res.fields[k])}</li>)}</ul>
      <div className="flex justify-end gap-2"><Button type="button" size="sm" variant="ghost" onClick={() => setRes(null)}>Discard</Button>
        <Button type="button" size="sm" variant="primary" onClick={() => { onApply(Object.fromEntries(Object.entries(res.fields).filter(([k]) => pick[k])) as Partial<AdrDraft>); setRes(null); }}>
          <Check size={12} /> Apply selected</Button></div>
    </div>}
  </div>;
}

function AdrForm({ projectId, open, onClose }: { projectId: string; open: boolean; onClose: () => void }) {
  const [f, setF] = useState({ title: "", context: "", decision_drivers: "", options: "", decision_outcome: "", consequences: "" });
  const [details, setDetails] = useState<Record<string, AdrOption>>({});        // pros/cons per option name (from the AI draft)
  const lines = (t: string) => t.split("\n").map((x) => x.trim()).filter(Boolean);
  const create = useAction(() => api(`/projects/${projectId}/adrs`, { method: "POST", json: { title: f.title, context: f.context,
    decision_drivers: lines(f.decision_drivers), considered_options: lines(f.options).map((name) => details[name] ?? { name }),
    decision_outcome: f.decision_outcome, consequences: f.consequences } }), [["adrs", projectId]], "ADR proposed");
  const apply = (d: Partial<AdrDraft>) => {
    setF((x) => ({ ...x, ...(d.title !== undefined && { title: d.title }), ...(d.context !== undefined && { context: d.context }),
      ...(d.decision_outcome !== undefined && { decision_outcome: d.decision_outcome }), ...(d.consequences !== undefined && { consequences: d.consequences }),
      ...(d.decision_drivers && { decision_drivers: d.decision_drivers.join("\n") }),
      ...(d.considered_options && { options: d.considered_options.map((o) => o.name).join("\n") }) }));
    if (d.considered_options) setDetails(Object.fromEntries(d.considered_options.map((o) => [o.name, o])));
  };
  return <Dialog open={open} onClose={onClose} title="New ADR (MADR)" wide>
    <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); await create.mutateAsync(undefined as never); onClose(); }}>
      <CompleteWithAi projectId={projectId} onApply={apply} current={() => ({ title: f.title, context: f.context, decision_drivers: lines(f.decision_drivers),
        considered_options: lines(f.options), decision_outcome: f.decision_outcome, consequences: f.consequences })} />
      <Field label="Title"><Input required value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
      <Field label="Context and problem statement"><Textarea rows={4} value={f.context} onChange={(e) => setF({ ...f, context: e.target.value })} /></Field>
      <div className="grid grid-cols-2 gap-3"><Field label="Decision drivers (one per line)"><Textarea rows={4} value={f.decision_drivers} onChange={(e) => setF({ ...f, decision_drivers: e.target.value })} /></Field>
        <Field label="Considered options (one per line)" hint={Object.keys(details).length ? "pros/cons from the AI draft are kept for these names" : undefined}>
          <Textarea rows={4} value={f.options} onChange={(e) => setF({ ...f, options: e.target.value })} /></Field></div>
      <Field label="Decision outcome"><Textarea rows={3} value={f.decision_outcome} onChange={(e) => setF({ ...f, decision_outcome: e.target.value })} /></Field>
      <Field label="Consequences"><Textarea rows={3} value={f.consequences} onChange={(e) => setF({ ...f, consequences: e.target.value })} /></Field>
      <ErrorBox error={create.error} /><div className="flex justify-end"><Button variant="primary">Propose</Button></div>
    </form></Dialog>;
}

function AdrView({ projectId, id }: { projectId: string; id: string }) {
  const me = useMe();
  const a = useApi<Adr>(["adr", id], `/projects/${projectId}/adrs/${id}`);
  const md = useApi<string>(["adr-md", id, a.data?.current?.version, a.data?.status], `/projects/${projectId}/adrs/${id}/markdown`);
  const decide = useAction((d: string) => api(`/projects/${projectId}/adrs/${id}/${d}`, { method: "POST", json: {} }), [["adr", id], ["adrs", projectId]], "Decision recorded");
  if (a.isLoading) return <Spinner />;
  if (a.error) return <ErrorBox error={a.error} />;
  const d = a.data!;
  const isAuthor = d.author_id === me.data?.id;
  return <div>
    <div className="mb-3 flex flex-wrap items-center gap-2"><Badge tone={TONE[d.status]}>{d.status}</Badge>{d.ai_drafted && <Badge tone="link"><Bot size={10} /> AI draft — review required</Badge>}
      <span className="text-xs text-soft">v{d.current?.version} · by {d.author}{d.approver && ` · decided by ${d.approver}`}</span>
      <div className="ml-auto flex gap-2">{d.status === "proposed" && <>
        <Button size="sm" variant="primary" disabled={isAuthor} title={isAuthor ? "The author cannot approve their own ADR" : ""} onClick={() => decide.mutate("accept")}>Accept</Button>
        <Button size="sm" variant="danger" disabled={isAuthor} onClick={() => decide.mutate("reject")}>Reject</Button></>}
        <Button size="sm" onClick={() => download(`/projects/${projectId}/adrs/${id}/markdown`, `ADR-${String(d.number).padStart(4, "0")}.md`)}>Markdown</Button></div></div>
    {isAuthor && d.status === "proposed" && <p className="mb-2 text-xs text-soft">Separation of duties: another approver must accept this ADR.</p>}
    <RichMarkdown>{md.data ?? ""}</RichMarkdown>
    {d.current?.content?.citations?.length > 0 && <div className="mt-3"><div className="eyebrow">Grounding</div><ul className="text-xs">{d.current!.content.citations.map((c: any) => <li key={c.id} className="font-mono">[{c.id}] {c.key} — {c.source}</li>)}</ul></div>}
  </div>;
}

export function DecisionsPage({ projectId }: { projectId: string }) {
  const [sel, setSel] = useState<string | null>(() => new URLSearchParams(window.location.search).get("adr"));   // deep link from Home
  const [open, setOpen] = useState(false);
  return <SplitLayout storageKey="decisions" title="Decision records" sideWidth="xl:w-[460px]" side={(toggle) => <div className="space-y-4">
    <PageAsk projectId={projectId} page="decisions" selected={sel} onPick={(m) => setSel(m.id)} />
    <Card eyebrow="MADR" title="Decision records" actions={<><ExportMenu projectId={projectId} resource="decisions" label="All" /><Button size="sm" variant="primary" onClick={() => setOpen(true)}><Plus size={14} /> New</Button>{toggle}</>}>
      <DataTable<Adr> queryKey={["adrs", projectId]} endpoint={`/projects/${projectId}/adrs`} rowKey={(a) => a.id} defaultSort="number" defaultDir="desc"
        searchPlaceholder="Search decisions" selected={sel} onRowClick={(a) => setSel(a.id)}
        filters={[{ key: "status", label: "Status", options: [["proposed", "Proposed"], ["accepted", "Accepted"], ["rejected", "Rejected"], ["superseded", "Superseded"]] }]}
        empty="No ADRs. Propose one, or ask the assistant to draft it from evidence."
        columns={[{ key: "number", label: "#", sortable: true, render: (a) => <span className="font-mono text-xs">{String(a.number).padStart(4, "0")}</span> },
          { key: "title", label: "Title", sortable: true, render: (a) => <>{a.title}{a.ai_drafted && <Bot size={11} className="ml-1 inline text-link" />}<div className="text-[10px] text-soft">{ago(a.created_at)}</div></> },
          { key: "status", label: "Status", sortable: true, render: (a) => <Badge tone={TONE[a.status]}>{a.status}</Badge> }]} />
    </Card></div>}>
    <Card title="Record" actions={sel ? <ExportMenu projectId={projectId} resource="decisions" id={sel} label="Export ADR" /> : undefined}>{sel ? <AdrView projectId={projectId} id={sel} /> : <p className="text-sm text-soft">Select an ADR.</p>}</Card>
    <AdrForm projectId={projectId} open={open} onClose={() => setOpen(false)} />
  </SplitLayout>;
}
