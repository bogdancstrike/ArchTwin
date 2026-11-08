import { Link } from "@tanstack/react-router";
import { Badge, Card, FreshnessBadge, Spinner, ago } from "@/components/ui";
import { useApi } from "@/lib/hooks";

export function OverviewPage({ projectId }: { projectId: string }) {
  const h = useApi<any>(["home", projectId], `/projects/${projectId}/home`, { refetchInterval: 10_000 });
  if (h.isLoading || !h.data) return <Spinner />;
  const d = h.data;
  const off = (c: any) => !c.configured && <p className="text-sm text-soft">{c.reason ?? "Not configured yet."}</p>;
  return <div className="grid gap-4 p-6 lg:grid-cols-2">
    <Card eyebrow="Evidence" title="Freshness" actions={<Link className="text-sm text-link" to="/projects/$projectId/inventory" params={{ projectId }}>Inventory ›</Link>}>
      {!d.freshness.configured ? <p className="text-sm text-soft">No connectors yet — add one in Inventory. Until then everything is <b>UNKNOWN</b>, never "absent".</p>
        : <ul className="space-y-2">{d.freshness.connectors.map((c: any) => <li key={c.id} className="flex items-center justify-between text-sm"><span><b>{c.name}</b> <span className="text-soft">({c.kind})</span></span><FreshnessBadge f={c.freshness} /></li>)}</ul>}
    </Card>
    <Card eyebrow="Architecture" title="Latest snapshot" actions={<Link className="text-sm text-link" to="/projects/$projectId/architecture" params={{ projectId }}>Diagrams ›</Link>}>
      {off(d.architecture) || (d.architecture.snapshot && <div className="text-sm"><div className="serif text-4xl">v{d.architecture.snapshot.version}</div>
        <p className="text-muted">{d.architecture.snapshot.node_count} elements · {d.architecture.snapshot.edge_count} relationships · {ago(d.architecture.snapshot.created_at)}</p>
        <p className="mt-1 font-mono text-xs text-soft">manifest {d.architecture.snapshot.manifest_hash.slice(0, 16)}</p></div>)}
    </Card>
    <Card eyebrow="Drift" title="Open findings" actions={<Link className="text-sm text-link" to="/projects/$projectId/drift" params={{ projectId }}>Triage ›</Link>}>
      {off(d.drift) || <div className="flex items-end gap-6"><div><div className="serif text-4xl text-accent">{d.drift.open}</div><div className="text-xs text-muted">drift (evidence-backed)</div></div>
        <div><div className="serif text-4xl text-soft">{d.drift.unknown}</div><div className="text-xs text-muted">unknown / incomplete (no alert)</div></div></div>}
    </Card>
    <Card eyebrow="Decisions" title="ADRs" actions={<Link className="text-sm text-link" to="/projects/$projectId/decisions" params={{ projectId }}>Decisions ›</Link>}>
      {off(d.decisions) || <div className="serif text-4xl">{d.decisions.adrs}</div>}
      <div className="mt-2">{d.assistant.configured ? <Badge tone="ok">assistant enabled</Badge> : <Badge>assistant off</Badge>}</div>
    </Card>
  </div>;
}
