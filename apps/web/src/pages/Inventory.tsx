import { Play, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, Dialog, Empty, ErrorBox, Field, FreshnessBadge, Input, Select, Spinner, Table, Textarea, ago } from "@/components/ui";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { Connector, Scan } from "@/lib/types";

interface Kind { kind: string; name: string; origin: string; scopes: string[]; enabled: boolean; flag: string; config: Record<string, unknown> }

const PRESETS: Record<string, { config: string; secret?: string }> = {
  git: { config: '{\n  "path": "/sources/horizon",\n  "name": "horizon"\n}' },
  docker: { config: '{\n  "endpoint": "http://docker-proxy:2375",\n  "compose_projects": ["horizon"]\n}' },
  postgresql: { config: '{\n  "host": "postgres", "port": 5432, "database": "archtwin", "username": "archtwin_catalog_ro",\n  "schemas": ["public"], "system": "archtwin", "service": "postgres"\n}', secret: '{\n  "password": ""\n}' },
  http_openapi: { config: '{\n  "url": "http://api:8000/api/openapi.json", "system": "archtwin", "service": "api"\n}' },
};

function AddConnector({ projectId, open, onClose }: { projectId: string; open: boolean; onClose: () => void }) {
  const kinds = useApi<Kind[]>(["kinds", projectId], `/connector-kinds?project_id=${projectId}`);
  const [kind, setKind] = useState("git");
  const [name, setName] = useState("");
  const [config, setConfig] = useState(PRESETS.git.config);
  const [secret, setSecret] = useState("");
  const create = useAction(() => api("/projects/" + projectId + "/connectors", { method: "POST", idempotent: true, json: {
    kind, name, config: JSON.parse(config), secret: secret.trim() ? JSON.parse(secret) : null } }), [["connectors", projectId]], "Connector created");
  const k = kinds.data?.find((x) => x.kind === kind);
  return <Dialog open={open} onClose={onClose} title="Add connector" wide>
    <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); await create.mutateAsync(undefined as never); onClose(); }}>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Kind"><Select className="w-full" value={kind} onChange={(e) => { setKind(e.target.value); setConfig(PRESETS[e.target.value]?.config ?? "{}"); setSecret(PRESETS[e.target.value]?.secret ?? ""); }}>
          {kinds.data?.map((x) => <option key={x.kind} value={x.kind} disabled={!x.enabled}>{x.name}{x.enabled ? "" : " (disabled by flag)"}</option>)}</Select></Field>
        <Field label="Name"><Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. horizon-repo" /></Field>
      </div>
      {k && <div className="flex flex-wrap items-center gap-2 text-xs text-muted"><ShieldCheck size={14} className="text-ok" /> read-only · origin <Badge>{k.origin}</Badge> scopes: {k.scopes.map((s) => <Badge key={s} tone="link">{s}</Badge>)}</div>}
      <Field label="Configuration (JSON)"><Textarea rows={7} className="font-mono text-xs" value={config} onChange={(e) => setConfig(e.target.value)} /></Field>
      <Field label="Credentials (JSON, optional)" hint="Encrypted with envelope encryption; never shown again or logged."><Textarea rows={3} className="font-mono text-xs" value={secret} onChange={(e) => setSecret(e.target.value)} /></Field>
      <ErrorBox error={create.error} />
      <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" disabled={create.isPending}>Create</Button></div>
    </form>
  </Dialog>;
}

