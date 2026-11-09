import { useNavigate, useParams } from "@tanstack/react-router";
import { Command } from "cmdk";
import {
  AlertTriangle, Bot, Boxes, Clock, Coins, CornerDownLeft, FileClock, FilePlus2, FileText, Flag, FolderPlus, Home, KeyRound, LayoutDashboard,
  LogOut, Moon, Network, Play, Plus, Radar, RefreshCw, ScrollText, Search, Server, Settings, Star, Sun, Workflow, type LucideIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "react-oidc-context";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useApi, useFavorites, useMe } from "@/lib/hooks";
import { toggleTheme, useTheme } from "@/lib/theme";
import type { Project } from "@/lib/types";
import { pushRecent, readRecent, type RecentItem } from "./recent";
import { MIN_QUERY, useProjectSearch, type Hit } from "./useProjectSearch";

/** ⌘K / Ctrl+K: go anywhere, switch project, run an action, or search the current project's architecture, flows,
 *  decisions and documents. Static items are fuzzy-filtered by cmdk; server results are already filtered (forceMount). */

const PROJECT_PAGES: [string, string, LucideIcon][] = [["", "Overview", LayoutDashboard], ["architecture", "Architecture", Network],
  ["flows", "Flows", Workflow], ["drift", "Drift", AlertTriangle], ["decisions", "Decisions", ScrollText], ["docs", "Docs", FileText],
  ["assistant", "Assistant", Bot], ["datasources", "Datasources", Radar], ["settings", "Settings", Settings]];
const HIT_ICON: Record<Hit["kind"], LucideIcon> = { element: Network, flow: Workflow, decision: ScrollText, document: FileText };
const HIT_GROUP: [Hit["kind"], string][] = [["element", "Architecture elements"], ["flow", "Flows"], ["decision", "Decisions"], ["document", "Documents"]];
const RECENT_ICON: Record<string, LucideIcon> = { page: LayoutDashboard, project: Boxes, ...HIT_ICON };
const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
export const MOD = isMac ? "⌘" : "Ctrl";

interface Dest { id: string; label: string; hint?: string; kind: string; to: string; search?: Record<string, string>; icon: LucideIcon; keywords?: string[] }

function Kbd({ children }: { children: React.ReactNode }) {
  return <kbd className="rounded border border-rule bg-paper px-1.5 py-0.5 font-mono text-[10px] text-soft">{children}</kbd>;
}

