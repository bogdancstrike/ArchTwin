import { CheckCircle2, ExternalLink, FolderOpen, Plus, RotateCcw, Save, Server, Trash2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge, Button, Card, Dialog, ErrorBox, Field, Input, Select, Skeleton, Table, ago, cn } from "@/components/ui";
import { CapBar, usd } from "@/components/charts";
import { FolderPicker } from "@/components/FolderPicker";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { Project } from "@/lib/types";

const TABS = [["overview", "Overview"], ["spend", "Spend limits"], ["roots", "Source roots"]] as const;
type Tab = typeof TABS[number][0];

function tabFromUrl(): Tab {
  const t = new URLSearchParams(window.location.search).get("tab");
  return (TABS.find(([k]) => k === t)?.[0] ?? "overview") as Tab;
}

export function SystemPage() {
  const [tab, setTab] = useState<Tab>(tabFromUrl);
  useEffect(() => { const u = new URL(window.location.href); u.searchParams.set("tab", tab); window.history.replaceState(null, "", u); }, [tab]);
  return <div className="space-y-5 p-8">
    <div><div className="eyebrow">Organization</div><h1 className="serif text-4xl">System</h1>
      <p className="text-muted">Health of every dependency, AI activity, monthly AI spend limits and which local folders datasources may read.</p></div>
    <nav role="tablist" aria-label="System sections" className="flex gap-1 border-b border-rule text-sm">{TABS.map(([k, l]) =>
      <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
        className={cn("-mb-px border-b-2 px-3 py-2", tab === k ? "border-accent font-medium text-ink" : "border-transparent text-muted hover:text-ink")}>{l}</button>)}</nav>
    {tab === "overview" && <Overview />}{tab === "spend" && <SpendLimits />}{tab === "roots" && <SourceRoots />}
  </div>;
}

function Overview() {
  const s = useApi<any>(["system"], "/admin/system", { refetchInterval: 10_000 });
  if (s.error) return <ErrorBox error={s.error} />;
  if (!s.data) return <div className="grid gap-4 lg:grid-cols-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-40 !rounded-xl" />)}</div>;
  const d = s.data;
  return <div className="grid gap-4 lg:grid-cols-2">
    <Card eyebrow={d.ok ? "All services healthy" : "Degraded"} title={<span className="flex items-center gap-2"><Server size={16} /> Services</span>}>
      <ul className="divide-y divide-rule text-sm">{d.services.map((x: any) => <li key={x.name} className="flex items-center justify-between py-1.5">
        <span className="flex items-center gap-2">{x.ok ? <CheckCircle2 size={14} className="text-ok" /> : <XCircle size={14} className="text-bad" />}{x.name}</span>
        <span className="flex items-center gap-2 text-xs text-muted"><span className="max-w-52 truncate font-mono">{x.detail}</span><span className="tabular-nums">{x.latency_ms} ms</span>
          <Badge tone={x.ok ? "ok" : "bad"}>{x.ok ? "OK" : "ERROR"}</Badge></span></li>)}</ul>
      <p className="mt-2 text-xs text-soft">AI mode: <b>{d.llm_mode}</b>{d.llm_mode === "fake" ? " (deterministic, no tokens spent)" : " (real models through LiteLLM)"}</p>
    </Card>
    <Card eyebrow="Last hour" title="AI gateway">
      <dl className="grid grid-cols-2 gap-3 text-sm">{[["Calls", d.llm_last_hour.calls], ["Errors", d.llm_last_hour.errors], ["p95 latency", `${d.llm_last_hour.p95_latency_ms} ms`],
        ["Spend", usd(d.llm_last_hour.cost_usd)]].map(([k, v]) => <div key={k} className="rounded-lg bg-paper/70 p-3"><dt className="eyebrow">{k}</dt><dd className="num mt-1 font-serif text-2xl">{v}</dd></div>)}</dl>
      <a href="/usage" className="mt-3 inline-block text-sm text-link">Usage &amp; costs →</a>
    </Card>
    <Card eyebrow="Last 24 hours" title="Scans and jobs">
      <div className="flex flex-wrap gap-2 text-sm">{Object.keys(d.scans_last_day).length === 0 ? <span className="text-soft">No scans.</span> :
        Object.entries(d.scans_last_day).map(([k, v]) => <Badge key={k} tone={k === "complete" ? "ok" : k === "failed" ? "bad" : k === "partial" ? "warn" : "muted"}>{k}: {String(v)}</Badge>)}</div>
      <p className="mt-3 text-sm text-muted">Outbox backlog: <b>{d.outbox.pending}</b>{d.outbox.oldest ? ` · oldest ${ago(d.outbox.oldest)}` : ""}</p>
      {d.connectors_attention.length > 0 && <div className="mt-3"><div className="eyebrow mb-1">Datasources needing attention</div>
        <ul className="space-y-1 text-sm">{d.connectors_attention.map((c: any) => <li key={c.project_id + c.name}><a className="text-link" href={`/projects/${c.project_id}/datasources`}>{c.name}</a>
          <span className="text-soft"> · {c.kind}</span> <Badge tone={c.last_status === "failed" ? "bad" : "warn"}>{c.last_status}</Badge></li>)}</ul></div>}
    </Card>
    <Card eyebrow="Operator consoles" title="Open the tools behind ArchTwin">
      <ul className="grid grid-cols-2 gap-2 text-sm">{[["Temporal UI", d.consoles.temporal_ui, "jobs & workflows"], ["Langfuse", d.consoles.langfuse, "LLM traces"],
        ["LiteLLM", d.consoles.litellm, "AI gateway, keys, models"], ["Keycloak", d.consoles.keycloak, "users & roles"]].map(([n, u, h]) =>
        <li key={n}><a href={u} target="_blank" rel="noopener noreferrer" className="flex items-start gap-2 rounded-lg border border-rule p-2 hover:border-muted">
          <ExternalLink size={14} className="mt-0.5 text-link" /><span><span className="block font-medium">{n}</span><span className="text-xs text-soft">{h}</span></span></a></li>)}</ul>
      <div className="mt-3 text-xs text-soft">Egress allow-list: {d.egress.private_hosts.join(", ") || "—"} · TLS not verified for: {d.egress.insecure_tls_hosts.join(", ") || "none"}</div>
    </Card>
  </div>;
}

