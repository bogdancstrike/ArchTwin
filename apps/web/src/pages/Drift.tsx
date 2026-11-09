import { useNavigate, useParams } from "@tanstack/react-router";
import { RefreshCw, RotateCcw, Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, Dialog, ErrorBox, Field, Input, OriginBadges, Spinner, Textarea, ago } from "@/components/ui";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { Finding } from "@/lib/types";
import { DataTable, type Column } from "@/components/DataTable";
import { SplitLayout } from "@/components/SplitLayout";

const SEV: Record<string, string> = { critical: "bad", high: "bad", medium: "warn", low: "muted" };
const VERDICT: Record<string, string> = { drift: "accent", unknown: "muted", incomplete: "warn" };

/** "Delete" a finding the user considers untrue: it is dismissed as a false positive (kept so re-evaluation does not recreate it). */
function DismissDialog({ projectId, findings, onClose, onDone }: { projectId: string; findings: Finding[]; onClose: () => void; onDone?: () => void }) {
  const [note, setNote] = useState("");
  const del = useAction(() => api(`/projects/${projectId}/drift/dismiss`, { method: "POST", json: { ids: findings.map((f) => f.id), note } }),
    [["drift", projectId], ...findings.map((f) => ["finding", f.id])], findings.length === 1 ? "Finding deleted" : `${findings.length} findings deleted`);
  return <Dialog open={findings.length > 0} onClose={onClose} title={findings.length === 1 ? "Delete drift finding" : `Delete ${findings.length} drift findings`}>
    <div className="space-y-3 text-sm">
      {findings.length === 1 && <p className="rounded bg-paper-2 p-2"><b>{findings[0].title}</b><br /><span className="font-mono text-xs text-soft">{findings[0].subject_key}</span></p>}
      <p className="text-muted">The finding is dismissed as <b>not true</b>: it disappears from the list, the counts and the diagrams, and the next evaluation will not bring it back.
        You can still see it under <i>Status: Dismissed</i> and restore it.</p>
      <Field label="Why is it not true? (optional, kept in the audit log)"><Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)}
        placeholder="e.g. the endpoint is served by the gateway, the ADR was superseded…" /></Field>
      <div className="flex justify-end gap-2"><Button onClick={onClose}>Cancel</Button>
        <Button variant="danger" disabled={del.isPending} onClick={() => del.mutate(undefined as never, { onSuccess: () => { onClose(); onDone?.(); } })}>
          <Trash2 size={13} /> Delete</Button></div>
    </div>
  </Dialog>;
}

function FindingDetail({ projectId, fid, onDeleted }: { projectId: string; fid: string; onDeleted: () => void }) {
  const f = useApi<Finding>(["finding", fid], `/projects/${projectId}/drift/${fid}`);
  const [note, setNote] = useState(""); const [days, setDays] = useState(30); const [comment, setComment] = useState("");
  const [deleting, setDeleting] = useState(false);
  const tr = useAction((b: { status: string; note?: string; suppress_days?: number }) => api(`/projects/${projectId}/drift/${fid}/transition`, { method: "POST", json: b }),
    [["finding", fid], ["drift", projectId]], "Finding updated");
  const cm = useAction(() => api(`/projects/${projectId}/drift/${fid}/comments`, { method: "POST", json: { body: comment } }), [["finding", fid]]);
  if (f.isLoading) return <Spinner />;
  if (f.error) return <ErrorBox error={f.error} />;
  const d = f.data!;
  return <div className="space-y-4">
    <div><div className="eyebrow">{d.rule?.title} · {d.rule_id} v{d.rule_version}</div><h2 className="text-lg font-semibold">{d.title}</h2>
      <div className="mt-1 flex flex-wrap gap-2"><Badge tone={VERDICT[d.verdict]}>{d.verdict}</Badge><Badge tone={SEV[d.severity]}>{d.severity}</Badge><Badge>{d.status}</Badge>
        <span className="text-xs text-soft">first seen {ago(d.first_seen)} · last {ago(d.last_seen)} · {d.occurrences}×</span>
        <span className="ml-auto">{d.status === "dismissed"
          ? <Button size="sm" onClick={() => tr.mutate({ status: "new", note: "restored" })}><RotateCcw size={13} /> Restore</Button>
          : <Button size="sm" variant="danger" onClick={() => setDeleting(true)} title="Not true — delete this finding"><Trash2 size={13} /> Delete</Button>}</span></div>
      <DismissDialog projectId={projectId} findings={deleting ? [d] : []} onClose={() => setDeleting(false)} onDone={onDeleted} />
      {d.verdict !== "drift" && <p className="mt-2 rounded bg-paper-2 p-2 text-xs text-muted">Evidence is {d.verdict}: the covering source is stale, partial or missing, so this is <b>not</b> reported as drift and raises no alert.</p>}</div>
    <div className="grid grid-cols-2 gap-3 text-xs"><div><div className="eyebrow mb-1">Expected (baseline / declared)</div><pre className="overflow-auto rounded bg-paper-2 p-2">{JSON.stringify(d.expected, null, 2)}</pre></div>
      <div><div className="eyebrow mb-1">Actual (observed)</div><pre className="overflow-auto rounded bg-paper-2 p-2">{JSON.stringify(d.actual, null, 2)}</pre></div></div>
    <div><div className="eyebrow mb-1">Evidence</div><ul className="space-y-1 text-xs">{d.evidence.map((e, i) => <li key={i} className="rounded border border-rule p-2"><OriginBadges origins={[e.origin]} /> <span className="font-mono">{e.source_ref}{e.span?.line_start ? `:${e.span.line_start}` : ""}</span> · rev <span className="font-mono">{(e.source_revision || "live").slice(0, 10)}</span> · {e.parser_version}</li>)}</ul></div>
    <div className="space-y-2 rounded border border-rule p-3"><div className="eyebrow">Triage</div>
      <Field label="Note / reason (optional)"><Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
      <div className="flex flex-wrap items-end gap-2">
        {["acknowledged", "investigating", "resolved"].map((s) => <Button key={s} size="sm" onClick={() => tr.mutate({ status: s, note })}>{s}</Button>)}
        <Button size="sm" onClick={() => tr.mutate({ status: "accepted", note })} title="Accept as intended — next baseline should include it">accept as intended</Button>
        <span className="flex items-end gap-1"><Field label="Days"><Input type="number" min={1} max={365} className="w-20" value={days} onChange={(e) => setDays(+e.target.value)} /></Field>
          <Button size="sm" variant="danger" onClick={() => tr.mutate({ status: "suppressed", note, suppress_days: days })}>suppress</Button></span>
      </div></div>
    <div><div className="eyebrow mb-1">Comments</div>{d.comments?.map((c) => <div key={c.id} className="border-b border-rule py-1 text-sm"><b>{c.username}</b> <span className="text-xs text-soft">{ago(c.created_at)}</span><p>{c.body}</p></div>)}
      <form className="mt-2 flex gap-2" onSubmit={(e) => { e.preventDefault(); cm.mutate(undefined as never); setComment(""); }}><Input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Add a comment" /><Button disabled={!comment}>Post</Button></form></div>
  </div>;
}