function Row({ icon: I, label, hint, shortcut }: { icon: LucideIcon; label: string; hint?: string; shortcut?: string }) {
  return <><I size={15} className="shrink-0 text-soft" aria-hidden /><span className="min-w-0 flex-1 truncate">{label}</span>
    {hint && <span className="max-w-[45%] truncate text-xs text-soft">{hint}</span>}{shortcut && <Kbd>{shortcut}</Kbd>}</>;
}

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const nav = useNavigate();
  const auth = useAuth();
  const me = useMe();
  const theme = useTheme();
  const { projectId } = useParams({ strict: false }) as { projectId?: string };
  const projects = useApi<Project[]>(["projects", me.data?.org_id], me.data && open ? "/projects" : null);
  const { favs } = useFavorites();
  const [query, setQuery] = useState("");
  const [recent, setRecent] = useState<RecentItem[]>([]);
  const found = useProjectSearch(open ? projectId : undefined, query);
  useEffect(() => { if (open) setRecent(readRecent()); else setQuery(""); }, [open]);

  const current = projects.data?.find((p) => p.id === projectId);
  const isAdmin = !!me.data && ["org_owner", "org_admin"].includes(me.data.org_role);
  const close = () => onOpenChange(false);
  const go = (d: Omit<Dest, "icon">) => {
    pushRecent({ id: d.id, label: d.label, hint: d.hint, kind: d.kind, to: d.to, search: d.search });
    close();
    void nav({ to: d.to, search: d.search } as never);
  };
  const run = (label: string, fn: () => Promise<unknown> | void) => { close(); void Promise.resolve(fn()).catch((e: Error) => toast.error(`${label}: ${e.message}`)); };

  const pages = useMemo<Dest[]>(() => [
    ...(projectId ? PROJECT_PAGES.map(([path, label, icon]): Dest => ({ id: `page:${projectId}:${path}`, label, hint: current?.title, kind: "page",
      to: `/projects/${projectId}${path ? `/${path}` : ""}`, icon, keywords: [current?.title ?? "", "project"] })) : []),
    { id: "page:home", label: "Home", kind: "page", to: "/home", icon: Home },
    { id: "page:projects", label: "All projects", kind: "page", to: "/projects", icon: Boxes },
    { id: "page:usage", label: "Usage & costs", kind: "page", to: "/usage", icon: Coins, keywords: ["spend", "tokens", "models", "pricing"] },
    ...(isAdmin ? [
      { id: "page:system", label: "System", kind: "page", to: "/admin/system", icon: Server, keywords: ["source roots", "health"] },
      { id: "page:roles", label: "Roles & permissions", kind: "page", to: "/admin/roles", icon: KeyRound, keywords: ["policies", "cerbos"] },
      { id: "page:flags", label: "Feature flags", kind: "page", to: "/admin/flags", icon: Flag },
      { id: "page:audit", label: "Audit trail", kind: "page", to: "/admin/audit", icon: FileClock },
    ] : []),
  ], [projectId, current?.title, isAdmin]);

  const switchable = useMemo(() => [...(projects.data ?? [])].filter((p) => p.id !== projectId)
    .sort((a, b) => Number(favs.includes(b.id)) - Number(favs.includes(a.id)) || a.title.localeCompare(b.title)), [projects.data, projectId, favs]);

  const hits = query.trim().length >= MIN_QUERY ? found.data ?? [] : [];
  const showRecent = !query.trim() && recent.length > 0;

  return <Command.Dialog open={open} onOpenChange={onOpenChange} label="Command palette" loop
    overlayClassName="fixed inset-0 z-50 bg-ink/35 backdrop-blur-[2px]"
    contentClassName="fixed left-1/2 top-[12vh] z-50 w-[min(680px,calc(100vw-2rem))] -translate-x-1/2 overflow-hidden rounded-xl border border-rule bg-card text-ink shadow-lift fade-up">
    <div className="flex items-center gap-2 border-b border-rule px-3">
      <Search size={16} className="shrink-0 text-soft" aria-hidden />
      <Command.Input value={query} onValueChange={setQuery} data-testid="cmdk-input"
        placeholder={projectId ? `Search ${current?.title ?? "this project"} — elements, flows, decisions, docs — or type a command` : "Go to a page, switch project or run a command"}
        className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-soft" />
      {found.isFetching && <RefreshCw size={14} className="shrink-0 animate-spin text-soft" aria-label="Searching" />}
    </div>
    <Command.List className="max-h-[min(60vh,520px)] overflow-y-auto overscroll-contain p-2">
      <Command.Empty className="px-3 py-6 text-center text-sm text-soft">{found.isFetching ? "Searching…" : "No results."}</Command.Empty>

      {showRecent && <Command.Group heading="Recent">
        {recent.map((r) => <Command.Item key={r.id} value={`recent ${r.id} ${r.label}`} keywords={[r.hint ?? ""]} onSelect={() => go(r)}>
          <Row icon={RECENT_ICON[r.kind] ?? Clock} label={r.label} hint={r.hint} /></Command.Item>)}
      </Command.Group>}

      {HIT_GROUP.map(([kind, heading]) => {
        const items = hits.filter((h) => h.kind === kind);
        return items.length > 0 && <Command.Group key={kind} heading={heading} forceMount>
          {items.map((h) => <Command.Item key={`${kind}:${h.id}`} value={`hit ${kind} ${h.id}`} forceMount data-testid={`cmdk-hit-${kind}`}
            onSelect={() => go({ id: `${kind}:${h.id}`, label: h.label, hint: h.hint, kind, to: h.to, search: h.search })}>
            <Row icon={HIT_ICON[kind]} label={h.label} hint={h.hint} /></Command.Item>)}
        </Command.Group>;
      })}

      <Command.Group heading={projectId ? `Go to · ${current?.title ?? "project"}` : "Go to"}>
        {pages.map((p) => <Command.Item key={p.id} value={`page ${p.id} ${p.label}`} keywords={p.keywords} onSelect={() => go(p)}>
          <Row icon={p.icon} label={p.label} /></Command.Item>)}
      </Command.Group>

      <Command.Group heading="Actions">
        <Command.Item value="action new project" keywords={["create"]} onSelect={() => go({ id: "page:projects", label: "All projects", kind: "page", to: "/projects", search: { new: "1" } })}>
          <Row icon={FolderPlus} label="New project" /></Command.Item>
        {projectId && <>
          <Command.Item value="action add datasource" keywords={["connector", "source", "directory", "gitlab", "github", "taiga"]}
            onSelect={() => go({ id: `page:${projectId}:datasources`, label: "Datasources", kind: "page", to: `/projects/${projectId}/datasources`, search: { add: "1" } })}>
            <Row icon={Plus} label="Add datasource" hint={current?.title} /></Command.Item>
          <Command.Item value="action scan all datasources" keywords={["rescan", "refresh", "analyse", "analyze"]}
            onSelect={() => run("Scan", async () => {
              const r = await api<{ queued: unknown[]; skipped: { name: string; reason: string }[] }>(`/projects/${projectId}/scan`, { method: "POST", idempotent: true });
              toast.success(`${r.queued.length} scan${r.queued.length === 1 ? "" : "s"} queued${r.skipped.length ? ` · ${r.skipped.length} skipped` : ""}`);
            })}><Row icon={Play} label="Scan all datasources" hint={current?.title} /></Command.Item>
          <Command.Item value="action evaluate drift" keywords={["check", "non-conformities"]}
            onSelect={() => run("Drift evaluation", async () => {
              await api(`/projects/${projectId}/drift/evaluate`, { method: "POST" });
              toast.success("Drift evaluated");
              void nav({ to: `/projects/${projectId}/drift` } as never);
            })}><Row icon={AlertTriangle} label="Evaluate drift now" hint={current?.title} /></Command.Item>
          <Command.Item value="action generate documentation" keywords={["docs", "user guide", "prd", "arf"]}
            onSelect={() => go({ id: `page:${projectId}:docs`, label: "Docs", kind: "page", to: `/projects/${projectId}/docs` })}>
            <Row icon={FilePlus2} label="Generate documentation" hint={current?.title} /></Command.Item>
          <Command.Item value="action new adr decision" keywords={["madr", "record"]}
            onSelect={() => go({ id: `page:${projectId}:decisions`, label: "Decisions", kind: "page", to: `/projects/${projectId}/decisions`, search: { new: "1" } })}>
            <Row icon={ScrollText} label="New decision record (ADR)" hint={current?.title} /></Command.Item>
        </>}
        <Command.Item value="action toggle theme dark light night mode" onSelect={() => { toggleTheme(); close(); }}>
          <Row icon={theme === "dark" ? Sun : Moon} label={theme === "dark" ? "Switch to light theme" : "Switch to night theme"} shortcut={`${MOD}⇧L`} /></Command.Item>
        <Command.Item value="action sign out logout" onSelect={() => { close(); void auth.signoutRedirect(); }}>
          <Row icon={LogOut} label="Sign out" /></Command.Item>
      </Command.Group>

      {switchable.length > 0 && <Command.Group heading="Switch project">
        {switchable.map((p) => <Command.Item key={p.id} value={`project ${p.id} ${p.title}`} keywords={[p.purpose ?? ""]}
          onSelect={() => go({ id: `project:${p.id}`, label: p.title, kind: "project", to: `/projects/${p.id}` })}>
          <Row icon={favs.includes(p.id) ? Star : Boxes} label={p.title} hint={favs.includes(p.id) ? "favorite" : undefined} /></Command.Item>)}
      </Command.Group>}
    </Command.List>
    <div className="flex items-center gap-3 border-t border-rule px-3 py-2 text-[11px] text-soft">
      <span className="flex items-center gap-1"><Kbd>↑</Kbd><Kbd>↓</Kbd> navigate</span>
      <span className="flex items-center gap-1"><Kbd><CornerDownLeft size={10} className="inline" /></Kbd> open</span>
      <span className="flex items-center gap-1"><Kbd>esc</Kbd> close</span>
      <span className="ml-auto flex items-center gap-1"><Kbd>{MOD}K</Kbd> anywhere</span>
    </div>
  </Command.Dialog>;
}

/** Global shortcuts: ⌘K / Ctrl+K toggles the palette, ⌘⇧L / Ctrl+Shift+L toggles the theme. */
export function useCommandShortcuts(toggle: () => void) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey)) return;
      const key = e.key.toLowerCase();
      if (key === "k" && !e.shiftKey) { e.preventDefault(); toggle(); }
      else if (key === "l" && e.shiftKey) { e.preventDefault(); toggleTheme(); }
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [toggle]);
}
