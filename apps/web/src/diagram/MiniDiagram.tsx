import { useNavigate } from "@tanstack/react-router";
import { Background, Controls, MarkerType, ReactFlow, ReactFlowProvider, useReactFlow, type Edge, type Node } from "@xyflow/react";
import { ExternalLink, Maximize2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, Dialog } from "@/components/ui";
import type { View } from "@/lib/types";
import { C4Edge, C4Node, ZoomContext, type EdgeData, type NodeData } from "./elements";
import { NODE_H, NODE_W, layoutView } from "./layout";

const nodeTypes = { c4: C4Node };
const edgeTypes = { c4: C4Edge };

function Canvas({ view, projectId, height }: { view: View; projectId: string; height: number }) {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const rf = useReactFlow();
  const nav = useNavigate();
  useEffect(() => {
    let alive = true;
    void layoutView(view).then((laid) => {
      if (!alive) return;
      setNodes(view.nodes.map((n) => ({ id: n.id, type: "c4", position: laid.pos[n.id] ?? { x: 0, y: 0 }, data: n as unknown as NodeData as never, width: NODE_W, height: NODE_H })));
      setEdges(view.edges.map((e) => ({ id: e.id, source: e.source, target: e.target, type: "c4", data: { ...e, route: laid.routes[e.id] } as EdgeData as never,
        markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: e.kind === "calls" ? "#2e5aa8" : "#4f5d75" } })));
      requestAnimationFrame(() => rf.fitView({ padding: 0.15 }));
    });
    return () => { alive = false; };
  }, [view, rf]);
  const open = (target: string) => void nav({ to: "/projects/$projectId/architecture", params: { projectId }, search: { view: target } as never });
  return <ZoomContext.Provider value={(target) => open(target)}>
    <div style={{ height }} className="overflow-hidden rounded-lg border border-rule bg-paper/60">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} minZoom={0.2} maxZoom={2.5} fitView nodesConnectable={false}
        proOptions={{ hideAttribution: true }} zoomOnDoubleClick={false}
        onNodeDoubleClick={(_, n) => { const d = n.data as unknown as NodeData & { parent_view?: string }; open(d.zoom ?? d.parent_view ?? "context"); }}>
        <Background gap={18} size={1} color="var(--color-rule)" /><Controls showInteractive={false} position="bottom-right" />
      </ReactFlow>
    </div>
  </ZoomContext.Provider>;
}

/** An answer's architecture diagram: pan/zoom inline, expand to a large dialog, or jump to the Architecture tab. */
export function MiniDiagram({ view, projectId }: { view: View; projectId: string }) {
  const [big, setBig] = useState(false);
  const nav = useNavigate();
  const first = view.nodes.find((n) => (n as unknown as { parent_view?: string }).parent_view) as unknown as { parent_view?: string } | undefined;
  return <div className="mt-3">
    <div className="mb-1 flex items-center gap-2 text-[11px] text-soft"><span className="eyebrow">Diagram</span><span>{view.nodes.length} elements · double-click or ⊕ to zoom into a C4 level</span>
      <span className="ml-auto flex gap-1">
        <Button size="sm" variant="ghost" onClick={() => setBig(true)} aria-label="Expand diagram"><Maximize2 size={12} /> Expand</Button>
        {first?.parent_view && <Button size="sm" variant="ghost" onClick={() => void nav({ to: "/projects/$projectId/architecture", params: { projectId }, search: { view: first.parent_view } as never })}>
          <ExternalLink size={12} /> Open in Architecture</Button>}</span></div>
    <ReactFlowProvider><Canvas view={view} projectId={projectId} height={300} /></ReactFlowProvider>
    <Dialog open={big} onClose={() => setBig(false)} title="Diagram for this answer" wide>
      <ReactFlowProvider><Canvas view={view} projectId={projectId} height={560} /></ReactFlowProvider>
    </Dialog>
  </div>;
}
