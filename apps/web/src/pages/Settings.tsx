import { useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge, Button, Card, Dialog, ErrorBox, Input, Select, Spinner, Table, ago } from "@/components/ui";
import { api } from "@/lib/api";
import { useAction, useApi, useMe } from "@/lib/hooks";
import type { Project, Snapshot } from "@/lib/types";

/** GitHub-style double confirmation: understand what is lost, then type the project slug. Enforced again by the API. */
function DangerZone({ projectId }: { projectId: string }) {
  const p = useApi<Project & { slug: string }>(["project", projectId], `/projects/${projectId}`);
  const [step, setStep] = useState<0 | 1 | 2>(0);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const nav = useNavigate();
  const qc = useQueryClient();
  const slug = p.data?.slug ?? "";
  const close = () => { setStep(0); setTyped(""); setErr(null); };
  const del = async () => {
    setBusy(true); setErr(null);
    try {
      await api(`/projects/${projectId}`, { method: "DELETE", json: { confirm: typed } });
      toast.success(`Project ${p.data?.title} deleted`);
      await qc.invalidateQueries({ queryKey: ["projects"] });
      void nav({ to: "/projects" });
    } catch (e) { setErr(e); } finally { setBusy(false); }
  };
  return <Card eyebrow="Danger zone" title={<span className="flex items-center gap-2 text-bad"><AlertTriangle size={16} /> Delete this project</span>} className="border-bad/40 xl:col-span-2">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm text-muted">Permanently deletes <b>{p.data?.title}</b>: datasources and their credentials, all evidence and snapshots, baselines,
        drift findings, decision records, documents and assistant conversations. The audit trail and AI cost history are kept. This cannot be undone.</p>
      <Button variant="danger" onClick={() => setStep(1)}><Trash2 size={14} /> Delete project…</Button>
    </div>
    <Dialog open={step > 0} onClose={close} title={`Delete ${p.data?.title ?? "project"}`}>
      {step === 1 ? <div className="space-y-3 text-sm">
        <div className="flex gap-2 rounded-lg border border-bad/30 bg-bad/10 p-3 text-bad"><AlertTriangle size={16} className="mt-0.5 shrink-0" />
          <span>This permanently deletes the project and everything in it. Members lose access immediately.</span></div>
        <ul className="list-disc space-y-0.5 pl-5 text-muted"><li>Datasources, sealed credentials and webhooks</li><li>Observations, snapshots, baselines and drift findings</li>
          <li>Decision records (ADRs), documents and generated docs</li><li>Assistant conversations</li></ul>
        <p className="text-soft">Kept: the organization audit trail and AI usage/cost history.</p>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={close}>Cancel</Button><Button variant="danger" onClick={() => setStep(2)}>I understand, continue</Button></div>
      </div> : <form className="space-y-3 text-sm" onSubmit={(e) => { e.preventDefault(); if (typed === slug) void del(); }}>
        <p>To confirm, type <code className="rounded bg-paper-2 px-1 font-mono">{slug}</code> below.</p>
        <Input autoFocus aria-label="Type the project slug to confirm" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" spellCheck={false} />
        <ErrorBox error={err} />
        <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={close}>Cancel</Button>
          <Button variant="danger" disabled={typed !== slug || busy}>{busy ? "Deleting…" : "Delete this project"}</Button></div>
      </form>}
    </Dialog>
  </Card>;
}

const ROLES = ["project_owner", "architect", "tech_lead", "contributor", "reviewer", "viewer"];

