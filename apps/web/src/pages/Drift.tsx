import { useNavigate, useParams } from "@tanstack/react-router";
import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, ErrorBox, Field, Input, OriginBadges, Spinner, Textarea, ago } from "@/components/ui";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { Finding } from "@/lib/types";
import { DataTable, type Column } from "@/components/DataTable";

const SEV: Record<string, string> = { critical: "bad", high: "bad", medium: "warn", low: "muted" };
const VERDICT: Record<string, string> = { drift: "accent", unknown: "muted", incomplete: "warn" };

function FindingDetail({ projectId, fid }: { projectId: string; fid: string }) {
  const f = useApi<Finding>(["finding", fid], `/projects/${projectId}/drift/${fid}`);
  const [note, setNote] = useState(""); const [days, setDays] = useState(30); const [comment, setComment] = useState("");
  const tr = useAction((b: { status: string; note?: string; suppress_days?: number }) => api(`/projects/${projectId}/drift/${fid}/transition`, { method: "POST", json: b }),
    [["finding", fid], ["drift", projectId]], "Finding updated");
  const cm = useAction(() => api(`/projects/${projectId}/drift/${fid}/comments`, { method: "POST", json: { body: comment } }), [["finding", fid]]);
  if (f.isLoading) return <Spinner />;
  if (f.error) return <ErrorBox error={f.error} />;
  const d = f.data!;
  return <div className="space-y-4">
    <div><div className="eyebrow">{d.rule?.title} · {d.rule_id} v{d.rule_version}</div><h2 className="text-lg font-semibold">{d.title}</h2>
      <div className="mt-1 flex flex-wrap gap-2"><Badge tone={VERDICT[d.verdict]}>{d.verdict}</Badge><Badge tone={SEV[d.severity]}>{d.severity}</Badge><Badge>{d.status}</Badge>
        <span className="text-xs text-soft">first seen {ago(d.first_seen)} · last {ago(d.last_seen)} · {d.occurrences}×</span></div>
      {d.verdict !== "drift" && <p className="mt-2 rounded bg-paper-2 p-2 text-xs text-muted">Evidence is {d.verdict}: the covering source is stale, partial or missing, so this is <b>not</b> reported as drift and raises no alert.</p>}</div>
    <div className="grid grid-cols-2 gap-3 text-xs"><div><div className="eyebrow mb-1">Expected (baseline / declared)</div><pre className="overflow-auto rounded bg-paper-2 p-2">{JSON.stringify(d.expected, null, 2)}</pre></div>
      <div><div className="eyebrow mb-1">Actual (observed)</div><pre className="overflow-auto rounded bg-paper-2 p-2">{JSON.stringify(d.actual, null, 2)}</pre></div></div>
    <div><div className="eyebrow mb-1">Evidence</div><ul className="space-y-1 text-xs">{d.evidence.map((e, i) => <li key={i} className="rounded border border-rule p-2"><OriginBadges origins={[e.origin]} /> <span className="font-mono">{e.source_ref}{e.span?.line_start ? `:${e.span.line_start}` : ""}</span> · rev <span className="font-mono">{(e.source_revision || "live").slice(0, 10)}</span> · {e.parser_version}</li>)}</ul></div>
    <div className="space-y-2 rounded border border-rule p-3"><div className="eyebrow">Triage</div>
      <Field label="Note / reason"><Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
      <div className="flex flex-wrap items-end gap-2">
        {["acknowledged", "investigating", "resolved"].map((s) => <Button key={s} size="sm" onClick={() => tr.mutate({ status: s, note })}>{s}</Button>)}
        <Button size="sm" onClick={() => tr.mutate({ status: "accepted", note })} title="Accept as intended — next baseline should include it">accept as intended</Button>
        <span className="flex items-end gap-1"><Field label="Days"><Input type="number" min={1} max={365} className="w-20" value={days} onChange={(e) => setDays(+e.target.value)} /></Field>
          <Button size="sm" variant="danger" disabled={!note} onClick={() => tr.mutate({ status: "suppressed", note, suppress_days: days })}>suppress</Button></span>
      </div></div>
    <div><div className="eyebrow mb-1">Comments</div>{d.comments?.map((c) => <div key={c.id} className="border-b border-rule py-1 text-sm"><b>{c.username}</b> <span className="text-xs text-soft">{ago(c.created_at)}</span><p>{c.body}</p></div>)}
      <form className="mt-2 flex gap-2" onSubmit={(e) => { e.preventDefault(); cm.mutate(undefined as never); setComment(""); }}><Input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Add a comment" /><Button disabled={!comment}>Post</Button></form></div>
  </div>;
}

export function DriftPage({ projectId }: { projectId: string }) {
  const { findingId } = useParams({ strict: false }) as { findingId?: string };
  const nav = useNavigate();
  const ev = useAction(() => api<any>(`/projects/${projectId}/drift/evaluate`, { method: "POST" }), [["drift", projectId]], "Evaluation complete");
  const columns: Column<Finding>[] = [
    { key: "verdict", label: "Verdict", sortable: true, render: (f) => <Badge tone={VERDICT[f.verdict]}>{f.verdict}</Badge> },
    { key: "severity", label: "Severity", sortable: true, render: (f) => <Badge tone={SEV[f.severity]}>{f.severity}</Badge> },
    { key: "title", label: "Finding", sortable: true, render: (f) => <><div>{f.title}</div><div className="font-mono text-[10px] text-soft">{f.rule_id}</div></> },
    { key: "status", label: "Status", sortable: true, render: (f) => <span className="text-xs">{f.status}</span> },
    { key: "last_seen", label: "Seen", sortable: true, render: (f) => <span className="text-xs">{ago(f.last_seen)}</span> },
  ];
  return <div className="grid gap-4 p-6 xl:grid-cols-[1fr_480px]">
    <Card eyebrow="Deterministic rules · three-way" title="Drift findings" actions={<Button size="sm" onClick={() => ev.mutate(undefined as never)}><RefreshCw size={14} /> Evaluate now</Button>}>
      <DataTable<Finding> queryKey={["drift", projectId]} endpoint={`/projects/${projectId}/drift`} columns={columns} rowKey={(f) => f.id}
        defaultSort="severity" defaultDir="asc" searchPlaceholder="Search findings, elements, rules" selected={findingId ?? null}
        onRowClick={(f) => nav({ to: "/projects/$projectId/drift/$findingId", params: { projectId, findingId: f.id } })}
        filters={[{ key: "status", label: "Status", options: [["open", "Open"], ["suppressed", "Suppressed"], ["resolved", "Resolved"], ["accepted", "Accepted"]] },
          { key: "verdict", label: "Verdict", options: [["drift", "Drift"], ["unknown", "Unknown"], ["incomplete", "Incomplete"]] },
          { key: "severity", label: "Severity", options: [["critical", "Critical"], ["high", "High"], ["medium", "Medium"], ["low", "Low"]] }]}
        empty="No findings. Approve a baseline in Settings and connect a runtime source; drift appears when evidence disagrees with the baseline or the code." />
    </Card>
    <Card title="Details">{findingId ? <FindingDetail projectId={projectId} fid={findingId} /> : <p className="text-sm text-soft">Select a finding.</p>}</Card>
  </div>;
}