function SpendLimits() {
  const lim = useApi<any>(["spend-limits"], "/admin/spend-limits");
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [filter, setFilter] = useState("");
  const [kind, setKind] = useState("");
  const [adding, setAdding] = useState(false);
  const save = useAction((items: { subject: string; monthly_usd: number | null }[]) => api("/admin/spend-limits", { method: "PUT", json: { items } }),
    [["spend-limits"], ["usage-ov"]], "Spend limits saved");
  const items: any[] = lim.data?.items ?? [];
  const shown = items.filter((i) => (!kind || i.kind === kind) && (!filter || i.label.toLowerCase().includes(filter.toLowerCase())));
  const at = items.filter((i) => i.pct >= 1).length, near = items.filter((i) => i.pct >= (lim.data?.warn_at ?? 0.8) && i.pct < 1).length;
  return <div className="space-y-4">
    <Card eyebrow="Cost control" title="Monthly spend controls">
      <dl className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">{[["Limits", items.length], ["At cap", at], ["Near cap · 80%+", near], ["Reset", "Monthly · UTC"]].map(([k, v]) =>
        <div key={String(k)} className="rounded-lg bg-paper/70 p-3"><dt className="eyebrow">{k}</dt><dd className="num mt-1 font-serif text-2xl">{v}</dd></div>)}</dl>
      <p className="mt-3 text-sm text-muted">A call is refused (HTTP 402) once any applicable cap is reached: the whole organization, the user, or the project. A cap of $0 blocks AI for that subject.</p>
    </Card>
    <Card actions={<Button variant="primary" onClick={() => setAdding(true)}><Plus size={14} /> Add limit</Button>} title="Limits">
      <div className="mb-3 flex flex-wrap gap-2"><Input className="max-w-xs" placeholder="Search" aria-label="Search limits" value={filter} onChange={(e) => setFilter(e.target.value)} />
        <Select aria-label="Scope filter" value={kind} onChange={(e) => setKind(e.target.value)}><option value="">All scopes</option><option value="global">Organization</option>
          <option value="project">Project</option><option value="user">User</option></Select></div>
      <ErrorBox error={lim.error ?? save.error} />
      {items.length === 0 && lim.data ? <p className="py-6 text-center text-sm text-soft">No limits yet — without limits, AI spend is unbounded. Add an organization-wide cap to start.</p> :
        <Table head={["Applies to", "Monthly limit (USD)", "Spent this month", "Used", ""]}>{shown.map((i) => <tr key={i.subject} className="border-b border-rule">
          <td className="px-2 py-1.5"><Badge>{i.kind === "global" ? "organization" : i.kind}</Badge> {i.label}</td>
          <td className="px-2"><Input type="number" min={0} step="0.01" aria-label={`Monthly limit for ${i.label}`} className="!w-28 text-right"
            value={edits[i.subject] ?? String(i.monthly_usd)} onChange={(e) => setEdits((x) => ({ ...x, [i.subject]: e.target.value }))} /></td>
          <td className="num px-2">{usd(i.spent_usd)}</td><td className="px-2"><CapBar pct={i.pct} warnAt={lim.data.warn_at} /></td>
          <td className="px-2 text-right"><Button size="sm" disabled={edits[i.subject] === undefined} onClick={() => save.mutate([{ subject: i.subject, monthly_usd: Number(edits[i.subject]) }])}><Save size={12} /> Save</Button>
            <Button size="sm" variant="ghost" aria-label={`Remove limit for ${i.label}`} onClick={() => confirm(`Remove the limit for ${i.label}?`) && save.mutate([{ subject: i.subject, monthly_usd: null }])}><Trash2 size={12} /></Button></td></tr>)}</Table>}
    </Card>
    <AddLimit open={adding} onClose={() => setAdding(false)} onSave={(it) => { save.mutate([it]); setAdding(false); }} />
  </div>;
}

