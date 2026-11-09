import { Activity, ArrowLeft, Box, CheckCircle2, Database, FolderGit2, FolderOpen, GitBranch, GitMerge, Globe, KeyRound, Play, Plus, Radio, ShieldCheck, SquareKanban, Trash2, Webhook, XCircle } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Badge, Button, Card, Dialog, Empty, ErrorBox, Field, FreshnessBadge, Input, OriginBadges, Skeleton, StatTile, StatusDot, Table, Textarea, ago, cn } from "@/components/ui";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { Connector, Scan } from "@/lib/types";

interface Kind { kind: string; name: string; origin: string; category: string; scopes: string[]; enabled: boolean; flag: string; module_flag: string;
  config: Record<string, unknown>; secret?: Record<string, string>; webhooks?: string[]; source_roots?: string[] }

const ICONS: Record<string, typeof Box> = { git: FolderOpen, github: FolderGit2, gitlab: GitMerge, taiga: SquareKanban, docker: Box, otel_servicegraph: Activity, postgresql: Database, mysql: Database,
  kafka: Radio, http_openapi: Globe };
const CATEGORIES: [string, string, string][] = [["code", "Code & repositories", "static evidence: what the code and config declare"],
  ["runtime", "Runtime", "what is actually running and calling what"], ["data", "Data stores", "catalog metadata — never rows"],
  ["messaging", "Messaging", "topics, consumer groups, schemas — never payloads"], ["api", "APIs", "live API contracts"],
  ["work", "Work tracking", "plans and status: epics, stories, tasks, sprints — read-only"]];

const PRESETS: Record<string, { config: object }> = {
  git: { config: { path: "/sources/archtwin/fixtures/shop", content: "auto" } },
  gitlab: { config: { projects: ["https://gitlab.example.com/group/subgroup/project"], branches: [], issues: true, merge_requests: true, analyze_code: true, max_items: 200 } },
  taiga: { config: { url: "https://taiga.example.com/project/my-project/kanban", epics: true, user_stories: true, tasks: true, issues: true, sprints: true } },
  github: { config: { repos: ["owner/name"], branches: ["main"], issues: true, pull_requests: true, analyze_code: true, max_items: 200 } },
  docker: { config: { endpoint: "http://docker-proxy:2375", compose_projects: ["archtwin-fixtures"] } },
  otel_servicegraph: { config: { prometheus_url: "http://prometheus:9090", system: "archtwin-fixtures", window: "15m", service_map: {}, peer_map: { orders: "orders-db", inventory: "inventory-db" } } },
  postgresql: { config: { host: "orders-db", port: 5432, database: "orders", username: "archtwin_catalog_ro", schemas: ["public"], system: "archtwin-fixtures", service: "orders-db" } },
  mysql: { config: { host: "inventory-db", port: 3306, database: "inventory", username: "archtwin_catalog_ro", system: "archtwin-fixtures", service: "inventory-db" } },
  kafka: { config: { bootstrap_servers: "kafka:9092", system: "archtwin-fixtures", service: "kafka", schema_registry_url: "http://schema-registry:8081", group_services: { billing: "shop-billing" } } },
  http_openapi: { config: { url: "http://api:8000/api/openapi.json", system: "archtwin", service: "api" } },
};
const pretty = (o: object | undefined) => (o ? JSON.stringify(o, null, 2) : "");

function KindIcon({ kind, className }: { kind: string; className?: string }) {
  const I = ICONS[kind] ?? Box;
  return <span className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-rule bg-paper text-muted", className)}><I size={17} /></span>;
}