export function DriftPage({ projectId }: { projectId: string }) {
  const { findingId } = useParams({ strict: false }) as { findingId?: string };
  const nav = useNavigate();
  const ev = useAction(() => api<any>(`/projects/${projectId}/drift/evaluate`, { method: "POST" }), [["drift", projectId]], "Evaluation complete");
  const [deleting, setDeleting] = useState<Finding[]>([]);
  const closeDetail = () => nav({ to: "/projects/$projectId/drift", params: { projectId } });
  const columns: Column<Finding>[] = [
    { key: "verdict", label: "Verdict", sortable: true, render: (f) => <Badge tone={VERDICT[f.verdict]}>{f.verdict}</Badge> },
    { key: "severity", label: "Severity", sortable: true, render: (f) => <Badge tone={SEV[f.severity]}>{f.severity}</Badge> },
    { key: "title", label: "Finding", sortable: true, render: (f) => <><div>{f.title}</div><div className="font-mono text-[10px] text-soft">{f.rule_id}</div></> },
    { key: "status", label: "Status", sortable: true, render: (f) => <span className="text-xs">{f.status}</span> },
    { key: "last_seen", label: "Seen", sortable: true, render: (f) => <span className="text-xs">{ago(f.last_seen)}</span> },
    { key: "actions", label: "", className: "w-10 text-right", render: (f) => f.status === "dismissed" ? null
      : <button type="button" aria-label={`Delete finding ${f.title}`} title="Not true — delete" className="rounded p-1 text-soft hover:bg-paper-2 hover:text-bad"
          onClick={(e) => { e.stopPropagation(); setDeleting([f]); }}><Trash2 size={14} /></button> },
  ];
  return <SplitLayout storageKey="drift" title="Drift findings" sideWidth="xl:w-[58%]" side={(toggle) =>
    <Card eyebrow="Deterministic rules · three-way" title="Drift findings" actions={<><Button size="sm" onClick={() => ev.mutate(undefined as never)}><RefreshCw size={14} /> Evaluate now</Button>{toggle}</>}>
      <DataTable<Finding> queryKey={["drift", projectId]} endpoint={`/projects/${projectId}/drift`} columns={columns} rowKey={(f) => f.id}
        defaultSort="severity" defaultDir="asc" searchPlaceholder="Search findings, elements, rules" selected={findingId ?? null}
        onRowClick={(f) => nav({ to: "/projects/$projectId/drift/$findingId", params: { projectId, findingId: f.id } })}
        filters={[{ key: "status", label: "Status", options: [["open", "Open"], ["suppressed", "Suppressed"], ["resolved", "Resolved"], ["accepted", "Accepted"], ["dismissed", "Dismissed (deleted)"]] },
          { key: "verdict", label: "Verdict", options: [["drift", "Drift"], ["unknown", "Unknown"], ["incomplete", "Incomplete"]] },
          { key: "severity", label: "Severity", options: [["critical", "Critical"], ["high", "High"], ["medium", "Medium"], ["low", "Low"]] }]}
        empty="No findings. Approve a baseline in Settings and connect a runtime source; drift appears when evidence disagrees with the baseline or the code." />
      <DismissDialog projectId={projectId} findings={deleting} onClose={() => setDeleting([])}
        onDone={() => { if (deleting.some((f) => f.id === findingId)) closeDetail(); }} />
    </Card>}>
    <Card title="Details">{findingId ? <FindingDetail projectId={projectId} fid={findingId} onDeleted={closeDetail} /> : <p className="text-sm text-soft">Select a finding.</p>}</Card>
  </SplitLayout>;
}
