import { Link, Outlet, useNavigate, useParams } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Bell, Boxes, Building2, ChevronDown, FileClock, Flag, Home, LogOut, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "react-oidc-context";
import { api, getOrg, setOrg } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { useApi, useMe } from "@/lib/hooks";
import type { Project } from "@/lib/types";
import { ago, Avatar, cn, Select } from "./ui";

interface Notif { id: string; title: string; body: string; link: string; occurrences: number; created_at: string; read_at?: string }

function useTheme() {
  const [t, setT] = useState(() => localStorage.getItem("at-theme") ?? "light");
  useEffect(() => { document.documentElement.setAttribute("data-theme", t); localStorage.setItem("at-theme", t); }, [t]);
  return [t, setT] as const;
}

function Notifications() {
  const [items, setItems] = useState<Notif[]>([]);
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  useEffect(() => {
    // SSE via fetch (Authorization header; EventSource cannot send headers)
    const ctl = new AbortController();
    (async () => {
      try {
        const r = await fetch("/api/v1/notifications/stream", { headers: { Authorization: `Bearer ${getToken()}`, ...(getOrg() ? { "X-ArchTwin-Org": getOrg()! } : {}) }, signal: ctl.signal });
        const reader = r.body!.getReader(); const dec = new TextDecoder(); let buf = "";
        for (;;) {
          const { value, done } = await reader.read(); if (done) break;
          buf += dec.decode(value, { stream: true });
          let i;
          while ((i = buf.indexOf("\n\n")) >= 0) {
            const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
            const data = chunk.split("\n").filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trim()).join("");
            if (data) { try { setItems(JSON.parse(data).items); } catch { /* ping */ } }
          }
        }
      } catch { /* aborted */ }
    })();
    return () => ctl.abort();
  }, []);
  return <div className="relative">
    <button aria-label={`Notifications (${items.length} unread)`} onClick={() => setOpen(!open)} className="relative rounded-md p-1.5 text-muted hover:bg-paper-2 hover:text-ink">
      <Bell size={18} />{items.length > 0 && <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-accent px-1 text-[10px] font-bold text-white">{items.length}</span>}
    </button>
    {open && <div className="fade-up absolute right-0 z-40 mt-2 w-96 overflow-hidden rounded-xl border border-rule bg-card shadow-lift">
      <div className="flex items-center justify-between border-b border-rule px-3 py-2"><span className="eyebrow">Notifications</span>
        <button className="text-xs text-link" onClick={async () => { await api("/notifications/read", { method: "POST", json: null }); setItems([]); }}>Mark all read</button></div>
      <ul className="max-h-96 overflow-auto">{items.length === 0 && <li className="p-4 text-sm text-soft">Nothing new.</li>}
        {items.map((n) => <li key={n.id}><button className="block w-full px-3 py-2 text-left hover:bg-paper-2" onClick={() => { setOpen(false); nav({ to: n.link }); }}>
          <div className="text-sm font-medium">{n.title}{n.occurrences > 1 && <span className="ml-1 text-xs text-soft">×{n.occurrences}</span>}</div>
          <div className="truncate text-xs text-muted">{n.body}</div><div className="text-[10px] text-soft">{ago(n.created_at)}</div></button></li>)}</ul>
    </div>}
  </div>;
}

const navCls = "flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-side-soft transition hover:bg-side-2 hover:text-side-ink";
const navActive = { className: "!bg-side-2 !text-side-ink font-medium shadow-[inset_2px_0_0_var(--color-accent)]" };