export function SettingsPage({ projectId }: { projectId: string }) {
  const me = useMe();
  const members = useApi<any[]>(["members", projectId], `/projects/${projectId}/members`);
  const users = useApi<any[]>(["orgusers"], "/org/users");
  const baselines = useApi<any[]>(["baselines", projectId], `/projects/${projectId}/baselines`);
  const snaps = useApi<Snapshot[]>(["snapshots", projectId], `/projects/${projectId}/snapshots`);
  const ids = useApi<any>(["identities", projectId], `/projects/${projectId}/identities`);
  const [u, setU] = useState(""); const [role, setRole] = useState("viewer"); const [snap, setSnap] = useState("");
  const setMember = useAction((b: { user_id: string; role: string | null }) => api(`/projects/${projectId}/members`, { method: "PUT", json: b }), [["members", projectId]], "Membership updated");
  const propose = useAction(() => api(`/projects/${projectId}/baselines`, { method: "POST", json: { snapshot_id: snap || snaps.data?.[0]?.id, note: "Proposed from UI" } }), [["baselines", projectId]], "Baseline proposed");
  const decide = useAction((b: { id: string; d: string; note?: string }) => api(`/projects/${projectId}/baselines/${b.id}/${b.d}`, { method: "POST", json: { note: b.note ?? "" } }),
    [["baselines", projectId]], "Baseline decided");
  const isAdmin = !!me.data && ["org_owner", "org_admin"].includes(me.data.org_role);
  const selfApprove = (id: string) => {
    const reason = prompt("You proposed this baseline. As an organization admin you may approve it yourself — this exception to four-eyes is audited.\n\nReason (required):");
    if (reason && reason.trim().length >= 10) decide.mutate({ id, d: "approve", note: reason.trim() });
    else if (reason !== null) toast.error("A reason of at least 10 characters is required.");
  };
  const merge = useAction((b: { alias_key: string; canonical_key: string }) => api(`/projects/${projectId}/identities/merge`, { method: "POST", json: { ...b, reason: "merged in UI" } }), [["identities", projectId]], "Identities merged");
  return <div className="grid gap-4 p-6 xl:grid-cols-2">
    <Card eyebrow="Desired state" title="Baselines" actions={<><Select aria-label="Snapshot" value={snap} onChange={(e) => setSnap(e.target.value)}>
      {snaps.data?.map((s) => <option key={s.id} value={s.id}>v{s.version} · {s.node_count} elements</option>)}</Select><Button size="sm" variant="primary" onClick={() => propose.mutate(undefined as never)}>Propose baseline</Button></>}>
      <p className="mb-2 text-xs text-soft">An approved baseline is the desired architecture drift is measured against. Scans never change it; the proposer cannot approve it.</p>
      {baselines.isLoading && <Spinner />}<ErrorBox error={propose.error ?? decide.error} />
      <Table head={["Snapshot", "Status", "Proposed", ""]}>{baselines.data?.map((b) => <tr key={b.id} className="border-b border-rule"><td className="px-2 py-1.5">v{b.version}</td>
        <td className="px-2"><Badge tone={({ approved: "ok", proposed: "warn", rejected: "bad", superseded: "muted" } as Record<string, string>)[b.status]}>{b.status}</Badge></td><td className="px-2 text-xs">{ago(b.proposed_at)}</td>
        <td className="px-2 text-right">{b.status === "proposed" && <span className="space-x-1">{b.author_id === me.data?.id && isAdmin
          ? <Button size="sm" title="Approve your own baseline as organization admin (audited, reason required)" onClick={() => selfApprove(b.id)}>Approve (admin)</Button>
          : <Button size="sm" disabled={b.author_id === me.data?.id} title={b.author_id === me.data?.id ? "Author cannot approve" : ""} onClick={() => decide.mutate({ id: b.id, d: "approve" })}>Approve</Button>}
          <Button size="sm" variant="danger" disabled={b.author_id === me.data?.id} onClick={() => decide.mutate({ id: b.id, d: "reject" })}>Reject</Button></span>}</td></tr>)}</Table>
    </Card>
    <Card eyebrow="Access" title="Members">
      <Table head={["User", "Role", ""]}>{members.data?.map((m) => <tr key={m.user_id} className="border-b border-rule"><td className="px-2 py-1.5">{m.display_name} <span className="text-soft">@{m.username}</span></td>
        <td className="px-2"><Select aria-label={`Role of ${m.username}`} value={m.role} onChange={(e) => setMember.mutate({ user_id: m.user_id, role: e.target.value })}>{ROLES.map((r) => <option key={r}>{r}</option>)}</Select></td>
        <td className="px-2 text-right"><Button size="sm" variant="danger" onClick={() => setMember.mutate({ user_id: m.user_id, role: null })}>Revoke</Button></td></tr>)}</Table>
      <div className="mt-3 flex gap-2"><Select aria-label="User" value={u} onChange={(e) => setU(e.target.value)}><option value="">Add organization member…</option>{users.data?.filter((x) => !members.data?.some((m) => m.user_id === x.id)).map((x) => <option key={x.id} value={x.id}>{x.display_name} (@{x.username})</option>)}</Select>
        <Select aria-label="Role" value={role} onChange={(e) => setRole(e.target.value)}>{ROLES.map((r) => <option key={r}>{r}</option>)}</Select><Button disabled={!u} onClick={() => setMember.mutate({ user_id: u, role })}>Add</Button></div>
      <ErrorBox error={setMember.error} />
    </Card>
    <Card eyebrow="Identity reconciliation" title="Suggested merges" className="xl:col-span-2">
      {ids.data?.suggestions?.length === 0 && <p className="text-sm text-soft">No ambiguous identities — static and runtime keys reconcile on authoritative keys (compose project/service labels).</p>}
      <Table head={["Element A", "Element B", "Reason", ""]}>{ids.data?.suggestions?.map((s: any) => <tr key={s.id} className="border-b border-rule"><td className="px-2 py-1 font-mono text-xs">{s.key_a}</td><td className="px-2 font-mono text-xs">{s.key_b}</td><td className="px-2 text-xs">{s.reason}</td>
        <td className="px-2"><Button size="sm" onClick={() => merge.mutate({ alias_key: s.key_b, canonical_key: s.key_a })}>Merge B into A</Button></td></tr>)}</Table>
    </Card>
    {me.data && ["org_owner", "org_admin"].includes(me.data.org_role) && <DangerZone projectId={projectId} />}
  </div>;
}
