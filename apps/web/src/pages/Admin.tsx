import { ShieldAlert, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, ErrorBox, Input, Select, Spinner, Table, ago } from "@/components/ui";
import { api } from "@/lib/api";
import { useAction, useApi, useMe } from "@/lib/hooks";
import type { Project } from "@/lib/types";

export function FlagsPage() {
  const me = useMe();
  const [project, setProject] = useState("");
  const [filter, setFilter] = useState("");
  const projects = useApi<Project[]>(["projects", me.data?.org_id], "/projects");
  const flags = useApi<any[]>(["flags", project], `/flags${project ? `?project_id=${project}` : ""}`);
  const set = useAction((b: { key: string; value: boolean }) => api(`/flags/${b.key}`, { method: "PUT", json: { scope_kind: project ? "project" : "org", scope_id: project || null, value: b.value, reason: "admin UI" } }),
    [["flags", project]], "Flag updated (propagates within 15 s)");
  const shown = flags.data?.filter((f) => f.key.includes(filter));
  return <div className="space-y-4 p-8">
    <div><div className="eyebrow">Organization</div><h1 className="serif text-4xl">Feature flags</h1><p className="text-muted">OpenFeature over PostgreSQL. Precedence: security invariants › emergency kill switch › enforced org policy › project › org › default.</p></div>
    <div className="flex gap-2"><Select aria-label="Scope" value={project} onChange={(e) => setProject(e.target.value)}><option value="">Scope: organization</option>{projects.data?.map((p) => <option key={p.id} value={p.id}>Project: {p.title}</option>)}</Select>
      <Input className="max-w-xs" placeholder="Filter" value={filter} onChange={(e) => setFilter(e.target.value)} /></div>
    {flags.isLoading && <Spinner />}<ErrorBox error={flags.error ?? set.error} />
    <Card><Table head={["Flag", "Phase", "Effective", "Reason", ""]}>{shown?.map((f) => <tr key={f.key} className="border-b border-rule">
      <td className="px-2 py-1.5 font-mono text-xs">{f.immutable ? <ShieldCheck size={12} className="mr-1 inline text-ok" /> : f.key === "security.emergency_kill_switch" ? <ShieldAlert size={12} className="mr-1 inline text-bad" /> : null}{f.key}</td>
      <td className="px-2 text-xs text-soft">{f.phase}</td><td className="px-2"><Badge tone={f.value ? "ok" : "muted"}>{f.value ? "on" : "off"}</Badge></td><td className="px-2 text-xs">{f.reason}</td>
      <td className="px-2 text-right">{f.immutable ? <span className="text-xs text-soft">security invariant</span> : <Button size="sm" onClick={() => set.mutate({ key: f.key, value: !f.value })}>{f.value ? "Turn off" : "Turn on"}</Button>}</td></tr>)}</Table></Card>
  </div>;
}

export function AuditPage() {
  const [actor, setActor] = useState(""); const [action, setAction] = useState("");
  const ev = useApi<any[]>(["audit", actor, action], `/audit?limit=300${actor ? `&actor=${actor}` : ""}${action ? `&action=${action}` : ""}`);
  const verify = useApi<any>(["audit-verify"], "/audit/verify");
  return <div className="space-y-4 p-8">
    <div><div className="eyebrow">Organization</div><h1 className="serif text-4xl">Audit trail</h1><p className="text-muted">Append-only, hash-chained per organization; allow and deny decisions.</p></div>
    {verify.data && <div className="flex items-center gap-2 text-sm">{verify.data.ok ? <Badge tone="ok">chain verified</Badge> : <Badge tone="bad">tampering detected</Badge>} {verify.data.events} events · head <span className="font-mono text-xs">{verify.data.head.slice(0, 16)}</span></div>}
    <div className="flex gap-2"><Input className="max-w-xs" placeholder="Actor (username)" value={actor} onChange={(e) => setActor(e.target.value)} /><Input className="max-w-xs" placeholder="Action prefix (e.g. connector.)" value={action} onChange={(e) => setAction(e.target.value)} /></div>
    {ev.isLoading && <Spinner />}<ErrorBox error={ev.error} />
    <Card><Table head={["#", "When", "Actor", "Action", "Decision", "Resource", "Details"]}>{ev.data?.map((e) => <tr key={e.id} className="border-b border-rule align-top">
      <td className="px-2 py-1 font-mono text-xs">{e.seq}</td><td className="px-2 text-xs">{ago(e.occurred_at)}</td><td className="px-2 text-sm">{e.actor_name}</td><td className="px-2 font-mono text-xs">{e.action}</td>
      <td className="px-2"><Badge tone={e.decision === "allow" ? "ok" : "bad"}>{e.decision}</Badge></td><td className="px-2 font-mono text-[10px]">{e.resource_kind}:{String(e.resource_id).slice(0, 36)}</td>
      <td className="max-w-md truncate px-2 font-mono text-[10px] text-soft" title={JSON.stringify(e.details)}>{JSON.stringify(e.details)}</td></tr>)}</Table></Card>
  </div>;
}
