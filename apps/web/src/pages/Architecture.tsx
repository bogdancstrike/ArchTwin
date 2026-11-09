import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { Background, Controls, MarkerType, MiniMap, ReactFlow, ReactFlowProvider, useReactFlow, type Edge, type Node, type NodeMouseHandler } from "@xyflow/react";
import { ChevronRight, GitCompare, RotateCcw, Table2, Workflow } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Badge, Button, Card, cn, Empty, ErrorBox, OriginBadges, Select, Spinner, Table } from "@/components/ui";
import { api, download } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { Evidence, Snapshot, View } from "@/lib/types";
import { C4Edge, C4Node, ZoomContext, type EdgeData, type NodeData } from "@/diagram/elements";
import { layoutView, NODE_H, NODE_W } from "@/diagram/layout";

const nodeTypes = { c4: C4Node };
const edgeTypes = { c4: C4Edge };
const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

interface Search { view?: string; snapshot?: string; compare?: string; full?: boolean; deps?: boolean; table?: boolean }

function viewPath(projectId: string, key: string, s: Search) {
  const q = new URLSearchParams();
  if (s.snapshot) q.set("snapshot_id", s.snapshot);
  if (s.full) q.set("full", "true");
  if (s.deps) q.set("deps", "true");
  return `/projects/${projectId}/views/${key}${q.toString() ? "?" + q : ""}`;
}

function EvidencePanel({ projectId, sel, onClose, onZoom }: { projectId: string; sel: { kind: "node" | "edge"; data: NodeData | EdgeData } | null; onClose: () => void; onZoom: (k: string) => void }) {
  const key = !sel ? null : sel.kind === "node" ? ((sel.data as NodeData).kind === "group" ? null : sel.data.id) : (sel.data as EdgeData).members[0];
  const obs = useApi<{ id: string; origin: string; source_ref: string; source_revision: string; observed_at: string; parser_version: string; confidence: string; evidence: Evidence["span"]; attributes: Record<string, unknown> }[]>(
    ["obs", projectId, key], key ? `/projects/${projectId}/observations?key=${encodeURIComponent(key)}` : null);
  if (!sel) return null;
  const d = sel.data;
  return <aside aria-label="Evidence" className="absolute right-3 top-3 bottom-3 z-10 w-96 overflow-auto rounded-lg border border-rule bg-card shadow-lg">
    <header className="flex items-start justify-between border-b border-rule p-3">
      <div><div className="eyebrow">{sel.kind === "node" ? (d as NodeData).kind : `${(d as EdgeData).kind} relationship`}</div>
        <h3 className="font-semibold">{sel.kind === "node" ? (d as NodeData).name : (d as EdgeData).label}</h3>
        <div className="mt-1 break-all font-mono text-[10px] text-soft">{sel.kind === "node" ? d.id : (d as EdgeData).members.join(", ")}</div></div>
      <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close evidence">✕</Button>
    </header>
    <div className="space-y-3 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2"><OriginBadges origins={d.origins} /><Badge tone={d.confidence >= 0.8 ? "ok" : d.confidence >= 0.6 ? "warn" : "bad"}>confidence {Number(d.confidence).toFixed(2)}</Badge>
        {d.inferred_only && <Badge tone="warn">inferred — not established</Badge>}</div>
      {sel.kind === "node" && (d as NodeData).zoom && <Button size="sm" onClick={() => onZoom((d as NodeData).zoom!)}>Zoom in ›</Button>}
      {sel.kind === "node" && (d as NodeData).kind === "group" && <div><div className="eyebrow mb-1">Members</div>
        <ul className="list-disc pl-5 text-xs">{(d as NodeData).member_keys?.map((m) => <li key={m} className="font-mono">{m}</li>)}</ul></div>}
      {key && <div><div className="eyebrow mb-1">Evidence ({obs.data?.length ?? "…"} observations)</div>
        {obs.isLoading && <Spinner />}
        <ul className="space-y-2">{obs.data?.slice(0, 12).map((o) => <li key={o.id} className="rounded border border-rule p-2 text-xs">
          <div className="flex justify-between"><OriginBadges origins={[o.origin]} /><span className="text-soft">{new Date(o.observed_at).toLocaleString()}</span></div>
          <div className="mt-1 break-all font-mono">{o.source_ref || "—"}{o.evidence?.line_start ? `:${o.evidence.line_start}${o.evidence.line_end && o.evidence.line_end !== o.evidence.line_start ? "-" + o.evidence.line_end : ""}` : ""}</div>
          <div className="mt-1 text-soft">rev <span className="font-mono">{(o.source_revision || "live").slice(0, 12)}</span> · {o.parser_version} · conf {Number(o.confidence).toFixed(2)}</div>
        </li>)}</ul></div>}
    </div>
  </aside>;
}

