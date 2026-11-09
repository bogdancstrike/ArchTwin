import { ChevronRight } from "lucide-react";
import { useState, type ReactNode } from "react";
import { CodeBlock, type Source } from "@/components/CodeBlock";
import { Badge, ErrorBox, OriginBadges, Spinner, cn } from "@/components/ui";
import { useApi } from "@/lib/hooks";

/** Everything known about one element or relation — attributes, source, decisions, work items, documentation and the
 * observations behind it — shared by the Architecture side panel and the Flows inspector. */

export function ElementDetail({ projectId, elementKey }: { projectId: string; elementKey: string }) {
  const d = useApi<any>(["element-detail", projectId, elementKey], `/projects/${projectId}/elements/detail?key=${encodeURIComponent(elementKey)}`);
  if (!d.data) return null;
  const a = d.data.attributes ?? {};
  const L = d.data.linked;
  return <div className="space-y-3">
    {a.columns?.length > 0 && <div><div className="eyebrow mb-1">Columns ({a.columns.length})</div>
      <table className="w-full table-fixed text-xs"><tbody>{a.columns.map((c: any) => <tr key={c.name} className="border-b border-rule">
        <td className="py-0.5 pr-2 font-mono">{c.primary_key ? "🔑 " : ""}{c.name}</td><td className="py-0.5 pr-2 font-mono text-soft">{c.type}{c.nullable === false ? " · not null" : ""}</td>
        <td className="truncate py-0.5 font-mono text-link" title={c.references}>{c.references ? `→ ${c.references}` : ""}</td></tr>)}</tbody></table>
      {a.declared_in?.length > 0 && <div className="mt-1 text-[10px] text-soft">declared in {a.declared_in.slice(0, 3).map((x: any) => `${x.path}:${x.line} (${x.kind})`).join(", ")}</div>}</div>}
    {a.method_list?.length > 0 && <div><div className="eyebrow mb-1">Methods ({a.method_list.length})</div>
      <ul className="columns-2 text-xs">{a.method_list.map((m: any) => <li key={m.name + m.line} className="font-mono">{m.name}<span className="text-soft">:{m.line}</span></li>)}</ul></div>}
    {a.element && <div className="text-xs text-muted">{a.element} in <span className="font-mono">{a.path}:{a.line_start}-{a.line_end}</span>{a.bases?.length ? <> · extends <span className="font-mono">{a.bases.join(", ")}</span></> : null}</div>}
    {d.data.source && <div><div className="eyebrow mb-1">Source</div>
      <CodeBlock src={d.data.source} title={d.data.name} maxHeight={360}
        highlight={a.line_start ? [a.line_start, a.line_start] : d.data.kind !== "code" ? [d.data.source.start + 2, d.data.source.start + 2] : undefined} /></div>}
    {(L.adrs.length > 0 || L.work_items.length > 0) && <div><div className="eyebrow mb-1">Decisions &amp; work items</div>
      <ul className="space-y-1 text-xs">{[...L.adrs, ...L.work_items].map((x: any) => <li key={x.key} className="flex items-start gap-1.5">
        <Badge tone={x.key.startsWith("adr:") ? "link" : "muted"}>{x.key.startsWith("adr:") ? "ADR" : x.provider || "task"}</Badge>
        {x.url ? <a href={x.url} target="_blank" rel="noopener noreferrer" className="text-link hover:underline">{x.name}</a> : <span>{x.name}</span>}
        {(x.status || x.state) && <span className="text-soft">· {x.status || x.state}</span>}</li>)}</ul></div>}
    {L.documented.length > 0 && <div><div className="eyebrow mb-1">Drawn in documentation</div>
      <ul className="space-y-0.5 text-xs">{L.documented.map((x: any) => <li key={x.edge}>{x.direction === "out" ? "→" : "←"} {x.kind} {x.other} <span className="text-soft">({x.diagram})</span></li>)}</ul></div>}
    {d.data.mentions.length > 0 && <div><div className="eyebrow mb-1">Mentioned in docs &amp; code</div>
      <ul className="space-y-1 text-xs">{d.data.mentions.map((m: any, i: number) => <SourceItem key={i} projectId={projectId} path={m.path} line={m.line_start}
        badge={<Badge tone={m.kind === "code" ? "muted" : "link"}>{m.kind}</Badge>} snippet={m.snippet} />)}</ul></div>}
  </div>;
}

/** A file:line reference that expands into the highlighted source, fetched on demand (inspect code inside ArchTwin). */
export function SourceItem({ projectId, path, line, badge, snippet }: { projectId: string; path: string; line?: number; badge?: ReactNode; snippet?: string }) {
  const [open, setOpen] = useState(false);
  const src = useApi<Source>(["source", projectId, path, line], open ? `/projects/${projectId}/source?path=${encodeURIComponent(path)}&around=${line ?? 1}` : null);
  return <li className="rounded border border-rule p-1.5">
    <button type="button" className="flex w-full items-center gap-1 text-left hover:text-link" onClick={() => setOpen((o) => !o)} aria-expanded={open}
      title="Show the source">{badge}<span className="truncate font-mono">{path}{line ? `:${line}` : ""}</span><ChevronRight size={12} className={cn("ml-auto shrink-0 transition", open && "rotate-90")} /></button>
    {!open && snippet && <div className="mt-0.5 line-clamp-2 text-soft">{snippet}</div>}
    {open && <div className="mt-1.5">{src.error ? <ErrorBox error={src.error} /> : !src.data ? <Spinner /> :
      <CodeBlock src={src.data} highlight={line ? [line, line] : undefined} maxHeight={300} title={path} />}</div>}
  </li>;
}


interface Obs { id: string; origin: string; source_ref: string; source_revision: string; observed_at: string; parser_version: string; confidence: string;
  evidence: { path?: string; line_start?: number; line_end?: number }; attributes: Record<string, unknown> }

/** Observations (evidence) of an element or relation key; code locations open as highlighted source. */
export function EvidenceList({ projectId, elementKey, limit = 12 }: { projectId: string; elementKey: string; limit?: number }) {
  const obs = useApi<Obs[]>(["obs", projectId, elementKey], `/projects/${projectId}/observations?key=${encodeURIComponent(elementKey)}`);
  return <div><div className="eyebrow mb-1">Evidence ({obs.data?.length ?? "…"} observations)</div>
    {obs.isLoading && <Spinner />}
    <ul className="space-y-2 text-xs">{obs.data?.slice(0, limit).map((o) => o.source_ref && !o.source_ref.includes("://") && o.origin !== "runtime"
      ? <SourceItem key={o.id} projectId={projectId} path={o.evidence?.path || o.source_ref} line={o.evidence?.line_start}
          badge={<OriginBadges origins={[o.origin]} />} snippet={`rev ${(o.source_revision || "live").slice(0, 12)} · ${o.parser_version} · conf ${Number(o.confidence).toFixed(2)}`} />
      : <li key={o.id} className="rounded border border-rule p-2">
          <div className="flex justify-between"><OriginBadges origins={[o.origin]} /><span className="text-soft">{new Date(o.observed_at).toLocaleString()}</span></div>
          <div className="mt-1 break-all font-mono">{o.source_ref || "—"}</div>
          <div className="mt-1 text-soft">rev <span className="font-mono">{(o.source_revision || "live").slice(0, 12)}</span> · {o.parser_version} · conf {Number(o.confidence).toFixed(2)}</div></li>)}</ul>
  </div>;
}