function AddConnector({ projectId, open, onClose }: { projectId: string; open: boolean; onClose: () => void }) {
  const kinds = useApi<Kind[]>(["kinds", projectId], `/connector-kinds?project_id=${projectId}`);
  const [kind, setKind] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [config, setConfig] = useState("");
  const [secret, setSecret] = useState<Record<string, string>>({});
  const [jsonErr, setJsonErr] = useState<string | null>(null);
  const create = useAction(() => api("/projects/" + projectId + "/connectors", { method: "POST", idempotent: true, json: {
    kind, name, config: JSON.parse(config), secret: Object.values(secret).some((v) => v.trim()) ? Object.fromEntries(Object.entries(secret).filter(([, v]) => v.trim())) : null } }),
    [["connectors", projectId]], "Datasource added");
  const k = kinds.data?.find((x) => x.kind === kind);
  const pick = (x: Kind) => {
    const preset = { ...(PRESETS[x.kind]?.config ?? {}) } as Record<string, unknown>;
    if (x.kind === "git" && x.source_roots?.length) preset.path = x.source_roots[x.source_roots.length - 1];
    setKind(x.kind); setName(x.kind === "git" ? "local-sources" : x.kind.replace("_", "-")); setConfig(pretty(preset)); setSecret({}); setJsonErr(null);
  };
  const close = () => { setKind(null); setSecret({}); onClose(); };
  return <Dialog open={open} onClose={close} title={k ? `Add ${k.name}` : "Add a source of evidence"} wide>
    {!k ? <div className="space-y-5">
      <p className="text-sm text-muted">Every datasource is <b>read-only</b>. Credentials are sealed with envelope encryption and never shown again.</p>
      {kinds.isLoading && <Skeleton className="h-40" />}
      {CATEGORIES.map(([cat, label, hint]) => {
        const ks = (kinds.data ?? []).filter((x) => x.category === cat);
        if (!ks.length) return null;
        return <section key={cat}><div className="mb-2 flex items-baseline gap-2"><h3 className="text-sm font-semibold">{label}</h3><span className="text-xs text-soft">{hint}</span></div>
          <div className="grid gap-2 sm:grid-cols-2">{ks.map((x) => <button key={x.kind} disabled={!x.enabled} onClick={() => pick(x)}
            className="group flex items-start gap-3 rounded-xl border border-rule bg-card p-3 text-left shadow-card transition enabled:hover:-translate-y-0.5 enabled:hover:shadow-lift disabled:cursor-not-allowed disabled:opacity-55">
            <KindIcon kind={x.kind} className="group-enabled:group-hover:border-accent/40 group-enabled:group-hover:text-accent" />
            <span className="min-w-0"><span className="block text-sm font-medium">{x.name}</span>
              <span className="mt-0.5 block text-xs text-soft">{x.enabled ? <>origin <b>{x.origin}</b>{x.webhooks ? " · webhooks" : ""}</> : <>off — enable <code className="font-mono">{x.flag}</code></>}</span></span>
          </button>)}</div></section>;
      })}
    </div> : <form className="space-y-3" onSubmit={async (e) => {
      e.preventDefault();
      try { JSON.parse(config); } catch (err) { setJsonErr((err as Error).message); return; }
      await create.mutateAsync(undefined as never); close(); }}>
      <button type="button" onClick={() => setKind(null)} className="flex items-center gap-1 text-xs text-link"><ArrowLeft size={13} /> All datasource types</button>
      <div className="flex items-start gap-3 rounded-lg bg-paper/70 p-3"><KindIcon kind={k.kind} />
        <div className="min-w-0 text-xs text-muted"><div className="flex items-center gap-1.5"><ShieldCheck size={14} className="text-ok" /> read-only · origin <Badge>{k.origin}</Badge></div>
          <div className="mt-1.5 flex flex-wrap gap-1">{k.scopes.map((s) => <Badge key={s} tone="link">{s}</Badge>)}</div></div></div>
      <Field label="Name"><Input required value={name} onChange={(e) => setName(e.target.value)} /></Field>
      {k.kind === "git" && k.source_roots?.length ? <p className="rounded-lg bg-paper/70 p-2 text-xs text-muted">Local directories must be under a mounted source root:{" "}
        {k.source_roots.map((r) => <code key={r} className="mr-1 font-mono">{r}</code>)}. A folder of repositories scans each repository as its own system;
        set <code className="font-mono">content</code> to <code className="font-mono">docs</code> for documentation or architecture folders.</p> : null}
      <Field label="Configuration (JSON)" hint={Object.entries(k.config).slice(0, 5).map(([a, b]) => `${a}: ${typeof b === "string" ? b : JSON.stringify(b)}`).join(" · ")}>
        <Textarea rows={8} className="font-mono text-xs" value={config} onChange={(e) => setConfig(e.target.value)} spellCheck={false} /></Field>
      {k.secret && Object.keys(k.secret).length > 0 && <fieldset className="space-y-2 rounded-lg border border-rule p-3">
        <legend className="flex items-center gap-1.5 px-1 text-sm font-medium"><KeyRound size={14} /> Credentials <span className="font-normal text-soft">(optional)</span></legend>
        <p className="text-xs text-soft">Sealed with envelope encryption; never returned, logged or sent to the AI. Use read-only credentials.</p>
        {Object.entries(k.secret).map(([key, hint]) => <Field key={key} label={key.replace(/_/g, " ")} hint={String(hint)}>
          <Input type={key === "username" ? "text" : "password"} autoComplete={key === "username" ? "off" : "new-password"} aria-label={`credential ${key}`}
            className="font-mono text-xs" value={secret[key] ?? ""} onChange={(e) => setSecret((s) => ({ ...s, [key]: e.target.value }))} /></Field>)}
      </fieldset>}
      {jsonErr && <div role="alert" className="text-sm text-bad">Invalid JSON: {jsonErr}</div>}
      <ErrorBox error={create.error} />
      <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={close}>Cancel</Button><Button variant="primary" disabled={create.isPending}>Add datasource</Button></div>
    </form>}
  </Dialog>;
}

