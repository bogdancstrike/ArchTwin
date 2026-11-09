import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/** Live search inside the current project for the command palette: elements, flows, decisions and documents.
 *  Debounced; each source is independent (a disabled module or a 403 just yields no results for that group). */
export interface Hit { kind: "element" | "flow" | "decision" | "document"; id: string; label: string; hint: string; to: string; search?: Record<string, string> }
export const MIN_QUERY = 2;
const PER_GROUP = 5;

const safe = <T,>(p: Promise<T>, fallback: T) => p.catch(() => fallback);

/** "component:shop/api/app.routes" -> "shop/api": tells same-named elements apart. */
function where(key: string): string {
  const parts = (key.split(":", 2)[1] ?? "").split("/");
  return parts.length > 1 ? parts.slice(0, -1).join("/").slice(0, 48) : "";
}

async function searchAll(projectId: string, q: string): Promise<Hit[]> {
  const enc = encodeURIComponent(q);
  const base = `/projects/${projectId}`;
  const paged = `page=1&page_size=${PER_GROUP}&q=${enc}`;
  const [els, flows, adrs, docs] = await Promise.all([
    safe(api<{ key: string; name: string; kind: string; technology: string; parent_view: string }[]>(`${base}/elements/search?q=${enc}&limit=${PER_GROUP}`), []),
    safe(api<{ items: { id: string; name: string; kind: string; length: number }[] }>(`${base}/flows?${paged}`), { items: [] }),
    safe(api<{ items: { id: string; number: number; title: string; status: string }[] }>(`${base}/adrs?${paged}`), { items: [] }),
    safe(api<{ items: { id: string; title: string; path: string }[] }>(`${base}/documents?${paged}`), { items: [] }),
  ]);
  return [
    ...els.map((e): Hit => ({ kind: "element", id: e.key, label: e.name, hint: [e.kind, where(e.key), e.technology].filter(Boolean).join(" · "),
      to: `${base}/architecture`, search: { view: e.parent_view, focus: e.key } })),
    ...flows.items.map((f): Hit => ({ kind: "flow", id: f.id, label: f.name, hint: `${f.kind} flow · ${f.length} steps`,
      to: `${base}/flows`, search: { flow: f.id, q: f.name } })),
    ...adrs.items.map((a): Hit => ({ kind: "decision", id: a.id, label: `ADR-${String(a.number).padStart(4, "0")} ${a.title}`, hint: a.status,
      to: `${base}/decisions`, search: { adr: a.id } })),
    ...docs.items.map((d): Hit => ({ kind: "document", id: d.id, label: d.title || d.path, hint: d.path, to: `${base}/docs`, search: { doc: d.id } })),
  ];
}

export function useProjectSearch(projectId: string | undefined, query: string) {
  const [q, setQ] = useState(query);
  useEffect(() => { const t = setTimeout(() => setQ(query.trim()), 220); return () => clearTimeout(t); }, [query]);
  const enabled = !!projectId && q.length >= MIN_QUERY;
  return useQuery({ queryKey: ["cmdk-search", projectId, q], queryFn: () => searchAll(projectId!, q), enabled, staleTime: 30_000,
    placeholderData: (p) => p, retry: false });
}
