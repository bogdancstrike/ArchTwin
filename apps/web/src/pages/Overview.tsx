import { Link } from "@tanstack/react-router";
import { AlertTriangle, ArrowRight, BookCheck, CheckCircle2, CircleDashed, Network, Radar, ShieldCheck } from "lucide-react";
import { ago, Badge, Card, Empty, FreshnessBadge, SeverityBar, Spinner, StatTile, StatusDot } from "@/components/ui";
import { useApi } from "@/lib/hooks";

interface ScanRow { id: string; status: string; revision?: string; ref?: string; created_at: string; finished_at?: string; connector: string; kind: string; stats: Record<string, any> }
interface Hist { version: number; nodes: number; edges: number; at: string }

/** Tiny inline sparkline of element counts per snapshot version (no chart library needed for 12 points). */
function Spark({ data }: { data: Hist[] }) {
  if (data.length < 2) return null;
  const w = 220, h = 44, max = Math.max(...data.map((d) => d.nodes)), min = Math.min(...data.map((d) => d.nodes));
  const x = (i: number) => (i / (data.length - 1)) * (w - 8) + 4, y = (v: number) => h - 6 - ((v - min) / Math.max(1, max - min)) * (h - 12);
  const pts = data.map((d, i) => `${x(i)},${y(d.nodes)}`).join(" ");
  return <svg width={w} height={h} role="img" aria-label={`Elements per snapshot: ${data.map((d) => `v${d.version} ${d.nodes}`).join(", ")}`}>
    <polyline points={`4,${h} ${pts} ${w - 4},${h}`} fill="var(--color-accent-tint)" stroke="none" />
    <polyline points={pts} fill="none" stroke="var(--color-accent)" strokeWidth={1.75} strokeLinejoin="round" strokeLinecap="round" />
    {data.map((d, i) => <circle key={d.version} cx={x(i)} cy={y(d.nodes)} r={i === data.length - 1 ? 3.5 : 2} fill={i === data.length - 1 ? "var(--color-accent)" : "var(--color-card)"} stroke="var(--color-accent)" strokeWidth={1.25}><title>v{d.version}: {d.nodes} elements</title></circle>)}
  </svg>;
}

function OriginBar({ by }: { by: Record<string, number> }) {
  const order = [["static", "bg-link", "code & config"], ["runtime", "bg-ok", "running"], ["desired", "bg-accent", "designed"], ["manual", "bg-accent/60", "manual"], ["inferred", "bg-soft/50", "inferred"]] as const;
  const total = Object.values(by).reduce((a, b) => a + b, 0);
  if (!total) return null;
  return <div>
    <div className="flex h-2 overflow-hidden rounded-full bg-paper-2">{order.map(([k, c]) => by[k] ? <div key={k} className={c} style={{ width: `${(by[k] / total) * 100}%` }} /> : null)}</div>
    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">{order.map(([k, c, l]) => by[k] ? <span key={k} className="flex items-center gap-1.5"><span className={`h-2 w-2 rounded-full ${c}`} />{l} <b className="num text-ink">{by[k].toLocaleString()}</b></span> : null)}</div>
  </div>;
}