function WebhookDialog({ projectId, c, onClose }: { projectId: string; c: Connector | null; onClose: () => void }) {
  const w = useApi<any>(["webhook", c?.id], c ? `/projects/${projectId}/connectors/${c.id}/webhook` : null, { refetchInterval: 5000 });
  return <Dialog open={!!c} onClose={onClose} title={`Webhooks · ${c?.name ?? ""}`} wide>
    {!w.data ? <Skeleton className="h-24" /> : <div className="space-y-4 text-sm">
      {!w.data.enabled && <div className="rounded-lg border border-warn/30 bg-warn/10 p-3 text-warn-ink">Webhooks are off (<code>connectors.webhooks</code>). Polling and scheduled reconciliation still converge.</div>}
      <Field label="Payload URL"><Input readOnly value={w.data.url} className="font-mono text-xs" onFocus={(e) => e.target.select()} /></Field>
      <p className="text-muted">Signature: <code className="font-mono text-xs">{w.data.signature}</code> using the connector's <code className="font-mono text-xs">webhook_secret</code>. Events: {w.data.events.join(", ")}.
        Redeliveries are de-duplicated; a commit is extracted once.</p>
      <div><div className="eyebrow mb-1">Recent deliveries</div>
        {w.data.recent.length === 0 ? <p className="text-soft">None yet.</p> : <Table head={["Delivery", "Event", "Outcome", "Received"]}>{w.data.recent.map((d: any) =>
          <tr key={d.delivery_id} className="border-b border-rule"><td className="px-2 py-1.5 font-mono text-xs">{d.delivery_id.slice(0, 14)}</td><td className="px-2">{d.event}</td>
            <td className="px-2"><Badge tone={d.outcome.includes("queued") || d.outcome.includes("updated") ? "ok" : "muted"}>{d.outcome}</Badge></td><td className="px-2 text-xs">{ago(d.received_at)}</td></tr>)}</Table>}
      </div>
    </div>}
  </Dialog>;
}

