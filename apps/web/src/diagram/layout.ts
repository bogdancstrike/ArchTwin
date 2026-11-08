import ELK, { type ElkNode } from "elkjs/lib/elk-api";
import workerUrl from "elkjs/lib/elk-worker.min.js?url";
import type { View } from "@/lib/types";

/** ELK layered layout with orthogonal routing, run in a Web Worker (task 2.1 / 2.10). */
const elk = new ELK({ workerUrl });
export const NODE_W = 184;
export const NODE_H = 68;

export interface Laid { pos: Record<string, { x: number; y: number }>; routes: Record<string, { x: number; y: number }[]> }

export async function layoutView(v: View): Promise<Laid> {
  const graph: ElkNode = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered", "elk.direction": "RIGHT", "elk.edgeRouting": "ORTHOGONAL",
      "elk.layered.spacing.nodeNodeBetweenLayers": "110", "elk.spacing.nodeNode": "46", "elk.spacing.edgeEdge": "14",
      "elk.spacing.edgeNode": "22", "elk.layered.spacing.edgeNodeBetweenLayers": "26", "elk.portConstraints": "FREE",
      "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF", "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
      "elk.layered.mergeEdges": "false", "elk.edgeLabels.inline": "true",
    },
    children: v.nodes.map((n) => ({ id: n.id, width: NODE_W, height: NODE_H })),
    edges: v.edges.map((e) => ({ id: e.id, sources: [e.source], targets: [e.target],
      labels: [{ text: e.label, width: e.label.length * 5.2 + 14, height: 14 }] })),
  };
  const out = await elk.layout(graph);
  const pos: Laid["pos"] = {};
  for (const c of out.children ?? []) pos[c.id] = { x: c.x ?? 0, y: c.y ?? 0 };
  const routes: Laid["routes"] = {};
  for (const e of out.edges ?? []) {
    const s = e.sections?.[0];
    if (s) routes[e.id] = [s.startPoint, ...(s.bendPoints ?? []), s.endPoint];
  }
  return { pos, routes };
}

/** SVG path through orthogonal points with rounded bends (radius 6, design-system rule 1). */
export function roundedPath(pts: { x: number; y: number }[], r = 6): string {
  if (pts.length < 2) return "";
  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const p0 = pts[i - 1], p1 = pts[i], p2 = pts[i + 1];
    const r1 = Math.min(r, Math.hypot(p1.x - p0.x, p1.y - p0.y) / 2, Math.hypot(p2.x - p1.x, p2.y - p1.y) / 2);
    const ax = p1.x - Math.sign(p1.x - p0.x) * r1, ay = p1.y - Math.sign(p1.y - p0.y) * r1;
    const bx = p1.x + Math.sign(p2.x - p1.x) * r1, by = p1.y + Math.sign(p2.y - p1.y) * r1;
    d += ` L ${ax} ${ay} Q ${p1.x} ${p1.y} ${bx} ${by}`;
  }
  const last = pts[pts.length - 1];
  return d + ` L ${last.x} ${last.y}`;
}

/** Midpoint of the longest segment (label anchor). */
export function labelAnchor(pts: { x: number; y: number }[]) {
  let best = { x: pts[0].x, y: pts[0].y }, len = -1;
  for (let i = 0; i < pts.length - 1; i++) {
    const l = Math.hypot(pts[i + 1].x - pts[i].x, pts[i + 1].y - pts[i].y);
    if (l > len) { len = l; best = { x: (pts[i].x + pts[i + 1].x) / 2, y: (pts[i].y + pts[i + 1].y) / 2 }; }
  }
  return best;
}
