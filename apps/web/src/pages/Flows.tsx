import { Database, GitFork, Globe, Network, Radio, Search, Workflow } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Badge, Card, Empty, ErrorBox, Input, OriginBadges, Skeleton, Table, cn } from "@/components/ui";
import { useApi } from "@/lib/hooks";

interface Step { from: string; to: string; kind: string; edge: string; label: string; protocol: string; origins: string[]; confidence: number;
  inferred_only: boolean; documented: boolean; evidence: number }
interface Participant { key: string; name: string; kind: string; subtype: string; system: string; technology: string }
interface Flow { id: string; kind: "request" | "endpoint" | "event" | "data"; name: string; entry: string | null; steps: Step[]; participants: Participant[];
  systems: string[]; distributed: boolean; confidence: number; inferred: boolean; documented: boolean; length: number }

const KIND: Record<Flow["kind"], { label: string; icon: typeof Network }> = { request: { label: "Request", icon: Network },
  endpoint: { label: "Endpoint", icon: Globe }, event: { label: "Event", icon: Radio }, data: { label: "Data", icon: Database } };
const kindOf = (k: string) => KIND[k as Flow["kind"]] ?? { label: k, icon: Workflow };      // unknown kinds never crash the page

/** Sequence diagram in real pixels: lifelines per participant (grouped by system), numbered arrows top-down. */
function Sequence({ flow, active, onStep }: { flow: Flow; active: number | null; onStep: (i: number) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(900);
  useEffect(() => {
    if (!box.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(480, Math.floor(e.contentRect.width))));
    ro.observe(box.current);
    return () => ro.disconnect();
  }, []);
  const ps = flow.participants;
  const col = Math.max(120, (w - 40) / Math.max(1, ps.length));
  const W = Math.max(w, col * ps.length + 40);
  const top = 64, row = 40, H = top + flow.steps.length * row + 30;
  const x = (k: string) => 20 + ps.findIndex((p) => p.key === k) * col + col / 2;
  const sysColor = useMemo(() => {
    const systems = [...new Set(ps.map((p) => p.system).filter(Boolean))];
    return Object.fromEntries(systems.map((s, i) => [s, `var(--series-${(i % 6) + 1})`]));
  }, [ps]);
  return <div ref={box} className="overflow-x-auto">
    <svg width={W} height={H} role="img" aria-label={`Sequence diagram: ${flow.name}`} className="block">
      <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--color-muted)" /></marker>
        <marker id="arr-on" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--color-accent)" /></marker></defs>
      {ps.map((p) => { const cx = x(p.key); return <g key={p.key}>
        <rect x={cx - col / 2 + 6} y={8} width={col - 12} height={40} rx={6} fill="var(--color-card)" stroke={p.system ? sysColor[p.system] : "var(--color-rule)"} strokeWidth={1.5} />
        <text x={cx} y={25} textAnchor="middle" fontSize={11.5} fontWeight={600} fill="var(--color-ink)">{p.name.length > 22 ? p.name.slice(0, 21) + "…" : p.name}</text>
        <text x={cx} y={40} textAnchor="middle" fontSize={9} fill="var(--color-soft)">{(p.kind === "kafka-topic" ? "topic" : p.subtype || p.kind)}{p.system ? ` · ${p.system}` : ""}</text>
        <line x1={cx} x2={cx} y1={48} y2={H - 10} stroke="var(--color-rule)" strokeDasharray="3 4" /></g>; })}
      {flow.steps.map((s, i) => {
        const x1 = x(s.from), x2 = x(s.to), y = top + i * row + 14;
        const on = active === i;
        const dashed = s.inferred_only || s.documented || s.confidence < 0.6;
        const self = x1 === x2;
        return <g key={i} onClick={() => onStep(i)} className="cursor-pointer" role="button" aria-label={`Step ${i + 1}: ${s.kind} ${s.label}`} tabIndex={0}
          onKeyDown={(e) => e.key === "Enter" && onStep(i)}>
          <rect x={Math.min(x1, x2) - 8} y={y - 16} width={Math.abs(x2 - x1) + 16 || 60} height={row - 6} fill="transparent" />
          {self ? <path d={`M${x1},${y} h28 v12 h-28`} fill="none" stroke={on ? "var(--color-accent)" : "var(--color-muted)"} strokeWidth={on ? 2 : 1.25} markerEnd={`url(#${on ? "arr-on" : "arr"})`} />
            : <line x1={x1} x2={x2 + (x2 > x1 ? -2 : 2)} y1={y} y2={y} stroke={on ? "var(--color-accent)" : "var(--color-muted)"} strokeWidth={on ? 2 : 1.25}
              strokeDasharray={dashed ? "5 4" : undefined} markerEnd={`url(#${on ? "arr-on" : "arr"})`} />}
          <circle cx={x1 + (x2 >= x1 ? 10 : -10)} cy={y - 9} r={7} fill={on ? "var(--color-accent)" : "var(--color-paper-2)"} />
          <text x={x1 + (x2 >= x1 ? 10 : -10)} y={y - 6} textAnchor="middle" fontSize={8.5} fontWeight={600} fill={on ? "#fff" : "var(--color-ink)"}>{i + 1}</text>
          <text x={(x1 + x2) / 2 + (self ? 50 : 0)} y={y - 5} textAnchor="middle" fontSize={10} fill="var(--color-muted)">{s.kind}{s.label && s.label !== s.kind ? ` · ${s.label}` : ""}</text>
        </g>;
      })}
    </svg>
    {flow.systems.length > 1 && <ul className="mt-1 flex flex-wrap gap-3 text-xs text-muted" aria-label="Systems">{flow.systems.map((s) =>
      <li key={s} className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: sysColor[s] }} />{s}</li>)}</ul>}
  </div>;
}