function ConnectorCard({ c, projectId, lastScan, onWebhook, children }: { c: Connector; projectId: string; lastScan?: Scan; onWebhook?: () => void; children?: ReactNode }) {
  const [ref, setRef] = useState("");
  const [test, setTest] = useState<any>(null);
  const [testing, setTesting] = useState(false);
  const scan = useAction((v: { ref?: string }) => api(`/projects/${projectId}/connectors/${c.id}/scan`, { method: "POST", idempotent: true, json: { ref: v.ref || null } }), [["scans", projectId]], "Scan queued");
  const del = useAction(() => api(`/projects/${projectId}/connectors/${c.id}`, { method: "DELETE" }), [["connectors", projectId]], "Connector removed — its evidence stays; coverage lapses to UNKNOWN");
  const running = lastScan && ["queued", "running"].includes(lastScan.status);
  return <article className="flex flex-col rounded-xl border border-rule bg-card p-4 shadow-card">
    <div className="flex items-start gap-3">
      <KindIcon kind={c.kind} />
      <div className="min-w-0 flex-1"><div className="flex items-center gap-2"><h3 className="truncate font-semibold tracking-tight">{c.name}</h3><FreshnessBadge f={c.freshness} /></div>
        <div className="truncate font-mono text-[11px] text-soft" title={JSON.stringify(c.config)}>{c.kind} · {Object.values(c.config).filter((v) => typeof v === "string").slice(0, 2).join(" · ")}</div></div>
    </div>
    <div className="mt-3 flex items-center gap-2 text-xs text-muted">
      {lastScan ? <><StatusDot status={lastScan.status} className={running ? "animate-pulse" : ""} /><span>{lastScan.status}</span><span className="text-soft">·</span>
        <span>{String(lastScan.stats?.observations ?? 0)} obs</span>{lastScan.revision && <><span className="text-soft">·</span><span className="truncate font-mono">{lastScan.revision.slice(0, 10)}</span></>}
        <span className="ml-auto text-soft">{ago(lastScan.finished_at ?? lastScan.created_at)}</span></> : <span className="text-soft">never scanned</span>}
    </div>
    {c.freshness.reason && <div className="mt-1 text-[11px] text-soft">{c.freshness.reason}</div>}
    {lastScan?.error && <div className="mt-1 text-[11px] text-bad">{lastScan.error}</div>}
    {test && <div className={cn("mt-2 rounded-lg p-2 text-xs", test.ok ? "bg-ok/10 text-ok" : "bg-bad/10 text-bad")}>
      <div className="flex items-center gap-1.5 font-medium">{test.ok ? <CheckCircle2 size={13} /> : <XCircle size={13} />} {test.ok ? "Connection OK" : "Connection failed"}</div>
      {test.warnings?.map((w: string) => <div key={w} className="mt-0.5 text-warn-ink">⚠ {w}</div>)}</div>}
    {children}
    <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-3">
      {["git", "github", "gitlab"].includes(c.kind) && <Input aria-label={`ref for ${c.name}`} className="!w-28 font-mono text-xs" placeholder="HEAD" value={ref} onChange={(e) => setRef(e.target.value)} />}
      <Button size="sm" variant="primary" disabled={!!running} onClick={() => scan.mutate({ ref })}><Play size={12} /> Scan</Button>
      <Button size="sm" disabled={testing} onClick={async () => { setTesting(true); try { setTest(await api(`/projects/${projectId}/connectors/${c.id}/test`, { method: "POST" })); } catch (e) { setTest({ ok: false, warnings: [(e as Error).message] }); } finally { setTesting(false); } }}>{testing ? "Testing…" : "Test"}</Button>
      {onWebhook && <Button size="sm" variant="ghost" onClick={onWebhook} aria-label={`Webhooks for ${c.name}`}><Webhook size={13} /></Button>}
      <Button size="sm" variant="ghost" className="ml-auto hover:!text-bad" aria-label={`Remove ${c.name}`} onClick={() => confirm(`Remove ${c.name}? Its evidence stays; coverage lapses to UNKNOWN.`) && del.mutate(undefined as never)}><Trash2 size={13} /></Button>
    </div>
  </article>;
}

