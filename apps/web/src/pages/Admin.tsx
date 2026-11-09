import { ShieldAlert, ShieldCheck } from "lucide-react";
import { Fragment, useState } from "react";
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

const CATS: [string, string][] = [["", "All"], ["datasources", "Datasources"], ["architecture", "Architecture & drift"], ["decisions", "Decisions"],
  ["ai", "AI & spend"], ["access", "Members & access"], ["exports", "Exports"]];

export function AuditPage() {
  const [f, setF] = useState({ q: "", actor: "", result: "", category: "", since: "", until: "", sort: "when", dir: "desc", page: 1, size: 25 });
  const [open, setOpen] = useState<string | null>(null);
  const set = (patch: Partial<typeof f>) => setF((x) => ({ ...x, page: 1, ...patch }));
  const qs = new URLSearchParams(Object.entries({ q: f.q, actor: f.actor, result: f.result, category: f.category, since: f.since, until: f.until,
    sort: f.sort, dir: f.dir, page: String(f.page), page_size: String(f.size) }).filter(([, v]) => v)).toString();
  const ev = useApi<any>(["audit-search", qs], `/audit/search?${qs}`, { keepPrevious: true });
  const verify = useApi<any>(["audit-verify"], "/audit/verify");
  const sortBy = (k: string) => setF((x) => ({ ...x, sort: k, dir: x.sort === k && x.dir === "desc" ? "asc" : "desc" }));
  const H = ({ k, children }: { k: string; children: string }) => <button className="flex items-center gap-1 uppercase" onClick={() => sortBy(k)} aria-label={`Sort by ${children}`}>
    {children}{f.sort === k ? (f.dir === "desc" ? " ↓" : " ↑") : ""}</button>;
  const dirty = f.q || f.actor || f.result || f.category || f.since || f.until;
  return <div className="space-y-4 p-8">
    <div><div className="eyebrow">Organization</div><h1 className="serif text-4xl">Audit trail</h1><p className="text-muted">Append-only and hash-chained per organization: every change, every AI call, every allow and deny decision.</p></div>
    {verify.data && <div className="flex items-center gap-2 text-sm">{verify.data.ok ? <Badge tone="ok">chain verified</Badge> : <Badge tone="bad">tampering detected</Badge>} {verify.data.events} events · head <span className="font-mono text-xs">{verify.data.head.slice(0, 16)}</span></div>}
    <div className="flex flex-wrap items-center gap-2">
      <Input className="max-w-xs" placeholder="Search actions, people, resources" aria-label="Search audit" value={f.q} onChange={(e) => set({ q: e.target.value })} />
      <div role="radiogroup" aria-label="Category" className="flex flex-wrap gap-1">{CATS.map(([k, l]) => <button key={k} role="radio" aria-checked={f.category === k} onClick={() => set({ category: k })}
        className={`rounded-full border px-2.5 py-1 text-xs ${f.category === k ? "border-ink bg-ink text-paper" : "border-rule hover:border-muted"}`}>{l}</button>)}</div>
      {dirty && <Button size="sm" variant="ghost" onClick={() => setF((x) => ({ ...x, q: "", actor: "", result: "", category: "", since: "", until: "", page: 1 }))}>Clear filters</Button>}
    </div>
    <ErrorBox error={ev.error} />
    <Card>
      <div className="mb-2 grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
        <label className="flex items-center gap-1">From <Input type="date" aria-label="From date" value={f.since} onChange={(e) => set({ since: e.target.value })} /></label>
        <label className="flex items-center gap-1">To <Input type="date" aria-label="To date (inclusive)" value={f.until} onChange={(e) => set({ until: e.target.value })} /></label>
        <Select aria-label="Who" value={f.actor} onChange={(e) => set({ actor: e.target.value })}><option value="">Anyone</option>{ev.data?.actors.map((a: string) => <option key={a} value={a}>{a}</option>)}</Select>
        <Select aria-label="Result" value={f.result} onChange={(e) => set({ result: e.target.value })}><option value="">Any result</option><option value="allow">Allowed</option><option value="deny">Denied</option></Select>
      </div>
      <Table head={[<H key="w" k="when">When</H>, <H key="o" k="who">Who</H>, "What happened", <H key="a" k="what">Action</H>, <H key="r" k="result">Result</H>]}>
        {ev.data?.items.map((e: any) => <Fragment key={e.id}>
          <tr className="cursor-pointer border-b border-rule align-top hover:bg-paper/60" onClick={() => setOpen(open === e.id ? null : e.id)} aria-expanded={open === e.id}>
            <td className="px-2 py-1.5 text-xs" title={e.occurred_at}>{ago(e.occurred_at)}</td><td className="px-2 text-sm">{e.actor_name}</td>
            <td className="px-2 text-sm">{e.summary}</td><td className="px-2 font-mono text-[11px]">{e.action}</td>
            <td className="px-2"><Badge tone={e.decision === "allow" ? "ok" : "bad"}>{e.decision === "allow" ? "Allowed" : "Denied"}</Badge></td></tr>
          {open === e.id && <tr className="border-b border-rule bg-paper/50"><td colSpan={5} className="px-3 py-2 text-xs">
            <dl className="grid gap-x-4 gap-y-1 md:grid-cols-4"><div><dt className="eyebrow">Sequence</dt><dd className="font-mono">#{e.seq}</dd></div>
              <div><dt className="eyebrow">Resource</dt><dd className="font-mono">{e.resource_kind}:{e.resource_id}</dd></div>
              <div><dt className="eyebrow">Project</dt><dd>{e.project_title || "—"}</dd></div><div><dt className="eyebrow">Trace</dt><dd className="font-mono">{e.trace_id || "—"}</dd></div></dl>
            <pre className="mt-2 max-h-64 overflow-auto rounded bg-card p-2 font-mono text-[11px]">{JSON.stringify(e.details, null, 2)}</pre>
            <div className="mt-1 font-mono text-[10px] text-soft">hash {e.hash?.slice(0, 24)} · prev {e.prev_hash?.slice(0, 24)}</div></td></tr>}
        </Fragment>)}</Table>
      {ev.data?.items.length === 0 && <p className="py-6 text-center text-sm text-soft">No activity matches these filters.</p>}
      {ev.data && <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="text-muted">{ev.data.total.toLocaleString()} events · page {ev.data.page} of {ev.data.pages}</span>
        <div className="flex items-center gap-2"><Select aria-label="Page size" value={f.size} onChange={(e) => set({ size: Number(e.target.value) })}>{[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n} / page</option>)}</Select>
          <Button size="sm" disabled={f.page <= 1} onClick={() => setF((x) => ({ ...x, page: x.page - 1 }))}>Previous</Button>
          <Button size="sm" disabled={f.page >= ev.data.pages} onClick={() => setF((x) => ({ ...x, page: x.page + 1 }))}>Next</Button></div></div>}
    </Card>
  </div>;
}
