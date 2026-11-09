import { ChevronRight, Database, GitFork, Globe, Network, Radio, Workflow, X } from "lucide-react";
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { Badge, Button, Card, Empty, OriginBadges, Table, cn } from "@/components/ui";
import { DataTable } from "@/components/DataTable";
import { ElementDetail, EvidenceList } from "@/components/ElementInspector";
import { SplitLayout } from "@/components/SplitLayout";
import { PageAsk } from "@/components/PageAsk";
import { StepCode } from "@/components/StepCode";
import { api } from "@/lib/api";
import { takeParam } from "@/lib/deeplink";

interface Step { from: string; to: string; kind: string; edge: string; label: string; protocol: string; origins: string[]; confidence: number;
  inferred_only: boolean; documented: boolean; evidence: number }
interface Participant { key: string; name: string; kind: string; subtype: string; system: string; technology: string }
interface Flow { id: string; kind: "request" | "endpoint" | "event" | "data"; name: string; entry: string | null; steps: Step[]; participants: Participant[];
  systems: string[]; distributed: boolean; confidence: number; inferred: boolean; documented: boolean; length: number }

const KIND: Record<Flow["kind"], { label: string; icon: typeof Network }> = { request: { label: "Request", icon: Network },
  endpoint: { label: "Endpoint", icon: Globe }, event: { label: "Event", icon: Radio }, data: { label: "Data", icon: Database } };
const kindOf = (k: string) => KIND[k as Flow["kind"]] ?? { label: k, icon: Workflow };      // unknown kinds never crash the page