export function InventoryPage({ projectId }: { projectId: string }) {
  const cs = useApi<Connector[]>(["connectors", projectId], `/projects/${projectId}/connectors`, { refetchInterval: 5000 });
  const scans = useApi<Scan[]>(["scans", projectId], `/projects/${projectId}/scans`, { refetchInterval: 4000 });
  const inv = useApi<any>(["inventory", projectId], `/projects/${projectId}/inventory`, { refetchInterval: 10_000 });
  const kinds = useApi<Kind[]>(["kinds", projectId], `/connector-kinds?project_id=${projectId}`);
  const [open, setOpen] = useState(false);
  const [hook, setHook] = useState<Connector | null>(null);
  const names = Object.fromEntries((cs.data ?? []).map((c) => [c.id, c.name]));
  const last = (id: string) => scans.data?.find((s) => s.connector_id === id);
  const counts: { origin: string; kind: string; n: number }[] = inv.data?.observation_counts ?? [];
  const total = counts.reduce((a, r) => a + r.n, 0);
  const byOrigin = counts.reduce<Record<string, number>>((a, r) => ({ ...a, [r.origin]: (a[r.origin] ?? 0) + r.n }), {});
  const max = Math.max(1, ...counts.map((r) => r.n));
  const cat = (k: string) => kinds.data?.find((x) => x.kind === k)?.category ?? "other";
  const hookable = new Set((kinds.data ?? []).filter((k) => k.webhooks).map((k) => k.kind));
  return <div className="space-y-6 p-6">
    <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatTile label="Datasources" value={cs.data?.length ?? "—"} icon={<Plus size={16} />} hint={`${(cs.data ?? []).filter((c) => c.freshness.status === "current").length} current`} />
      <StatTile label="Observations" value={total.toLocaleString()} icon={<Activity size={16} />} hint="append-only, with provenance" />
      <StatTile label="Static" value={(byOrigin.static ?? 0).toLocaleString()} tone="link" icon={<GitBranch size={16} />} hint="code & configuration" />
      <StatTile label="Runtime" value={(byOrigin.runtime ?? 0).toLocaleString()} tone="ok" icon={<Box size={16} />} hint="running systems, catalogs, traces" />
    </section>
    <div className="flex items-end justify-between">
      <div><div className="eyebrow">Read-only datasources</div><h2 className="serif text-3xl">Datasources</h2></div>
      <Button variant="primary" onClick={() => setOpen(true)}><Plus size={15} /> Add datasource</Button>
    </div>
    {cs.isLoading && <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-44 !rounded-xl" />)}</div>}
    <ErrorBox error={cs.error} />
    {cs.data?.length === 0 && <Empty title="No datasources yet">Add local directories (code, docs, architecture), GitLab or GitHub projects, Taiga boards, a Docker host or OTel service graph, a database catalog, a Kafka cluster or a live OpenAPI document.
      Until then everything is <b>UNKNOWN</b>, never “absent”.</Empty>}
    {CATEGORIES.map(([k, label]) => {
      const list = (cs.data ?? []).filter((c) => cat(c.kind) === k);
      if (!list.length) return null;
      return <section key={k} className="space-y-2"><h3 className="eyebrow">{label}</h3>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{list.map((c) => <ConnectorCard key={c.id} c={c} projectId={projectId} lastScan={last(c.id)}
          onWebhook={hookable.has(c.kind) ? () => setHook(c) : undefined} />)}</div></section>;
    })}
    <div className="grid gap-6 lg:grid-cols-2">
      <Card eyebrow="Jobs" title="Recent scans"><Table head={["Datasource", "Status", "Revision", "Observations", "When"]}>{scans.data?.slice(0, 15).map((s) => <tr key={s.id} className="border-b border-rule">
        <td className="px-2 py-1.5">{names[s.connector_id] ?? "—"}</td><td className="px-2"><Badge tone={{ complete: "ok", partial: "warn", failed: "bad", running: "link", queued: "muted", skipped: "warn" }[s.status]}>{s.status}</Badge>{s.error && <div className="max-w-56 truncate text-[10px] text-bad" title={s.error}>{s.error}</div>}</td>
        <td className="px-2 font-mono text-xs">{(s.revision ?? "").slice(0, 10)}{s.ref ? ` (${s.ref.slice(0, 18)})` : ""}</td><td className="num px-2">{String(s.stats?.observations ?? "")}</td><td className="px-2 text-xs">{ago(s.finished_at ?? s.created_at)}</td></tr>)}</Table></Card>
      <Card eyebrow="Normalized" title="Observations by origin and kind"><Table head={["Origin", "Kind", "Count"]}>
        {[...counts].sort((a, b) => b.n - a.n).slice(0, 18).map((r) => <tr key={r.origin + r.kind} className="border-b border-rule"><td className="px-2 py-1"><OriginBadges origins={[r.origin]} /></td><td className="px-2">{r.kind}</td>
          <td className="px-2"><div className="flex items-center gap-2"><div className="h-1.5 flex-1 rounded-full bg-paper-2"><div className="h-1.5 rounded-full bg-muted/50" style={{ width: `${(r.n / max) * 100}%` }} /></div><span className="num w-12 text-right">{r.n}</span></div></td></tr>)}</Table></Card>
    </div>
    <AddConnector projectId={projectId} open={open} onClose={() => setOpen(false)} />
    <WebhookDialog projectId={projectId} c={hook} onClose={() => setHook(null)} />
  </div>;
}
