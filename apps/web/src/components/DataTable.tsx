import { ChevronDown, ChevronUp, ChevronsUpDown, Search } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Button, ErrorBox, Input, Select, Skeleton, Table, cn } from "@/components/ui";
import { useApi } from "@/lib/hooks";

export const PAGE_SIZES = [5, 15, 25, 50, 100] as const;
export const DEFAULT_PAGE_SIZE = 15;

export interface Page<T> { items: T[]; total: number; page: number; page_size: number; pages: number }
export interface Column<T> { key: string; label: string; sortable?: boolean; render: (row: T) => ReactNode; className?: string; weight?: number }
export interface FilterDef { key: string; label: string; options: [string, string][] }

/** Server-side table: every list in the UI uses this contract (page, page_size, q, sort, dir + endpoint filters). */
export function DataTable<T>({ queryKey, endpoint, columns, rowKey, filters = [], defaultSort = "", defaultDir = "desc", searchPlaceholder = "Search",
  onRowClick, selected, empty = "Nothing here yet.", extraParams = {}, toolbar, onFiltersChange }: {
  queryKey: unknown[]; endpoint: string; columns: Column<T>[]; rowKey: (r: T) => string; filters?: FilterDef[]; defaultSort?: string;
  defaultDir?: "asc" | "desc"; searchPlaceholder?: string; onRowClick?: (r: T) => void; selected?: string | null; empty?: ReactNode;
  extraParams?: Record<string, string | undefined>; toolbar?: ReactNode;
  onFiltersChange?: (filters: Record<string, string>) => void;          // e.g. exports that follow the visible filters
}) {
  const [page, setPage] = useState(1);
  const [size, setSize] = useState<number>(DEFAULT_PAGE_SIZE);
  const [typed, setTyped] = useState("");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState(defaultSort);
  const [dir, setDir] = useState<"asc" | "desc">(defaultDir);
  const [vals, setVals] = useState<Record<string, string>>({});
  useEffect(() => { const t = setTimeout(() => { setQ(typed.trim()); setPage(1); }, 250); return () => clearTimeout(t); }, [typed]);
  useEffect(() => { onFiltersChange?.(vals); }, [vals, onFiltersChange]);
  const params = new URLSearchParams(Object.entries({ page: String(page), page_size: String(size), q, sort, dir, ...vals, ...extraParams })
    .filter((e): e is [string, string] => !!e[1]));
  const res = useApi<Page<T>>([...queryKey, params.toString()], `${endpoint}${endpoint.includes("?") ? "&" : "?"}${params}`, { keepPrevious: true });
  const toggleSort = (k: string) => { if (sort === k) setDir(dir === "asc" ? "desc" : "asc"); else { setSort(k); setDir("asc"); } setPage(1); };
  const head = columns.map((c) => c.sortable
    ? <button key={c.key} className="flex items-center gap-1 uppercase hover:text-ink" onClick={() => toggleSort(c.key)} aria-label={`Sort by ${c.label}`}>
        {c.label}{sort === c.key ? (dir === "asc" ? <ChevronUp size={12} /> : <ChevronDown size={12} />) : <ChevronsUpDown size={11} className="opacity-40" />}</button>
    : c.label);
  const d = res.data;
  return <div className="space-y-2">
    <div className="flex flex-wrap items-center gap-2">
      <div className="relative min-w-48 flex-1"><Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-soft" />
        <Input aria-label={searchPlaceholder} placeholder={searchPlaceholder} className="!pl-7 text-sm" value={typed} onChange={(e) => setTyped(e.target.value)} /></div>
      {filters.map((f) => <Select key={f.key} aria-label={f.label} value={vals[f.key] ?? ""} onChange={(e) => { setVals((v) => ({ ...v, [f.key]: e.target.value })); setPage(1); }}>
        <option value="">{f.label}: all</option>{f.options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select>)}
      {toolbar}
    </div>
    <ErrorBox error={res.error} />
    {!d ? <Skeleton className="h-40" /> : <>
      <div className={cn(res.isFetching && "opacity-70 transition-opacity")}>
        <Table head={head} weights={columns.map((c) => c.weight ?? 1)}>{d.items.map((r) => { const k = rowKey(r);
          return <tr key={k} onClick={onRowClick ? () => onRowClick(r) : undefined}
            className={cn("border-b border-rule align-top", onRowClick && "cursor-pointer hover:bg-paper-2", selected === k && "bg-paper-2")}>
            {columns.map((c) => <td key={c.key} className={cn("px-2 py-1.5 text-sm", c.className)}>{c.render(r)}</td>)}</tr>; })}</Table>
        {d.items.length === 0 && <p className="py-6 text-center text-sm text-soft">{q || Object.values(vals).some(Boolean) ? "No result matches." : empty}</p>}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="text-muted">{d.total.toLocaleString()} total · page {d.page} of {d.pages}</span>
        <div className="flex items-center gap-2"><Select aria-label="Rows per page" value={size} onChange={(e) => { setSize(Number(e.target.value)); setPage(1); }}>
          {PAGE_SIZES.map((n) => <option key={n} value={n}>{n} / page</option>)}</Select>
          <Button size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
          <Button size="sm" disabled={page >= d.pages} onClick={() => setPage(page + 1)}>Next</Button></div>
      </div></>}
  </div>;
}
