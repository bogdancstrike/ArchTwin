import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, Handle, Position, type EdgeProps, type NodeProps } from "@xyflow/react";
import { FileText, ListChecks, Database, Globe, Layers, User, ZoomIn } from "lucide-react";
import { createContext, useContext } from "react";
import { cn } from "@/components/ui";
import type { ViewEdge, ViewNode } from "@/lib/types";
import { labelAnchor, NODE_H, NODE_W, roundedPath } from "./layout";

export type NodeData = ViewNode & { diff?: "added" | "changed"; dimmed?: boolean; links?: { adrs: number; work_items: number; documented: number } };

/** Lets a node's zoom icon zoom straight into its detail view (no need to select it and use the side panel). */
export const ZoomContext = createContext<((target: string, nodeId: string) => void) | null>(null);
export type EdgeData = ViewEdge & { route?: { x: number; y: number }[]; diff?: "added" | "changed"; dimmed?: boolean };

const EYEBROW: Record<string, string> = { person: "Person", external: "External system", system: "Software system", group: "Group", component: "Component" };

/** Node treatments from the diagram-design system: paper fill, ink stroke for primary, muted/secondary, accent for focal,
 * dashed for inferred-only or grouped elements. */
export function C4Node({ data, selected }: NodeProps) {
  const n = data as unknown as NodeData;
  const zoom = useContext(ZoomContext);
  const eyebrow = n.element_kind === "code" ? `${n.subtype || "code"}${n.kind === "external" ? " · other component" : ""}`
    : EYEBROW[n.kind] ?? (n.subtype || "container");
  const Icon = n.kind === "person" ? User : n.kind === "external" ? Globe : n.subtype === "database" ? Database : n.kind === "group" ? Layers : null;
  return <div style={{ width: NODE_W, height: NODE_H }}
    className={cn("group relative rounded-md border px-3 py-2 text-left transition-shadow",
      n.focal ? "border-accent bg-accent-tint ring-1 ring-accent" : n.primary ? "border-ink bg-card" : "border-muted/60 bg-paper-2",
      (n.inferred_only || n.kind === "group") && "border-dashed", selected && "shadow-[0_0_0_3px_var(--color-link)]",
      n.diff === "added" && "!border-ok !bg-ok/10", n.diff === "changed" && "!border-warn !bg-warn/10", n.dimmed && "opacity-30")}
    title={`${n.name}${n.description ? " — " + n.description : ""}`}>
    <Handle type="target" position={Position.Left} className="!h-1 !w-1 !border-0 !bg-transparent" />
    <Handle type="source" position={Position.Right} className="!h-1 !w-1 !border-0 !bg-transparent" />
    <div className="flex items-center justify-between font-mono text-[8px] uppercase tracking-[0.16em] text-soft">
      <span className="flex items-center gap-1">{Icon && <Icon size={10} />}{eyebrow}</span>
      <span className="flex items-center gap-1">{n.state && n.state !== "running" && <span className={n.state === "completed" ? "text-ok" : "text-bad"}>{n.state === "completed" ? "✓ completed" : n.state}</span>}
        {n.zoom && <button type="button" aria-label={`Zoom into ${n.name}`} title="Zoom in"
          className="nodrag nopan -m-1 rounded p-1 text-link hover:bg-link/10 focus:outline-none focus-visible:ring-1 focus-visible:ring-link"
          onClick={(e) => { e.stopPropagation(); zoom?.(n.zoom!, n.id); }} onDoubleClick={(e) => e.stopPropagation()}><ZoomIn size={12} /></button>}</span>
    </div>
    <div className="mt-0.5 truncate text-[12.5px] font-semibold text-ink">{n.name}</div>
    <div className="truncate font-mono text-[9px] text-muted">{n.technology || n.description}</div>
    {n.links && (n.links.adrs + n.links.work_items + n.links.documented) > 0 && <div className="absolute -bottom-2 left-2 flex gap-1 font-mono text-[8px]">
      {n.links.adrs > 0 && <span title={`${n.links.adrs} ADR(s) mention this`} className="flex items-center gap-0.5 rounded bg-card px-1 text-muted ring-1 ring-rule"><FileText size={8} />{n.links.adrs}</span>}
      {n.links.work_items > 0 && <span title={`${n.links.work_items} work item(s) mention this`} className="flex items-center gap-0.5 rounded bg-card px-1 text-muted ring-1 ring-rule"><ListChecks size={8} />{n.links.work_items}</span>}
      {n.links.documented > 0 && <span title={`${n.links.documented} relation(s) drawn in documentation diagrams`} className="rounded bg-card px-1 text-muted ring-1 ring-rule">doc {n.links.documented}</span>}
    </div>}
    {n.focal && <span className="absolute -top-2 right-2 rounded bg-accent px-1 font-mono text-[8px] uppercase text-white">{n.focal_reason === "drift" ? "drift" : "focal"}</span>}
  </div>;
}

export function C4Edge(p: EdgeProps) {
  const e = p.data as unknown as EdgeData;
  const moved = !e.route;
  const path = moved ? getSmoothStepPath({ sourceX: p.sourceX, sourceY: p.sourceY, targetX: p.targetX, targetY: p.targetY,
    sourcePosition: p.sourcePosition, targetPosition: p.targetPosition, borderRadius: 6 })[0] : roundedPath(e.route!);
  const anchor = moved ? { x: (p.sourceX + p.targetX) / 2, y: (p.sourceY + p.targetY) / 2 } : labelAnchor(e.route!);
  const color = e.focal ? "var(--color-accent)" : e.diff === "added" ? "var(--color-ok)" : e.diff === "changed" ? "var(--color-warn)"
    : e.kind === "calls" ? "var(--color-link)" : "var(--color-muted)";
  const dashed = e.kind === "depends-on" || e.inferred_only || e.confidence < 0.6;
  return <>
    <BaseEdge id={p.id} path={path} markerEnd={p.markerEnd} interactionWidth={14}
      style={{ stroke: color, strokeWidth: e.focal || p.selected ? 2 : 1.25, strokeDasharray: dashed ? "5 4" : undefined, opacity: e.dimmed ? 0.2 : 1 }} />
    <EdgeLabelRenderer>
      <div style={{ transform: `translate(-50%,-50%) translate(${anchor.x}px,${anchor.y}px)`, opacity: e.dimmed ? 0.2 : 1 }}
        className="nodrag nopan pointer-events-auto absolute rounded-sm bg-paper px-[7px] font-mono text-[8.5px] leading-[14px] tracking-wide text-muted">
        {e.label}{e.count > 1 && <span className="text-soft"> ×{e.count}</span>}
      </div>
    </EdgeLabelRenderer>
  </>;
}
