import { Bot, Plus } from "lucide-react";
import { useState } from "react";
import Markdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { Badge, Button, Card, Dialog, ErrorBox, Field, Input, Spinner, ago } from "@/components/ui";
import { api, download } from "@/lib/api";
import { useAction, useApi, useMe } from "@/lib/hooks";
import type { Adr } from "@/lib/types";
import { AiTextarea } from "@/components/AiTextarea";
import { DataTable } from "@/components/DataTable";
import { SplitLayout } from "@/components/SplitLayout";

const TONE: Record<string, string> = { proposed: "warn", accepted: "ok", rejected: "bad", superseded: "muted" };

function AdrForm({ projectId, open, onClose }: { projectId: string; open: boolean; onClose: () => void }) {
  const [f, setF] = useState({ title: "", context: "", decision_drivers: "", options: "", decision_outcome: "", consequences: "" });
  const create = useAction(() => api(`/projects/${projectId}/adrs`, { method: "POST", json: { title: f.title, context: f.context,
    decision_drivers: f.decision_drivers.split("\n").filter(Boolean), considered_options: f.options.split("\n").filter(Boolean).map((name) => ({ name })),
    decision_outcome: f.decision_outcome, consequences: f.consequences } }), [["adrs", projectId]], "ADR proposed");
  return <Dialog open={open} onClose={onClose} title="New ADR (MADR)" wide>
    <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); await create.mutateAsync(undefined as never); onClose(); }}>
      <Field label="Title"><Input required value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
      <Field label="Context and problem statement"><AiTextarea projectId={projectId} field="Context and problem statement" title={f.title} rows={4} value={f.context} onChange={(v) => setF({ ...f, context: v })} /></Field>
      <div className="grid grid-cols-2 gap-3"><Field label="Decision drivers (one per line)"><AiTextarea projectId={projectId} field="Decision drivers (one per line)" title={f.title} rows={4} value={f.decision_drivers} onChange={(v) => setF({ ...f, decision_drivers: v })} /></Field>
        <Field label="Considered options (one per line)"><AiTextarea projectId={projectId} field="Considered options (one per line)" title={f.title} rows={4} value={f.options} onChange={(v) => setF({ ...f, options: v })} /></Field></div>
      <Field label="Decision outcome"><AiTextarea projectId={projectId} field="Decision outcome" title={f.title} rows={3} value={f.decision_outcome} onChange={(v) => setF({ ...f, decision_outcome: v })} /></Field>
      <Field label="Consequences"><AiTextarea projectId={projectId} field="Consequences" title={f.title} rows={3} value={f.consequences} onChange={(v) => setF({ ...f, consequences: v })} /></Field>
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
    <article className="prose-at"><Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>{md.data ?? ""}</Markdown></article>
    {d.current?.content?.citations?.length > 0 && <div className="mt-3"><div className="eyebrow">Grounding</div><ul className="text-xs">{d.current!.content.citations.map((c: any) => <li key={c.id} className="font-mono">[{c.id}] {c.key} — {c.source}</li>)}</ul></div>}
  </div>;
}

export function DecisionsPage({ projectId }: { projectId: string }) {
  const [sel, setSel] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  return <SplitLayout storageKey="decisions" title="Decision records" sideWidth="xl:w-[460px]" side={(toggle) =>
    <Card eyebrow="MADR" title="Decision records" actions={<><Button size="sm" variant="primary" onClick={() => setOpen(true)}><Plus size={14} /> New</Button>{toggle}</>}>
      <DataTable<Adr> queryKey={["adrs", projectId]} endpoint={`/projects/${projectId}/adrs`} rowKey={(a) => a.id} defaultSort="number" defaultDir="desc"
        searchPlaceholder="Search decisions" selected={sel} onRowClick={(a) => setSel(a.id)}
        filters={[{ key: "status", label: "Status", options: [["proposed", "Proposed"], ["accepted", "Accepted"], ["rejected", "Rejected"], ["superseded", "Superseded"]] }]}
        empty="No ADRs. Propose one, or ask the assistant to draft it from evidence."
        columns={[{ key: "number", label: "#", sortable: true, render: (a) => <span className="font-mono text-xs">{String(a.number).padStart(4, "0")}</span> },
          { key: "title", label: "Title", sortable: true, render: (a) => <>{a.title}{a.ai_drafted && <Bot size={11} className="ml-1 inline text-link" />}<div className="text-[10px] text-soft">{ago(a.created_at)}</div></> },
          { key: "status", label: "Status", sortable: true, render: (a) => <Badge tone={TONE[a.status]}>{a.status}</Badge> }]} />
    </Card>}>
    <Card title="Record">{sel ? <AdrView projectId={projectId} id={sel} /> : <p className="text-sm text-soft">Select an ADR.</p>}</Card>
    <AdrForm projectId={projectId} open={open} onClose={() => setOpen(false)} />
  </SplitLayout>;
}