export function FlowsPage({ projectId }: { projectId: string }) {
  const f = useApi<{ flows: Flow[]; total: number; counts: Record<string, number> }>(["flows", projectId], `/projects/${projectId}/flows`);
  const [kind, setKind] = useState<string>("");
  const [q, setQ] = useState("");
  const [onlyDist, setOnlyDist] = useState(false);
  const [sel, setSel] = useState<string | null>(null);
  const [step, setStep] = useState<number | null>(null);
  const flows = (f.data?.flows ?? []).filter((x) => (!kind || x.kind === kind) && (!onlyDist || x.distributed)
    && (!q || `${x.name} ${x.participants.map((p) => p.name).join(" ")}`.toLowerCase().includes(q.toLowerCase())));
  const cur = flows.find((x) => x.id === sel) ?? flows[0];
  useEffect(() => setStep(null), [cur?.id]);
  if (f.error) return <div className="p-6"><ErrorBox error={f.error} /></div>;
  return <div className="grid h-full gap-4 p-6 xl:grid-cols-[340px_minmax(0,1fr)]">
    <Card eyebrow={f.data ? `${f.data.total} recognized automatically` : "Recognizing…"} title={<span className="flex items-center gap-2"><Workflow size={16} /> Flows</span>}>
      <div className="relative mb-2"><Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-soft" />
        <Input aria-label="Search flows" placeholder="Search flows or participants" className="!pl-7" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      <div role="radiogroup" aria-label="Flow kind" className="mb-2 flex flex-wrap gap-1">{[["", "All"], ["endpoint", "Endpoint"], ["request", "Request"], ["event", "Event"], ["data", "Data"]].map(([k, l]) =>
        <button key={k} role="radio" aria-checked={kind === k} onClick={() => setKind(k)}
          className={cn("rounded-full border px-2.5 py-0.5 text-xs", kind === k ? "border-ink bg-ink text-paper" : "border-rule hover:border-muted")}>
          {l}{k && f.data ? ` ${f.data.counts[k] ?? 0}` : ""}</button>)}</div>
      <label className="mb-2 flex items-center gap-1.5 text-xs text-muted"><input type="checkbox" checked={onlyDist} onChange={(e) => setOnlyDist(e.target.checked)} /> Only distributed (spanning systems)</label>
      {!f.data ? <Skeleton className="h-64" /> : flows.length === 0 ? <p className="py-6 text-center text-sm text-soft">No flow matches. Flows appear once datasources show calls, topics or data access.</p> :
        <ul className="max-h-[65vh] space-y-1 overflow-auto">{flows.map((x) => { const K = kindOf(x.kind);
          return <li key={x.id}><button onClick={() => setSel(x.id)} className={cn("w-full rounded-lg px-2.5 py-2 text-left", cur?.id === x.id ? "bg-paper-2" : "hover:bg-paper-2")}>
            <span className="flex items-center gap-1.5 text-sm"><K.icon size={13} className="shrink-0 text-soft" /><span className="truncate">{x.name}</span></span>
            <span className="mt-0.5 flex flex-wrap items-center gap-1 text-[11px] text-soft">{x.length} steps · {x.participants.length} participants
              {x.distributed && <Badge tone="link"><GitFork size={9} /> {x.systems.length} systems</Badge>}{x.documented && <Badge tone="muted">documented</Badge>}
              {x.inferred && <Badge tone="warn">inferred</Badge>}</span></button></li>; })}</ul>}
    </Card>
    <div className="min-w-0 space-y-4">
      {!cur ? (f.data ? <Empty title="No flows yet">Add datasources and scan them: request flows come from calls between services, event flows from topics, data flows from database access.</Empty> : <Skeleton className="h-96 !rounded-xl" />) : <>
        <Card eyebrow={`${kindOf(cur.kind).label} flow · confidence ${cur.confidence.toFixed(2)}${cur.distributed ? ` · across ${cur.systems.join(", ")}` : ""}`} title={cur.name}>
          <Sequence flow={cur} active={step} onStep={setStep} />
          <p className="mt-2 text-xs text-soft">Solid = observed in code or runtime; dashed = documented in a diagram, inferred, or low confidence. Click a step for its evidence.</p>
        </Card>
        <Card eyebrow="Steps" title="Evidence per step">
          <Table head={["#", "From", "Relation", "To", "Origins", "Confidence", "Evidence"]}>{cur.steps.map((s, i) => {
            const n = (k: string) => cur.participants.find((p) => p.key === k)?.name ?? k;
            return <tr key={i} onClick={() => setStep(i)} className={cn("cursor-pointer border-b border-rule", step === i && "bg-accent-tint")}>
              <td className="px-2 py-1.5 font-mono text-xs">{i + 1}</td><td className="px-2 text-sm">{n(s.from)}</td>
              <td className="px-2 text-xs">{s.kind}{s.protocol ? ` · ${s.protocol}` : ""}{s.documented && <Badge tone="muted">doc</Badge>}</td><td className="px-2 text-sm">{n(s.to)}</td>
              <td className="px-2"><OriginBadges origins={s.origins} /></td><td className="num px-2">{s.confidence.toFixed(2)}</td><td className="num px-2">{s.evidence}</td></tr>; })}</Table>
          {step !== null && <p className="mt-2 break-all font-mono text-[11px] text-soft">relation key: {cur.steps[step].edge}</p>}
        </Card></>}
    </div>
  </div>;
}