export function OverviewPage({ projectId }: { projectId: string }) {
  const h = useApi<any>(["home", projectId], `/projects/${projectId}/home`, { refetchInterval: 10_000 });
  if (h.isLoading || !h.data) return <Spinner />;
  const d = h.data;
  const a = d.architecture, dr = d.drift, de = d.decisions;
  const sevCounts: Record<string, number> = {};
  for (const r of dr.by ?? []) if (r.verdict === "drift") sevCounts[r.severity] = (sevCounts[r.severity] ?? 0) + r.n;
  const base = `/projects/${projectId}`;
  const off = (c: any) => !c.configured && <p className="text-sm text-soft">{c.reason ?? "Not configured yet."}</p>;
  return <div className="mx-auto max-w-7xl space-y-6 p-6">
    <section aria-label="Key figures" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatTile label="Elements" value={a.snapshot ? a.snapshot.node_count.toLocaleString() : "—"} icon={<Network size={16} />}
        hint={a.snapshot ? `${a.snapshot.edge_count.toLocaleString()} relationships · v${a.snapshot.version}` : a.reason ?? "no snapshot yet"} />
      <StatTile label="Open drift" value={dr.configured ? dr.open : "—"} tone={dr.configured ? (dr.open ? "accent" : "ok") : undefined} icon={<AlertTriangle size={16} />}
        hint={dr.configured ? "deterministic, evidence-backed" : dr.reason} />
      <StatTile label="Unknown" value={dr.configured ? dr.unknown : "—"} icon={<CircleDashed size={16} />} hint="missing / stale evidence — never alerts" />
      <StatTile label="Decisions" value={de.configured ? de.adrs : "—"} icon={<BookCheck size={16} />}
        hint={de.configured ? `${de.accepted} accepted · ${de.proposed} proposed` : de.reason} />
    </section>

    <div className="grid gap-6 lg:grid-cols-3">
      <Card className="lg:col-span-2" eyebrow="Architecture" title="Model over time" actions={<Link className="flex items-center gap-1 text-sm text-link" to="/projects/$projectId/architecture" params={{ projectId }}>Open diagrams <ArrowRight size={14} /></Link>}>
        {off(a) || (a.snapshot && <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <div className="flex items-baseline gap-3"><span className="serif text-6xl leading-none">v{a.snapshot.version}</span><span className="text-sm text-muted">{ago(a.snapshot.created_at)} · {a.snapshot.trigger}</span></div>
            <p className="mt-2 font-mono text-xs text-soft">manifest {a.snapshot.manifest_hash.slice(0, 16)}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {a.baseline ? <Badge tone="ok"><ShieldCheck size={11} /> baseline v{a.baseline.version} approved</Badge> : <Badge>no approved baseline</Badge>}
              {a.pending_baselines > 0 && <Badge tone="link">{a.pending_baselines} awaiting review</Badge>}
            </div>
          </div>
          <div className="text-right"><Spark data={a.history ?? []} /><div className="eyebrow mt-1">elements per snapshot</div></div>
        </div>)}
        <div className="mt-5 border-t border-rule pt-4"><div className="eyebrow mb-2">Evidence by origin</div>
          {Object.keys(d.freshness.observations_by_origin ?? {}).length ? <OriginBar by={d.freshness.observations_by_origin} /> : <p className="text-sm text-soft">No observations yet.</p>}</div>
      </Card>

      <Card eyebrow="Evidence" title="Sources" actions={<Link className="flex items-center gap-1 text-sm text-link" to="/projects/$projectId/datasources" params={{ projectId }}>Datasources <ArrowRight size={14} /></Link>}>
        {!d.freshness.configured ? <p className="text-sm text-soft">No datasources yet — add one in Datasources. Until then everything is <b>UNKNOWN</b>, never “absent”.</p>
          : <ul className="space-y-2.5">{d.freshness.connectors.map((c: any) => <li key={c.id} className="flex items-center gap-3">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-paper-2 font-mono text-[10px] uppercase text-muted">{c.kind.slice(0, 3)}</span>
            <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{c.name}</span><span className="block truncate text-xs text-soft">{c.freshness.reason ?? c.kind}</span></span>
            <FreshnessBadge f={c.freshness} /></li>)}</ul>}
      </Card>
    </div>

    <div className="grid gap-6 lg:grid-cols-3">
      <Card eyebrow="Drift" title="Top findings" actions={<Link className="flex items-center gap-1 text-sm text-link" to="/projects/$projectId/drift" params={{ projectId }}>Triage <ArrowRight size={14} /></Link>}>
        {off(dr) || <>
          <SeverityBar counts={sevCounts} />
          {(dr.top ?? []).length === 0 ? <div className="mt-3 flex items-center gap-2 text-sm text-ok"><CheckCircle2 size={16} /> No open drift against the baseline.</div>
            : <ul className="mt-3 space-y-1">{dr.top.map((f: any) => <li key={f.id}><Link to={`${base}/drift/${f.id}`} className="-mx-2 flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-paper/70">
              <StatusDot status={f.severity} /><span className="min-w-0 flex-1"><span className="block truncate text-sm">{f.title}</span><span className="block truncate font-mono text-[11px] text-soft">{f.subject_key}</span></span></Link></li>)}</ul>}
        </>}
      </Card>
      <Card eyebrow="Activity" title="Recent scans">
        {(d.freshness.recent_scans ?? []).length === 0 ? <p className="text-sm text-soft">No scans yet.</p> :
          <ul className="space-y-2.5">{d.freshness.recent_scans.map((s: ScanRow) => <li key={s.id} className="flex items-start gap-2.5">
            <StatusDot status={s.status} className="mt-1.5" />
            <div className="min-w-0 flex-1"><div className="truncate text-sm"><b className="font-medium">{s.connector}</b> <span className="text-soft">· {s.status}</span></div>
              <div className="truncate text-xs text-soft">{(s.stats?.observations ?? 0).toLocaleString()} observations{s.revision ? ` · ${s.revision.slice(0, 10)}` : ""} · {ago(s.finished_at ?? s.created_at)}</div></div>
          </li>)}</ul>}
      </Card>
      <Card eyebrow="Decisions" title="Latest ADRs" actions={<Link className="flex items-center gap-1 text-sm text-link" to="/projects/$projectId/decisions" params={{ projectId }}>Decisions <ArrowRight size={14} /></Link>}>
        {off(de) || ((de.recent ?? []).length === 0 ? <Empty title="No decisions yet">Record the first ADR — or let the assistant draft one.</Empty> :
          <ul className="space-y-2">{de.recent.map((x: any) => <li key={x.id} className="flex items-start gap-2.5">
            <span className="mt-0.5 font-mono text-[11px] text-soft">{String(x.number).padStart(4, "0")}</span>
            <span className="min-w-0 flex-1 text-sm leading-snug">{x.title}</span>
            <Badge tone={{ accepted: "ok", proposed: "link", rejected: "bad", superseded: "muted" }[x.status as string] ?? "muted"}>{x.status}</Badge></li>)}</ul>)}
        <div className="mt-4 flex items-center gap-2 border-t border-rule pt-3 text-xs text-muted"><Radar size={13} />
          {d.assistant.configured ? <>Assistant enabled — <Link to="/projects/$projectId/assistant" params={{ projectId }} className="text-link">ask about this architecture</Link></> : "Assistant is off for this project."}</div>
      </Card>
    </div>
  </div>;
}