export function AppShell() {
  const me = useMe();
  const auth = useAuth();
  const qc = useQueryClient();
  const nav = useNavigate();
  const params = useParams({ strict: false }) as { projectId?: string };
  const projects = useApi<Project[]>(["projects", me.data?.org_id], me.data ? "/projects" : null);
  const [theme, setTheme] = useTheme();
  const [showAll, setShowAll] = useState(false);
  const isAdmin = me.data && ["org_owner", "org_admin"].includes(me.data.org_role);
  const list = projects.data ?? [];
  const visible = showAll ? list : list.filter((p, i) => i < 6 || p.id === params.projectId);
  return <div className="flex h-full">
    <aside className="flex w-60 shrink-0 flex-col bg-side text-side-ink">
      <Link to="/home" className="flex items-center gap-2.5 px-4 pb-3 pt-4"><img src="/logo.svg" alt="" className="h-8 w-8 rounded-lg bg-white/95 p-0.5" />
        <span><span className="serif block text-[1.6rem] leading-none">ArchTwin</span><span className="font-mono text-[9px] uppercase tracking-[0.18em] text-side-soft">architecture twin</span></span></Link>
      <nav className="flex-1 space-y-0.5 overflow-auto px-2.5 py-2 text-sm" aria-label="Main">
        <Link to="/home" className={navCls} activeProps={navActive}><Home size={16} /> Home</Link>
        <Link to="/projects" className={navCls} activeProps={navActive} activeOptions={{ exact: true }}><Boxes size={16} /> All projects</Link>
        <div className="px-2.5 pb-1.5 pt-5 font-mono text-[10px] uppercase tracking-[0.16em] text-side-soft">Projects</div>
        {visible.map((p) => <Link key={p.id} to="/projects/$projectId" params={{ projectId: p.id }}
          className={cn(navCls, "py-1", params.projectId === p.id && "!bg-side-2 !text-side-ink font-medium shadow-[inset_2px_0_0_var(--color-accent)]")}>
          <Avatar name={p.title} size={20} className="!rounded-md" onDark /><span className="truncate">{p.title}</span></Link>)}
        {list.length > 6 && <button onClick={() => setShowAll(!showAll)} className={cn(navCls, "w-full py-1 text-xs")}>
          <ChevronDown size={14} className={cn("transition", showAll && "rotate-180")} />{showAll ? "Show fewer" : `Show all ${list.length}`}</button>}
        {isAdmin && <><div className="px-2.5 pb-1.5 pt-5 font-mono text-[10px] uppercase tracking-[0.16em] text-side-soft">Organization</div>
          <Link to="/admin/flags" className={navCls} activeProps={navActive}><Flag size={16} /> Feature flags</Link>
          <Link to="/admin/audit" className={navCls} activeProps={navActive}><FileClock size={16} /> Audit trail</Link></>}
      </nav>
      <div className="m-2.5 rounded-lg bg-side-2/70 p-3">
        <div className="flex items-center gap-2.5">
          <Avatar name={me.data?.display_name ?? "?"} size={30} className="!rounded-full" onDark />
          <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium">{me.data?.display_name}</div>
            <div className="truncate text-[11px] text-side-soft">{me.data?.org_role.replace("_", " ")}</div></div>
          <button aria-label="Sign out" title="Sign out" onClick={() => auth.signoutRedirect()} className="rounded-md p-1.5 text-side-soft hover:bg-side hover:text-side-ink"><LogOut size={16} /></button>
        </div>
      </div>
    </aside>
    <div className="flex min-w-0 flex-1 flex-col">
      <header className="flex h-12 shrink-0 items-center justify-between gap-3 border-b border-rule bg-card/70 px-5 backdrop-blur">
        <div className="flex items-center gap-2 text-sm">
          <Building2 size={15} className="text-soft" />
          {me.data && me.data.orgs.length > 1 && <Select aria-label="Organization" value={me.data.org_id} onChange={(e) => { setOrg(e.target.value); qc.clear(); nav({ to: "/home" }); }}>
            {me.data.orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</Select>}
          {me.data && me.data.orgs.length <= 1 && <span className="font-medium text-muted">{me.data.orgs[0]?.name}</span>}
        </div>
        <div className="flex items-center gap-1">
          <Notifications />
          <button aria-label="Toggle theme" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} className="rounded-md p-1.5 text-muted hover:bg-paper-2 hover:text-ink">{theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}</button>
        </div>
      </header>
      <main className="min-h-0 flex-1 overflow-auto"><Outlet /></main>
    </div>
  </div>;
}
