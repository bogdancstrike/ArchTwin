import { useState } from "react";
import { Badge, Button, Card, ErrorBox, Select, Spinner, Table, ago } from "@/components/ui";
import { api } from "@/lib/api";
import { useAction, useApi, useMe } from "@/lib/hooks";
import type { Snapshot } from "@/lib/types";

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
  const decide = useAction((b: { id: string; d: string }) => api(`/projects/${projectId}/baselines/${b.id}/${b.d}`, { method: "POST", json: {} }), [["baselines", projectId]], "Baseline decided");
  const merge = useAction((b: { alias_key: string; canonical_key: string }) => api(`/projects/${projectId}/identities/merge`, { method: "POST", json: { ...b, reason: "merged in UI" } }), [["identities", projectId]], "Identities merged");
  return <div className="grid gap-4 p-6 xl:grid-cols-2">
    <Card eyebrow="Desired state" title="Baselines" actions={<><Select aria-label="Snapshot" value={snap} onChange={(e) => setSnap(e.target.value)}>
      {snaps.data?.map((s) => <option key={s.id} value={s.id}>v{s.version} · {s.node_count} elements</option>)}</Select><Button size="sm" variant="primary" onClick={() => propose.mutate(undefined as never)}>Propose baseline</Button></>}>
      <p className="mb-2 text-xs text-soft">An approved baseline is the desired architecture drift is measured against. Scans never change it; the proposer cannot approve it.</p>
      {baselines.isLoading && <Spinner />}<ErrorBox error={propose.error ?? decide.error} />
      <Table head={["Snapshot", "Status", "Proposed", ""]}>{baselines.data?.map((b) => <tr key={b.id} className="border-b border-rule"><td className="px-2 py-1.5">v{b.version}</td>
        <td className="px-2"><Badge tone={({ approved: "ok", proposed: "warn", rejected: "bad", superseded: "muted" } as Record<string, string>)[b.status]}>{b.status}</Badge></td><td className="px-2 text-xs">{ago(b.proposed_at)}</td>
        <td className="px-2 text-right">{b.status === "proposed" && <span className="space-x-1"><Button size="sm" disabled={b.author_id === me.data?.id} title={b.author_id === me.data?.id ? "Author cannot approve" : ""} onClick={() => decide.mutate({ id: b.id, d: "approve" })}>Approve</Button>
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
  </div>;
}