function Canvas({ projectId }: { projectId: string }) {
  const search = useSearch({ strict: false }) as Search;
  const nav = useNavigate();
  const qc = useQueryClient();
  const rf = useReactFlow();
  const viewKey = search.view ?? "context";
  const setSearch = useCallback((patch: Partial<Search>) => nav({ to: ".", search: (s: Search) => ({ ...s, ...patch }) as never, replace: false }), [nav]);
  const q = useQuery({ queryKey: ["view", projectId, viewKey, search.snapshot, search.full, search.deps], queryFn: () => api<View>(viewPath(projectId, viewKey, search)), retry: false });
  const snaps = useApi<Snapshot[]>(["snapshots", projectId], `/projects/${projectId}/snapshots`);
  const diff = useApi<any>(["diff", projectId, search.compare, q.data?.snapshot.id], search.compare && q.data ? `/projects/${projectId}/diff?from=${search.compare}&to=${q.data.snapshot.id}` : null);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [sel, setSel] = useState<{ kind: "node" | "edge"; data: NodeData | EdgeData } | null>(null);
  const [lint, setLint] = useState<{ ok: boolean; violations: { rule: string; detail: string }[] } | null>(null);
  const zooming = useRef(false);
  const moved = useRef<Record<string, { x: number; y: number }>>({});

  useEffect(() => {
    const v = q.data;
    if (!v) return;
    let cancelled = false;
    (async () => {
      const laid = await layoutView(v);
      if (cancelled) return;
      const ov = v.layout.overrides ?? {};
      moved.current = {};
      const added = new Set<string>(diff.data ? [...diff.data.nodes.added] : []);
      const changed = new Set<string>(diff.data ? diff.data.nodes.changed.map((c: { key: string }) => c.key) : []);
      const eAdded = new Set<string>(diff.data ? diff.data.edges.added : []);
      const eChanged = new Set<string>(diff.data ? diff.data.edges.changed.map((c: { key: string }) => c.key) : []);
      const ns: Node[] = v.nodes.map((n) => {
        const members = [n.id, ...(n.member_keys ?? [])];
        const d: NodeData = { ...n, diff: members.some((m) => added.has(m)) ? "added" : members.some((m) => changed.has(m)) ? "changed" : undefined };
        return { id: n.id, type: "c4", position: ov[n.id] ?? laid.pos[n.id] ?? { x: 0, y: 0 }, data: d as never, width: NODE_W, height: NODE_H };
      });
      const es: Edge[] = v.edges.map((e) => {
        const usesOverride = !!(ov[e.source] || ov[e.target]);
        const d: EdgeData = { ...e, route: usesOverride ? undefined : laid.routes[e.id],
          diff: e.members.some((m) => eAdded.has(m)) ? "added" : e.members.some((m) => eChanged.has(m)) ? "changed" : undefined };
        return { id: e.id, source: e.source, target: e.target, type: "c4", data: d as never,
          markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: e.focal ? "#eb6c36" : e.kind === "calls" ? "#2e5aa8" : "#4f5d75" } };
      });
      setNodes(ns); setEdges(es);
      requestAnimationFrame(() => {
        if (zooming.current && !reduced()) {      // shared-element zoom: arrive slightly zoomed-in, then settle
          rf.setViewport({ x: 0, y: 0, zoom: 1.8 });
          setTimeout(() => rf.fitView({ padding: 0.15, duration: 450 }), 20);
        } else rf.fitView({ padding: 0.15 });
        zooming.current = false;
      });
    })();
    return () => { cancelled = true; };
  }, [q.data, diff.data, rf]);

  useEffect(() => {
    api<typeof lint>(`/projects/${projectId}/export/lint/${viewKey}${search.full ? "?full=true" : ""}`).then(setLint).catch(() => setLint(null));
  }, [projectId, viewKey, search.full, q.data?.snapshot.id]);

  const zoomInto = useCallback(async (target: string, nodeId?: string) => {
    setSel(null);
    if (nodeId && !reduced()) {
      const n = rf.getNode(nodeId);
      if (n) { rf.setCenter(n.position.x + NODE_W / 2, n.position.y + NODE_H / 2, { zoom: 2.4, duration: 380 }); await new Promise((r) => setTimeout(r, 380)); }
    }
    zooming.current = true;
    setSearch({ view: target });
  }, [rf, setSearch]);

  const goUp = useCallback(() => {
    const bc = q.data?.breadcrumbs;
    if (bc && bc.length > 1) setSearch({ view: bc[bc.length - 2].key });
  }, [q.data, setSearch]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input,textarea,select")) return;
      if (e.key === "Backspace") { e.preventDefault(); goUp(); }
      if (e.key === "Enter" && sel?.kind === "node" && (sel.data as NodeData).zoom) zoomInto((sel.data as NodeData).zoom!, sel.data.id);
      if (e.key === "Escape") setSel(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goUp, sel, zoomInto]);

  const onNodeDouble: NodeMouseHandler = (_, n) => {
    const d = n.data as unknown as NodeData;
    if (d.zoom) zoomInto(d.zoom, n.id);
    else if (d.kind === "container") toast.info("No component-level evidence exists for this container.");
  };
  const onHover: NodeMouseHandler = (_, n) => {          // hover prefetch of the next level
    const d = n.data as unknown as NodeData;
    if (d.zoom) qc.prefetchQuery({ queryKey: ["view", projectId, d.zoom, search.snapshot, search.full, search.deps], queryFn: () => api<View>(viewPath(projectId, d.zoom!, search)) });
  };
  const saveLayout = async () => {
    if (!Object.keys(moved.current).length) return;
    try {
      await api(`/projects/${projectId}/layouts/${viewKey}`, { method: "PUT", json: { overrides: moved.current, revision: q.data?.layout.revision } });
      toast.success("Layout saved — kept across regenerations"); qc.invalidateQueries({ queryKey: ["view", projectId, viewKey] });
    } catch (e) { toast.error((e as Error).message); }
  };

  if (q.isLoading) return <Spinner label="Generating diagram from the latest snapshot…" />;
  if (q.error) return <div className="p-6"><ErrorBox error={q.error} /></div>;
  const v = q.data!;
  return <div className="flex h-full flex-col">
    <div className="flex flex-wrap items-center gap-2 border-b border-rule bg-card/50 px-4 py-2">
      <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-sm">
        {v.breadcrumbs.map((b, i) => <span key={b.key} className="flex items-center gap-1">{i > 0 && <ChevronRight size={14} className="text-soft" />}
          {i < v.breadcrumbs.length - 1 ? <button className="text-link hover:underline" onClick={() => setSearch({ view: b.key })}>{b.title}</button> : <span className="font-semibold">{b.title}</span>}</span>)}
      </nav>
      <Badge tone="muted">L{v.level}</Badge>
      <Badge tone={v.budget.primary <= v.budget.max ? "ok" : "warn"} title="primary nodes / budget">{v.budget.primary}/{v.budget.max} primary</Badge>
      {(v as any).hidden_edges > 0 && <Badge tone="muted" title={(v as any).hidden_reason}>{(v as any).hidden_edges} weak deps hidden</Badge>}
      {lint && <Badge tone={lint.ok ? "ok" : "bad"} title={lint.violations.map((x) => `${x.rule}: ${x.detail}`).join("\n")}>lint {lint.ok ? "pass" : `${lint.violations.length} issues`}</Badge>}
      <div className="ml-auto flex flex-wrap items-center gap-2">
        <Select aria-label="Snapshot" value={search.snapshot ?? ""} onChange={(e) => setSearch({ snapshot: e.target.value || undefined })}>
          <option value="">Latest snapshot (v{snaps.data?.[0]?.version ?? "?"})</option>
          {snaps.data?.map((s) => <option key={s.id} value={s.id}>v{s.version} · {new Date(s.created_at).toLocaleString()}</option>)}</Select>
        <Select aria-label="Compare with" value={search.compare ?? ""} onChange={(e) => setSearch({ compare: e.target.value || undefined })}>
          <option value="">Compare: off</option>{snaps.data?.filter((s) => s.id !== v.snapshot.id).map((s) => <option key={s.id} value={s.id}>vs v{s.version}</option>)}</Select>
        {v.level === 2 && <><label className="flex items-center gap-1 text-xs text-muted"><input type="checkbox" checked={!!search.deps} onChange={(e) => setSearch({ deps: e.target.checked || undefined })} /> startup deps</label>
          <label className="flex items-center gap-1 text-xs text-muted"><input type="checkbox" checked={!!search.full} onChange={(e) => setSearch({ full: e.target.checked || undefined })} /> all containers</label></>}
        <Button size="sm" variant={search.table ? "primary" : "default"} onClick={() => setSearch({ table: !search.table || undefined })}><Table2 size={14} /> Table</Button>
        <Button size="sm" onClick={saveLayout} title="Persist dragged positions"><Workflow size={14} /> Save layout</Button>
        <Button size="sm" variant="ghost" title="Reset layout" onClick={async () => { await api(`/projects/${projectId}/layouts/${viewKey}`, { method: "DELETE" }); qc.invalidateQueries({ queryKey: ["view", projectId, viewKey] }); }}><RotateCcw size={14} /></Button>
        <Select aria-label="Export" value="" onChange={async (e) => {
          const f = e.target.value; if (!f) return;
          const ext = { svg: "svg", html: "html", mermaid: "mmd", structurizr: "dsl" }[f];
          try { await download(`/projects/${projectId}/export/${f}/${viewKey}${search.full ? "?full=true" : ""}`, `${viewKey.replace(/[:/]/g, "_")}.${ext}`); }
          catch (err) { toast.error((err as Error).message); }
        }}><option value="">Export…</option><option value="svg">SVG (linted)</option><option value="html">HTML (linted)</option><option value="mermaid">Mermaid</option><option value="structurizr">Structurizr DSL</option></Select>
      </div>
    </div>
    {v.detail_views.length > 0 && <div className="flex flex-wrap items-center gap-2 border-b border-rule px-4 py-1.5 text-xs text-muted">
      <span className="eyebrow">Overview · detail views</span>{v.detail_views.map((d) => <button key={d.key} onClick={() => zoomInto(d.key, d.key.includes("group:") ? `group:${d.key.split("group:")[1]}` : undefined)} className="rounded border border-rule px-2 py-0.5 hover:border-muted">{d.title} ({d.count})</button>)}</div>}
    {search.compare && diff.data && <div className="flex gap-3 border-b border-rule bg-paper-2 px-4 py-1.5 text-xs"><GitCompare size={14} />
      <span>vs v{diff.data.from.version}: <b className="text-ok">+{diff.data.summary.nodes_added}</b> nodes, <b className="text-bad">−{diff.data.summary.nodes_removed}</b>, <b className="text-warn">~{diff.data.summary.nodes_changed}</b> changed · edges <b className="text-ok">+{diff.data.summary.edges_added}</b> <b className="text-bad">−{diff.data.summary.edges_removed}</b></span>
      {diff.data.nodes.removed.length > 0 && <span className="truncate text-bad" title={diff.data.nodes.removed.join("\n")}>removed: {diff.data.nodes.removed.slice(0, 4).join(", ")}{diff.data.nodes.removed.length > 4 ? "…" : ""}</span>}</div>}
    {v.empty_reason ? <div className="p-8"><Empty title="No deeper level">{v.empty_reason} <button className="text-link" onClick={goUp}>Back</button></Empty></div>
      : search.table ? <div className="overflow-auto p-4"><Table head={["Element", "Kind", "Technology", "Origins", "Confidence", "Zoom"]}>
        {v.nodes.map((n) => <tr key={n.id} className="border-b border-rule"><td className="px-2 py-1.5 font-medium">{n.name}{n.focal && <Badge tone="accent">focal</Badge>}</td><td className="px-2">{n.kind}</td><td className="px-2 font-mono text-xs">{n.technology}</td>
          <td className="px-2"><OriginBadges origins={n.origins} /></td><td className="px-2">{Number(n.confidence).toFixed(2)}</td><td className="px-2">{n.zoom && <button className="text-link" onClick={() => zoomInto(n.zoom!)}>open</button>}</td></tr>)}
      </Table><h3 className="eyebrow mt-6 mb-2">Relationships</h3><Table head={["From", "Relation", "To", "Confidence"]}>
        {v.edges.map((e) => <tr key={e.id} className="border-b border-rule"><td className="px-2 py-1">{v.nodes.find((n) => n.id === e.source)?.name}</td><td className="px-2 font-mono text-xs">{e.label}</td><td className="px-2">{v.nodes.find((n) => n.id === e.target)?.name}</td><td className="px-2">{e.confidence.toFixed(2)}</td></tr>)}</Table></div>
      : <div className="relative min-h-0 flex-1">
        <ZoomContext.Provider value={zoomInto}><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} minZoom={0.1} maxZoom={3} proOptions={{ hideAttribution: true }}
          onNodesChange={(chs) => setNodes((ns) => ns.map((n) => { const c = chs.find((x) => x.type === "position" && x.id === n.id) as { position?: { x: number; y: number } } | undefined;
            if (c?.position) { moved.current[n.id] = c.position; return { ...n, position: c.position }; } const s = chs.find((x) => x.type === "select" && x.id === n.id) as { selected?: boolean } | undefined; return s ? { ...n, selected: s.selected } : n; }))}
          onNodeClick={(_, n) => setSel({ kind: "node", data: n.data as unknown as NodeData })} onEdgeClick={(_, e) => setSel({ kind: "edge", data: e.data as unknown as EdgeData })}
          onNodeDoubleClick={onNodeDouble} onNodeMouseEnter={onHover} onPaneClick={() => setSel(null)} deleteKeyCode={null} nodesConnectable={false} zoomOnDoubleClick={false} fitView>
          <Background gap={24} color="var(--color-rule)" />
          <Controls showInteractive={false} />
          <MiniMap pannable zoomable nodeColor={(n) => ((n.data as unknown as NodeData).focal ? "#eb6c36" : "#bfc0c0")} />
        </ReactFlow></ZoomContext.Provider>
        <EvidencePanel projectId={projectId} sel={sel} onClose={() => setSel(null)} onZoom={(k) => zoomInto(k, sel?.data.id)} />
        <div className="pointer-events-none absolute bottom-3 left-14 rounded bg-card/90 px-2 py-1 font-mono text-[9px] text-soft">
          double-click / Enter to zoom · Backspace up · solid = observed · dashed = depends-on / inferred · accent = focal</div>
      </div>}
  </div>;
}

export function ArchitecturePage({ projectId }: { projectId: string }) {
  const snaps = useApi<Snapshot[]>(["snapshots", projectId], `/projects/${projectId}/snapshots`, { refetchInterval: 10_000 });
  if (snaps.isLoading) return <Spinner />;
  if (snaps.error) return <div className="p-6"><ErrorBox error={snaps.error} /></div>;
  if (!snaps.data?.length) return <div className="p-6"><Card><Empty title="No architecture yet">Add a datasource in <b>Datasources</b> and run a scan — the graph, C4 diagrams and docs are generated from the evidence.</Empty></Card></div>;
  return <ReactFlowProvider><div className={cn("h-full")}><Canvas projectId={projectId} /></div></ReactFlowProvider>;
}