function AddLimit({ open, onClose, onSave }: { open: boolean; onClose: () => void; onSave: (i: { subject: string; monthly_usd: number }) => void }) {
  const [kind, setKind] = useState("global");
  const [who, setWho] = useState("");
  const [amount, setAmount] = useState("50");
  const users = useApi<any[]>(["org-users"], open ? "/org/users" : null);
  const projects = useApi<Project[]>(["projects-all"], open ? "/projects" : null);
  const subject = kind === "global" ? "global" : `${kind}:${who}`;
  return <Dialog open={open} onClose={onClose} title="Add a monthly limit">
    <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); onSave({ subject, monthly_usd: Number(amount) }); }}>
      <Field label="Applies to"><Select value={kind} onChange={(e) => { setKind(e.target.value); setWho(""); }}><option value="global">The whole organization</option>
        <option value="project">A project</option><option value="user">A user</option></Select></Field>
      {kind === "user" && <Field label="User"><Select required value={who} onChange={(e) => setWho(e.target.value)}><option value="">Choose…</option>
        {users.data?.map((u) => <option key={u.id} value={u.id}>{u.display_name || u.username} ({u.username})</option>)}</Select></Field>}
      {kind === "project" && <Field label="Project"><Select required value={who} onChange={(e) => setWho(e.target.value)}><option value="">Choose…</option>
        {projects.data?.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</Select></Field>}
      <Field label="Monthly cap (USD)" hint="0 blocks every AI call for this subject."><Input type="number" min={0} step="0.01" required value={amount} onChange={(e) => setAmount(e.target.value)} /></Field>
      <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" disabled={kind !== "global" && !who}>Add limit</Button></div>
    </form>
  </Dialog>;
}

function SourceRoots() {
  const r = useApi<any>(["source-roots"], "/admin/source-roots");
  const [picking, setPicking] = useState(false);
  const save = useAction((roots: string[] | null) => api("/admin/source-roots", { method: "PUT", json: { roots } }), [["source-roots"]], "Source roots saved");
  const wl: string[] | null = r.data?.whitelist ?? null;
  return <div className="space-y-4">
    <Card eyebrow="Local directories" title="Which folders datasources may read">
      <p className="text-sm text-muted">ArchTwin can only see folders mounted read-only into its containers (the <b>boundary</b>, set by <code className="font-mono text-xs">ARCHTWIN_SOURCE_WORKSPACE</code>).
        Inside it, whitelist exactly the folders people may add as datasources. Without a whitelist the whole boundary is allowed. <code className="font-mono text-xs">{r.data?.builtin}</code> (ArchTwin’s own mounts) is always allowed.</p>
      <ErrorBox error={r.error ?? save.error} />
      {r.data && <div className="mt-3 grid gap-4 md:grid-cols-2">
        <div><div className="eyebrow mb-1">Mounted boundaries</div><ul className="space-y-1 font-mono text-xs">{r.data.boundaries.map((b: string) => <li key={b}>{b}</li>)}</ul></div>
        <div><div className="eyebrow mb-1">Effective roots</div><ul className="space-y-1 font-mono text-xs">{r.data.effective.map((b: string) => <li key={b} className="flex items-center gap-1"><CheckCircle2 size={12} className="text-ok" />{b}</li>)}</ul></div>
      </div>}
    </Card>
    <Card title="Whitelist" actions={<><Button onClick={() => setPicking(true)}><FolderOpen size={14} /> Add folder…</Button>
      {wl && <Button variant="ghost" onClick={() => confirm("Remove the whitelist and allow the whole mounted boundary again?") && save.mutate(null)}><RotateCcw size={14} /> Allow whole boundary</Button>}</>}>
      {!wl ? <p className="text-sm text-soft">No whitelist: every folder inside the boundaries is allowed. Add a folder to restrict datasources to it.</p> :
        <Table head={["Folder", ""]}>{wl.map((f) => <tr key={f} className="border-b border-rule"><td className="px-2 py-1.5 font-mono text-xs">{f}</td>
          <td className="px-2 text-right"><Button size="sm" variant="ghost" aria-label={`Remove ${f}`} onClick={() => save.mutate(wl.filter((x) => x !== f))}><Trash2 size={12} /></Button></td></tr>)}</Table>}
      <FolderPicker endpoint="/admin/source-folders" title="Whitelist a folder" open={picking} value="" onClose={() => setPicking(false)}
        onChoose={(p) => { setPicking(false); save.mutate([...new Set([...(wl ?? []), p])]); }} />
    </Card>
  </div>;
}
