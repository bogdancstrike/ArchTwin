import { Link } from "@tanstack/react-router";
import { AlertTriangle, ArrowRight, BookCheck, Boxes, CheckCircle2, CircleDashed, GitBranch, Network, Plus, Radar, ScrollText, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { ago, Avatar, Badge, Button, Card, Empty, ErrorBox, SeverityBar, Skeleton, StatTile, StatusDot } from "@/components/ui";
import { useApi, useMe } from "@/lib/hooks";
import { NewProjectDialog } from "./Projects";

export interface HomeProject {
  id: string; title: string; purpose: string; tags: string[]; my_role?: string | null; connectors: number; freshness: string;
  freshness_counts: Record<string, number>; snapshot: { version: number; nodes: number; edges: number; at: string } | null;
  drift: { open: number; unknown: number; by_severity: Record<string, number> } | null;
  adrs: { total: number; proposed: number; accepted: number } | null; last_activity: string;
}
interface Item { kind: string; severity?: string; status?: string; project_id: string; project: string; title: string; detail: string; link?: string; at?: string }
export interface HomeData {
  generated_at: string; projects: HomeProject[]; attention: Item[]; activity: Item[];
  totals: { projects: number; connectors: number; elements: number; relationships: number; drift_open: number; unknown: number; adrs: number; stale_connectors: number };
}

const KIND_ICON: Record<string, typeof Boxes> = { scan: Radar, drift: AlertTriangle, adr: ScrollText, baseline: ShieldCheck, connector: GitBranch };

function greeting() {
  const h = new Date().getHours();
  return h < 5 ? "Working late" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export function ProjectHealthCard({ p }: { p: HomeProject }) {
  return <Link to="/projects/$projectId" params={{ projectId: p.id }} className="group block h-full">
    <article className="flex h-full flex-col rounded-xl border border-rule bg-card p-4 shadow-card transition group-hover:-translate-y-0.5 group-hover:shadow-lift">
      <div className="flex items-start gap-3">
        <Avatar name={p.title} size={36} />
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-semibold tracking-tight">{p.title}</h3>
          <p className="line-clamp-1 text-xs text-muted">{p.purpose || "No purpose stated."}</p>
        </div>
        <ArrowRight size={16} className="mt-1 text-soft opacity-0 transition group-hover:translate-x-0.5 group-hover:opacity-100" />
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg bg-paper/70 py-2"><dt className="eyebrow !text-[9px]">elements</dt><dd className="num text-lg font-semibold">{p.snapshot?.nodes ?? "—"}</dd></div>
        <div className="rounded-lg bg-paper/70 py-2"><dt className="eyebrow !text-[9px]">drift</dt>
          <dd className={`num text-lg font-semibold ${p.drift?.open ? "text-accent" : ""}`}>{p.drift ? p.drift.open : "—"}</dd></div>
        <div className="rounded-lg bg-paper/70 py-2"><dt className="eyebrow !text-[9px]">ADRs</dt><dd className="num text-lg font-semibold">{p.adrs?.total ?? "—"}</dd></div>
      </dl>
      <div className="mt-3"><SeverityBar counts={p.drift?.by_severity ?? {}} /></div>
      <div className="mt-auto flex items-center justify-between pt-3 text-xs text-muted">
        <span className="flex items-center gap-1.5" title={`Evidence freshness: ${p.freshness}`}><StatusDot status={p.freshness} />
          {p.connectors ? `${p.connectors} connector${p.connectors > 1 ? "s" : ""} · ${p.freshness}` : "no connectors"}</span>
        <span>{p.snapshot ? `v${p.snapshot.version} · ` : ""}{ago(p.last_activity)}</span>
      </div>
    </article>
  </Link>;
}

function AttentionList({ items }: { items: Item[] }) {
  if (!items.length) return <div className="flex items-center gap-3 rounded-lg bg-ok/8 p-4 text-sm text-ok"><CheckCircle2 size={18} />Nothing needs you right now — evidence is fresh and nothing awaits review.</div>;
  return <ul className="divide-y divide-rule">{items.map((a, i) => {
    const I = KIND_ICON[a.kind] ?? CircleDashed;
    const hot = a.severity === "critical" || a.severity === "high";
    return <li key={i}><Link to={a.link ?? "/home"} className="-mx-2 flex items-start gap-3 rounded-lg px-2 py-2.5 transition hover:bg-paper/70">
      <span className={`mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg ${hot ? "bg-accent-tint text-accent" : "bg-paper-2 text-muted"}`}><I size={15} /></span>
      <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{a.title}</span>
        <span className="block truncate text-xs text-muted">{a.project}{a.detail ? ` · ${a.detail}` : ""}</span></span>
      {a.severity && <Badge tone={{ critical: "bad", high: "accent", medium: "warn", low: "muted" }[a.severity]}>{a.severity}</Badge>}
    </Link></li>;
  })}</ul>;
}

function Activity({ items }: { items: Item[] }) {
  if (!items.length) return <p className="text-sm text-soft">No activity yet.</p>;
  return <ol className="relative space-y-3 before:absolute before:bottom-1 before:left-[13px] before:top-1 before:w-px before:bg-rule">{items.map((a, i) => {
    const I = KIND_ICON[a.kind] ?? CircleDashed;
    return <li key={i} className="relative flex gap-3">
      <span className="z-10 grid h-7 w-7 shrink-0 place-items-center rounded-full border border-rule bg-card text-muted"><I size={13} /></span>
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="flex items-center gap-2"><span className="truncate text-sm">{a.title}</span>{a.status && <StatusDot status={a.status} />}</div>
        <div className="truncate text-xs text-soft"><Link to="/projects/$projectId" params={{ projectId: a.project_id }} className="hover:text-link">{a.project}</Link>
          {a.detail ? ` · ${a.detail}` : ""} · {ago(a.at)}</div>
      </div>
    </li>;
  })}</ol>;
}

export function HomePage() {
  const me = useMe();
  const h = useApi<HomeData>(["home", me.data?.org_id], me.data ? "/home" : null, { refetchInterval: 30_000 });
  const [open, setOpen] = useState(false);
  const d = h.data;
  const first = me.data?.display_name.split(" ")[0];
  return <div className="hero-wash min-h-full">
    <div className="mx-auto max-w-7xl space-y-8 p-8">
      <div className="fade-up flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="eyebrow">{new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}</div>
          <h1 className="serif mt-1 text-5xl leading-none">{greeting()}{first ? <>, <em>{first}</em></> : ""}.</h1>
          <p className="mt-2 max-w-2xl text-muted">What was designed, what the code says and what is running — across every project you can see.</p>
        </div>
        <div className="flex gap-2">
          <Link to="/projects"><Button><Boxes size={16} /> All projects</Button></Link>
          <Button variant="primary" onClick={() => setOpen(true)}><Plus size={16} /> New project</Button>
        </div>
      </div>
      <ErrorBox error={h.error} />
      <section aria-label="Totals" className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {!d ? Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-[104px] !rounded-xl" />) : <>
          <StatTile label="Projects" value={d.totals.projects} icon={<Boxes size={16} />} hint={`${d.totals.connectors} connectors`} />
          <StatTile label="Elements" value={d.totals.elements.toLocaleString()} icon={<Network size={16} />} hint={`${d.totals.relationships.toLocaleString()} relationships`} />
          <StatTile label="Open drift" value={d.totals.drift_open} tone={d.totals.drift_open ? "accent" : "ok"} icon={<AlertTriangle size={16} />} hint="evidence-backed" />
          <StatTile label="Unknown" value={d.totals.unknown} icon={<CircleDashed size={16} />} hint="incomplete evidence, no alert" />
          <StatTile label="Decisions" value={d.totals.adrs} icon={<BookCheck size={16} />} hint="architecture decision records" />
          <StatTile label="Stale sources" value={d.totals.stale_connectors} tone={d.totals.stale_connectors ? "warn" : "ok"} icon={<Radar size={16} />} hint="past freshness SLA" />
        </>}
      </section>
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2" eyebrow="For you" title={<span className="flex items-center gap-2">Needs attention {d && d.attention.length > 0 && <Badge tone="accent">{d.attention.length}</Badge>}</span>}>
          {!d ? <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-10" />)}</div> : <AttentionList items={d.attention} />}
        </Card>
        <Card eyebrow="Across projects" title="Recent activity">
          {!d ? <div className="space-y-3">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-8" />)}</div> : <div className="max-h-[420px] overflow-auto pr-1"><Activity items={d.activity.slice(0, 14)} /></div>}
        </Card>
      </div>
      <section aria-labelledby="h-projects" className="space-y-3">
        <div className="flex items-end justify-between"><div><div className="eyebrow">Health</div><h2 id="h-projects" className="serif text-3xl">Your projects</h2></div>
          <Link to="/projects" className="text-sm text-link hover:underline">View all ›</Link></div>
        {d && d.projects.length === 0 && <Empty title="No projects yet">Create one, connect a repository or runtime, and ArchTwin builds the architecture from evidence.</Empty>}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {!d ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-48 !rounded-xl" />) : d.projects.slice(0, 9).map((p) => <ProjectHealthCard key={p.id} p={p} />)}
        </div>
      </section>
    </div>
    <NewProjectDialog open={open} onClose={() => setOpen(false)} />
  </div>;
}
