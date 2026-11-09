import { ArrowUp, ChevronRight, Clock, FileText, FolderClosed, FolderGit2, FolderOpen, GitBranch, HardDrive, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Badge, Button, Dialog, ErrorBox, Input, Skeleton, cn } from "@/components/ui";
import { useApi } from "@/lib/hooks";

export interface FolderListing {
  path: string; name: string; parent: string | null; root: string | null; places: { name: string; path: string }[];
  layout: "repository" | "folder of repositories" | "plain directory" | null; repositories?: number; markers: string[]; truncated?: boolean;
  suggested_content?: "auto" | "docs"; folders: { name: string; path: string; is_repo: boolean; has_children: boolean }[];
}

const RECENT_KEY = "archtwin.recentSourceFolders";

function loadRecent(): string[] {
  try { const v = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); return Array.isArray(v) ? v.filter((x) => typeof x === "string").slice(0, 6) : []; }
  catch { return []; }
}
function saveRecent(p: string) {
  try { localStorage.setItem(RECENT_KEY, JSON.stringify([p, ...loadRecent().filter((x) => x !== p)].slice(0, 6))); } catch { /* storage unavailable */ }
}

/** Browse the mounted source roots on the server and choose a directory: places, recent, typed/pasted paths, filter, keyboard. */
export function FolderPicker({ endpoint, open, value, onClose, onChoose, title = "Choose a local directory" }: {
  endpoint: string; open: boolean; value: string; onClose: () => void; onChoose: (path: string, info: FolderListing) => void; title?: string;
}) {
  const [path, setPath] = useState(value);
  const [filter, setFilter] = useState("");
  const [typed, setTyped] = useState<string | null>(null);        // null = not editing the path bar
  const [cursor, setCursor] = useState(0);
  const [recent, setRecent] = useState<string[]>([]);
  const listRef = useRef<HTMLDivElement>(null);
  const clickTimer = useRef<number | undefined>(undefined);      // a click opens a folder, unless a double-click (choose) follows
  useEffect(() => () => window.clearTimeout(clickTimer.current), []);
  const q = useApi<FolderListing>(["source-folders", endpoint, path], open ? `${endpoint}${path ? `?path=${encodeURIComponent(path)}` : ""}` : null);
  const data = q.data;

  useEffect(() => { if (open) { setPath(value); setRecent(loadRecent()); } }, [open, value]);
  useEffect(() => { setFilter(""); setCursor(0); }, [path]);
  useEffect(() => { if (q.error && path) setPath(""); }, [q.error]);                // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { listRef.current?.querySelector<HTMLElement>(`[data-i="${cursor}"]`)?.scrollIntoView({ block: "nearest" }); }, [cursor]);

  const shown = useMemo(() => {
    const f = filter.trim().toLowerCase();
    return (data?.folders ?? []).filter((x) => !f || x.name.toLowerCase().includes(f));
  }, [data, filter]);

  const choose = (p: string) => { if (!p || !data) return; saveRecent(p); onChoose(p, data); };
  const up = () => data?.parent !== undefined && data?.parent !== null && setPath(data.parent);

  const onKey = (e: KeyboardEvent) => {
    if ((e.target as HTMLElement).tagName === "INPUT" && !["ArrowDown", "ArrowUp", "Enter"].includes(e.key)) return;
    if (e.key === "Enter" && (e.target as HTMLElement).closest('button, [role="button"]')) return;   // Enter on a control is that control's
    if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, shown.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
    else if (e.key === "Enter" && shown[cursor]) { e.preventDefault(); if (e.ctrlKey || e.metaKey) choose(shown[cursor].path); else setPath(shown[cursor].path); }
    else if (e.key === "Backspace" && !filter && (e.target as HTMLElement).tagName !== "INPUT") { e.preventDefault(); up(); }
  };

  // breadcrumb: the root (one segment, as mounted) then each folder below it
  const root = data?.root ?? "";
  const rel = root && data?.path.startsWith(root) ? data.path.slice(root.length).replace(/^\/+/, "") : "";
  const parts = rel ? rel.split("/") : [];

  const Side = ({ icon: I, label, to, title }: { icon: typeof FolderOpen; label: string; to: string; title?: string }) =>
    <button type="button" onClick={() => setPath(to)} title={title ?? to}
      className={cn("flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-[13px] text-muted hover:bg-paper-2 hover:text-ink",
        path === to && "bg-paper-2 font-medium text-ink")}>
      <I size={14} className="shrink-0 opacity-70" /><span className="truncate">{label}</span></button>;

  return <Dialog open={open} onClose={onClose} title={title} wide>
    <div className="flex flex-col gap-3 sm:flex-row" onKeyDown={onKey}>
      <nav aria-label="Places" className="flex gap-1 overflow-x-auto pb-1 sm:w-48 sm:shrink-0 sm:flex-col sm:overflow-visible sm:pb-0">
        <div className="eyebrow hidden px-2.5 pb-1 sm:block">Places</div>
        <Side icon={HardDrive} label="All sources" to="" title="Mounted source roots" />
        {(data?.places ?? []).map((p) => <Side key={p.path} icon={FolderOpen} label={p.name} to={p.path} />)}
        {recent.length > 0 && <div className="eyebrow hidden px-2.5 pb-1 pt-3 sm:block">Recent</div>}
        {recent.map((r) => <Side key={`r-${r}`} icon={Clock} label={r.split("/").pop() || r} to={r} />)}
      </nav>

      <div className="min-w-0 flex-1">
        <div className="mb-2 flex items-center gap-1.5">
          <Button type="button" size="sm" variant="ghost" disabled={!path} onClick={up} aria-label="Up one folder"><ArrowUp size={14} /></Button>
          {typed === null
            ? <div role="button" tabIndex={0} title="Click to type or paste a path" aria-label="Current path — click to type a path"
                onClick={() => setTyped(data?.path || "")}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); setTyped(data?.path || ""); } }}
                className="flex min-w-0 flex-1 cursor-text items-center gap-0.5 overflow-hidden rounded-md border border-rule bg-paper/60 px-2 py-1 font-mono text-[12px]">
                <button type="button" onClick={(e) => { e.stopPropagation(); setPath(root || ""); }} className="inline-flex shrink-0 items-center gap-1 text-muted hover:text-ink">
                  <HardDrive size={12} /> {root || "All sources"}</button>
                {parts.map((p, i) => <span key={i} className="inline-flex min-w-0 items-center">
                  <ChevronRight size={12} className="shrink-0 text-soft" />
                  <button type="button" onClick={(e) => { e.stopPropagation(); setPath(`${root}/${parts.slice(0, i + 1).join("/")}`); }}
                    className={cn("truncate hover:text-ink", i === parts.length - 1 ? "font-medium text-ink" : "text-muted")}>{p}</button></span>)}
              </div>
            : <Input autoFocus value={typed} aria-label="Type a path" className="font-mono text-xs" placeholder="/home/me/workspace/project/backend"
                onChange={(e) => setTyped(e.target.value)}
                onBlur={(e) => {   // close when the user moves to another control of the picker; a focus loss to the page (re-render) keeps editing
                  const to = e.relatedTarget as Node | null;
                  if (to && e.currentTarget.closest('[role="dialog"]')?.contains(to)) setTyped(null);
                }}
                onKeyDown={(e) => { if (e.key === "Escape") setTyped(null); if (e.key === "Enter") { e.preventDefault(); setPath(typed.trim().replace(/\/+$/, "")); setTyped(null); } e.stopPropagation(); }} />}
        </div>
        <div className="relative mb-2"><Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-soft" />
          <Input aria-label="Filter folders" placeholder="Filter folders" className="!pl-7 text-xs" value={filter} onChange={(e) => { setFilter(e.target.value); setCursor(0); }} /></div>

        <div ref={listRef} tabIndex={0} role="listbox" aria-label="Folders" className="h-[46vh] min-h-[220px] overflow-y-auto rounded-xl border border-rule bg-paper/60 p-1.5 outline-none">
          {q.error ? <ErrorBox error={q.error} />
            : !data ? <div className="space-y-2 p-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-8" />)}</div>
            : shown.length === 0 ? <p className="py-10 text-center text-sm text-soft">{filter ? "No folder matches" : "No subfolders here: you can use this folder"}</p>
            : shown.map((f, i) => <button type="button" role="option" aria-selected={i === cursor} key={f.path} data-i={i}
                onClick={(e) => { setCursor(i); window.clearTimeout(clickTimer.current); if (e.detail > 1) return;
                  clickTimer.current = window.setTimeout(() => setPath(f.path), 250); }}
                onDoubleClick={() => { window.clearTimeout(clickTimer.current); choose(f.path); }} onMouseEnter={() => setCursor(i)}
                className={cn("flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px]", i === cursor ? "bg-paper-2" : "hover:bg-paper-2", q.isFetching && "opacity-60")}>
                {f.is_repo ? <FolderGit2 size={16} className="shrink-0 text-accent" /> : <FolderClosed size={16} className="shrink-0 text-muted" />}
                <span className="min-w-0 flex-1 truncate">{f.name}</span>
                {f.is_repo && <Badge tone="link">git</Badge>}
                {f.has_children && <ChevronRight size={14} className="text-soft" />}
              </button>)}
        </div>
        {data?.truncated && <p className="mt-1 text-[11px] text-warn-ink">Only the first 500 folders are listed — type a path or filter.</p>}
        <p className="mt-2 text-[11px] text-soft">Click a folder to open it, double-click (or Ctrl+Enter) to choose it. ↑ ↓ to move, Enter to open, Backspace to go up. Click the path to paste one.
          Only folders mounted read-only for ArchTwin and whitelisted in System › Source roots are visible.</p>
      </div>
    </div>
    <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-rule pt-3">
      <span className="flex min-w-0 items-center gap-1.5 text-xs text-muted">
        {data?.layout && <>{data.layout === "repository" ? <GitBranch size={13} /> : data.layout === "folder of repositories" ? <FolderGit2 size={13} /> : <FileText size={13} />}
          <b className="font-medium">{data.layout}</b>{data.layout === "folder of repositories" && <span>· {data.repositories} repos, each scanned as its own system</span>}
          {data.markers.length > 0 && <span className="truncate">· {data.markers.join(", ")}</span>}</>}
      </span>
      <div className="flex gap-2"><Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
        <Button type="button" variant="primary" disabled={!data?.path} onClick={() => choose(data!.path)}>Use this folder</Button></div>
    </div>
  </Dialog>;
}