export function InventoryPage({ projectId }: { projectId: string }) {
  const cs = useApi<Connector[]>(["connectors", projectId], `/projects/${projectId}/connectors`, { refetchInterval: 5000 });
  const scans = useApi<Scan[]>(["scans", projectId], `/projects/${projectId}/scans`, { refetchInterval: 4000 });
  const inv = useApi<any>(["inventory", projectId], `/projects/${projectId}/inventory`, { refetchInterval: 10_000 });
  const [open, setOpen] = useState(false);
  const [refs, setRefs] = useState<Record<string, string>>({});
  const [tests, setTests] = useState<Record<string, any>>({});
  const scan = useAction((c: { id: string; ref?: string }) => api(`/projects/${projectId}/connectors/${c.id}/scan`, { method: "POST", idempotent: true, json: { ref: c.ref || null } }), [["scans", projectId]], "Scan queued");
  const del = useAction((id: string) => api(`/projects/${projectId}/connectors/${id}`, { method: "DELETE" }), [["connectors", projectId]], "Connector removed — its evidence stays; coverage lapses to UNKNOWN");
  const names = Object.fromEntries((cs.data ?? []).map((c) => [c.id, c.name]));
  return <div className="space-y-6 p-6">
    <Card eyebrow="Read-only connectors" title="Sources of evidence" actions={<Button variant="primary" size="sm" onClick={() => setOpen(true)}><Plus size={14} /> Add connector</Button>}>
      {cs.isLoading && <Spinner />}<ErrorBox error={cs.error} />
      {cs.data?.length === 0 && <Empty title="No connectors">Connect a repository (static), a Docker host (runtime), a database catalog or a live OpenAPI document.</Empty>}
      {!!cs.data?.length && <Table head={["Connector", "Kind", "Freshness", "Last scan", "Ref", ""]}>{cs.data.map((c) => <tr key={c.id} className="border-b border-rule align-top">
        <td className="px-2 py-2"><b>{c.name}</b><div className="font-mono text-[10px] text-soft">{JSON.stringify(c.config).slice(0, 80)}</div>
          {tests[c.id] && <div className="mt-1 text-xs">{tests[c.id].ok ? <Badge tone="ok">test ok</Badge> : <Badge tone="bad">test failed</Badge>} {tests[c.id].warnings?.join("; ")}</div>}</td>
        <td className="px-2"><Badge>{c.kind}</Badge></td><td className="px-2"><FreshnessBadge f={c.freshness} /><div className="text-[10px] text-soft">{c.freshness.reason}</div></td>
        <td className="px-2 text-xs">{c.last_status} · {ago(c.last_complete_at)}</td>
        <td className="px-2">{c.kind === "git" && <Input aria-label="ref" className="w-28 font-mono text-xs" placeholder="HEAD" value={refs[c.id] ?? ""} onChange={(e) => setRefs({ ...refs, [c.id]: e.target.value })} />}</td>
        <td className="space-x-1 whitespace-nowrap px-2 text-right">
          <Button size="sm" onClick={async () => { try { setTests({ ...tests, [c.id]: await api(`/projects/${projectId}/connectors/${c.id}/test`, { method: "POST" }) }); } catch (e) { setTests({ ...tests, [c.id]: { ok: false, warnings: [(e as Error).message] } }); } }}>Test</Button>
          <Button size="sm" variant="primary" onClick={() => scan.mutate({ id: c.id, ref: refs[c.id] })}><Play size={12} /> Scan</Button>
          <Button size="sm" variant="danger" aria-label={`Remove ${c.name}`} onClick={() => confirm(`Remove ${c.name}?`) && del.mutate(c.id)}><Trash2 size={12} /></Button></td></tr>)}</Table>}
    </Card>
    <div className="grid gap-6 lg:grid-cols-2">
      <Card eyebrow="Jobs" title="Recent scans"><Table head={["Connector", "Status", "Revision", "Observations", "When"]}>{scans.data?.slice(0, 15).map((s) => <tr key={s.id} className="border-b border-rule">
        <td className="px-2 py-1.5">{names[s.connector_id] ?? "—"}</td><td className="px-2"><Badge tone={{ complete: "ok", partial: "warn", failed: "bad", running: "link", queued: "muted", skipped: "warn" }[s.status]}>{s.status}</Badge>{s.error && <div className="text-[10px] text-bad">{s.error}</div>}</td>
        <td className="px-2 font-mono text-xs">{(s.revision ?? "").slice(0, 10)}{s.ref ? ` (${s.ref})` : ""}</td><td className="px-2">{String(s.stats?.observations ?? "")}</td><td className="px-2 text-xs">{ago(s.finished_at ?? s.created_at)}</td></tr>)}</Table></Card>
      <Card eyebrow="Normalized" title="Observations by origin and kind"><Table head={["Origin", "Kind", "Count"]}>
        {inv.data?.observation_counts?.sort((a: any, b: any) => b.n - a.n).slice(0, 18).map((r: any) => <tr key={r.origin + r.kind} className="border-b border-rule"><td className="px-2 py-1"><Badge>{r.origin}</Badge></td><td className="px-2">{r.kind}</td><td className="px-2">{r.n}</td></tr>)}</Table></Card>
    </div>
    <AddConnector projectId={projectId} open={open} onClose={() => setOpen(false)} />
  </div>;
}