/** Sequence diagram in real pixels: lifelines per participant (grouped by system), numbered arrows top-down. */
function Sequence({ flow, active, onStep, onParticipant, selected }: { flow: Flow; active: number | null; onStep: (i: number) => void;
  onParticipant: (p: Participant) => void; selected?: string | null }) {
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
      {ps.map((p) => { const cx = x(p.key); return <g key={p.key} role="button" tabIndex={0} aria-label={`Inspect ${p.name}`} className="cursor-pointer"
        onClick={() => onParticipant(p)} onKeyDown={(e) => e.key === "Enter" && onParticipant(p)}>
        <rect x={cx - col / 2 + 6} y={8} width={col - 12} height={40} rx={6} fill={selected === p.key ? "var(--color-accent-tint)" : "var(--color-card)"}
          stroke={selected === p.key ? "var(--color-accent)" : p.system ? sysColor[p.system] : "var(--color-rule)"} strokeWidth={selected === p.key ? 2 : 1.5} />
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
  const [cur, setCur] = useState<Flow | null>(null);
  useEffect(() => {                      // ?flow=<id>&q=<name> (command palette): open that flow
    const id = takeParam("flow"), name = takeParam("q");
    if (!id) return;
    void api<{ items: Flow[] }>(`/projects/${projectId}/flows?page=1&page_size=25&q=${encodeURIComponent(name ?? "")}`)
      .then((r) => { const f = r.items.find((x) => x.id === id); if (f) setCur(f); }).catch(() => undefined);
  }, [projectId]);
  const [step, setStep] = useState<number | null>(null);
  const [inspect, setInspect] = useState<{ kind: "element" | "relation"; key: string; title: string } | null>(null);
  useEffect(() => { setStep(null); setInspect(null); }, [cur?.id]);
  const name = (k: string) => cur?.participants.find((pp) => pp.key === k)?.name ?? k;
  const pickStep = (i: number) => { if (i < 0) { setStep(null); return; } setStep(i); const st = cur!.steps[i];
    setInspect({ kind: "relation", key: st.edge, title: `${name(st.from)} ${st.kind} ${name(st.to)}` }); };
  return <SplitLayout storageKey="flows" title="Flows" sideWidth="xl:w-[440px]" side={(toggle) => <div className="space-y-4">
    <PageAsk projectId={projectId} page="flows" selected={cur?.id ?? null} onPick={(m) => m.flow && setCur(m.flow as Flow)} />
    <Card eyebrow="Recognized automatically" title={<span className="flex items-center gap-2"><Workflow size={16} /> Flows</span>} actions={toggle}>
      <DataTable<Flow> queryKey={["flows", projectId]} endpoint={`/projects/${projectId}/flows`} rowKey={(x) => x.id} selected={cur?.id ?? null}
        onRowClick={setCur} searchPlaceholder="Search flows or participants" defaultSort="" defaultDir="desc"
        empty="No flows yet. Add datasources and scan them: flows come from endpoints, calls between services, topics and data access."
        filters={[{ key: "kind", label: "Kind", options: [["endpoint", "Endpoint"], ["request", "Request"], ["event", "Event"], ["data", "Data"]] },
          { key: "distributed", label: "Distributed", options: [["true", "Across systems"]] }]}
        columns={[{ key: "name", label: "Flow", sortable: true, render: (x) => { const K = kindOf(x.kind);
            return <><span className="flex items-center gap-1.5"><K.icon size={13} className="shrink-0 text-soft" /><span className="truncate">{x.name}</span></span>
              <span className="mt-0.5 flex flex-wrap gap-1">{x.distributed && <Badge tone="link"><GitFork size={9} /> {x.systems.length} systems</Badge>}
                {x.documented && <Badge tone="muted">documented</Badge>}{x.inferred && <Badge tone="warn">inferred</Badge>}</span></>; } },
          { key: "length", label: "Steps", sortable: true, render: (x) => <span className="num">{x.length}</span> },
          { key: "participants", label: "Participants", sortable: true, render: (x) => <span className="num">{x.participants.length}</span> }]} />
    </Card>
  </div>}>
      {!cur ? <Empty title="Select a flow">Pick a flow to see it as a diagram with the evidence for every step.</Empty> : <>
        <Card eyebrow={`${kindOf(cur.kind).label} flow · confidence ${cur.confidence.toFixed(2)}${cur.distributed ? ` · across ${cur.systems.join(", ")}` : ""}`} title={cur.name}>
          <Sequence flow={cur} active={step} onStep={pickStep} selected={inspect?.kind === "element" ? inspect.key : null}
            onParticipant={(pp) => { setStep(null); setInspect({ kind: "element", key: pp.key, title: pp.name }); }} />
          <p className="mt-2 text-xs text-soft">Solid = observed in code or runtime; dashed = documented in a diagram, inferred, or low confidence.
            Click a participant to inspect it (source, references) or a step for its evidence.</p>
        </Card>
        {inspect && <Card eyebrow={inspect.kind === "element" ? "Participant" : "Step"} title={inspect.title}
          actions={<Button size="sm" variant="ghost" aria-label="Close inspector" onClick={() => setInspect(null)}><X size={14} /></Button>}>
          {inspect.kind === "element" ? <div className="space-y-3"><ElementDetail projectId={projectId} elementKey={inspect.key} />
            <EvidenceList projectId={projectId} elementKey={inspect.key} /></div>
            : <div className="space-y-3"><EvidenceList projectId={projectId} elementKey={inspect.key} />
              <p className="text-xs text-soft">Steps marked “uses” or “handles” come from the endpoint's route module (its imports); inspect the participants for their source.</p></div>}
        </Card>}
        <Card eyebrow="Steps" title="Evidence per step">
          <p className="mb-2 text-xs text-soft">Click a step to follow the code: the call site, or the handler/component source for steps derived from imports.</p>
          <Table head={["#", "From", "Relation", "To", "Origins", "Confidence", "Evidence"]}>{cur.steps.map((st, i) => {
            const n = name;
            return <Fragment key={i}><tr onClick={() => pickStep(step === i ? -1 : i)} aria-expanded={step === i}
              className={cn("cursor-pointer border-b border-rule", step === i && "bg-accent-tint")}>
              <td className="px-2 py-1.5 font-mono text-xs"><ChevronRight size={11} className={cn("mr-0.5 inline transition", step === i && "rotate-90")} />{i + 1}</td><td className="px-2 text-sm">{n(st.from)}</td>
              <td className="px-2 text-xs">{st.kind}{st.protocol ? ` · ${st.protocol}` : ""}{st.label && st.label !== st.kind ? <div className="truncate font-mono text-[10px] text-soft" title={st.label}>{st.label}</div> : null}
                {st.documented && <Badge tone="muted">doc</Badge>}</td><td className="px-2 text-sm">{n(st.to)}</td>
              <td className="px-2"><OriginBadges origins={st.origins} /></td><td className="num px-2">{st.confidence.toFixed(2)}</td><td className="num px-2">{st.evidence}</td></tr>
              {step === i && <tr className="border-b border-rule"><td colSpan={7} className="bg-paper/60 px-2 py-2"><StepCode projectId={projectId} step={st} /></td></tr>}
            </Fragment>; })}</Table>
          {step !== null && <p className="mt-2 break-all font-mono text-[11px] text-soft">relation key: {cur.steps[step].edge}</p>}
        </Card></>}
  </SplitLayout>;
}
