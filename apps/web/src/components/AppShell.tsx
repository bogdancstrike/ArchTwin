import { Link, Outlet, useNavigate, useParams } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Bell, Boxes, FileClock, Flag, LogOut, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "react-oidc-context";
import { api, getOrg, setOrg } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { useApi, useMe } from "@/lib/hooks";
import type { Project } from "@/lib/types";
import { ago, cn, Select } from "./ui";

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
    {open && <div className="absolute right-0 z-40 mt-2 w-96 rounded-lg border border-rule bg-card shadow-lg">
      <div className="flex items-center justify-between border-b border-rule px-3 py-2"><span className="eyebrow">Notifications</span>
        <button className="text-xs text-link" onClick={async () => { await api("/notifications/read", { method: "POST", json: null }); setItems([]); }}>Mark all read</button></div>
      <ul className="max-h-96 overflow-auto">{items.length === 0 && <li className="p-4 text-sm text-soft">Nothing new.</li>}
        {items.map((n) => <li key={n.id}><button className="block w-full px-3 py-2 text-left hover:bg-paper-2" onClick={() => { setOpen(false); nav({ to: n.link }); }}>
          <div className="text-sm font-medium">{n.title}{n.occurrences > 1 && <span className="ml-1 text-xs text-soft">×{n.occurrences}</span>}</div>
          <div className="truncate text-xs text-muted">{n.body}</div><div className="text-[10px] text-soft">{ago(n.created_at)}</div></button></li>)}</ul>
    </div>}
  </div>;
}

export function AppShell() {
  const me = useMe();
  const auth = useAuth();
  const qc = useQueryClient();
  const nav = useNavigate();
  const params = useParams({ strict: false }) as { projectId?: string };
  const projects = useApi<Project[]>(["projects", me.data?.org_id], me.data ? "/projects" : null);
  const [theme, setTheme] = useTheme();
  const isAdmin = me.data && ["org_owner", "org_admin"].includes(me.data.org_role);
  return <div className="flex h-full">
    <aside className="flex w-56 shrink-0 flex-col border-r border-rule bg-paper-2/60">
      <Link to="/" className="flex items-center gap-2 px-4 py-4"><img src="/logo.svg" alt="" className="h-7 w-7" /><span className="serif text-2xl">ArchTwin</span></Link>
      <nav className="flex-1 space-y-0.5 px-2 text-sm" aria-label="Main">
        <Link to="/" className="flex items-center gap-2 rounded-md px-2 py-1.5 text-muted hover:bg-card hover:text-ink" activeProps={{ className: "bg-card !text-ink font-medium" }} activeOptions={{ exact: true }}><Boxes size={16} /> Projects</Link>
        <div className="eyebrow px-2 pb-1 pt-4">Projects</div>
        {projects.data?.map((p) => <Link key={p.id} to="/projects/$projectId" params={{ projectId: p.id }}
          className={cn("block truncate rounded-md px-2 py-1 text-muted hover:bg-card hover:text-ink", params.projectId === p.id && "bg-card font-medium text-ink")}>{p.title}</Link>)}
        {isAdmin && <><div className="eyebrow px-2 pb-1 pt-4">Organization</div>
          <Link to="/admin/flags" className="flex items-center gap-2 rounded-md px-2 py-1.5 text-muted hover:bg-card hover:text-ink" activeProps={{ className: "bg-card !text-ink font-medium" }}><Flag size={16} /> Feature flags</Link>
          <Link to="/admin/audit" className="flex items-center gap-2 rounded-md px-2 py-1.5 text-muted hover:bg-card hover:text-ink" activeProps={{ className: "bg-card !text-ink font-medium" }}><FileClock size={16} /> Audit trail</Link></>}
      </nav>
      <div className="border-t border-rule p-3 text-xs text-soft">Evidence-first architecture · v0.1</div>
    </aside>
    <div className="flex min-w-0 flex-1 flex-col">
      <header className="flex h-12 items-center justify-between gap-3 border-b border-rule bg-card/60 px-4">
        <div className="flex items-center gap-2 text-sm">
          {me.data && me.data.orgs.length > 1 && <Select aria-label="Organization" value={me.data.org_id} onChange={(e) => { setOrg(e.target.value); qc.clear(); nav({ to: "/" }); }}>
            {me.data.orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</Select>}
          {me.data && me.data.orgs.length <= 1 && <span className="text-muted">{me.data.orgs[0]?.name}</span>}
        </div>
        <div className="flex items-center gap-1">
          <Notifications />
          <button aria-label="Toggle theme" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} className="rounded-md p-1.5 text-muted hover:bg-paper-2 hover:text-ink">{theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}</button>
          <span className="ml-2 text-sm"><span className="font-medium">{me.data?.display_name}</span> <span className="text-soft">· {me.data?.org_role.replace("_", " ")}</span></span>
          <button aria-label="Sign out" onClick={() => auth.signoutRedirect()} className="rounded-md p-1.5 text-muted hover:bg-paper-2 hover:text-ink"><LogOut size={18} /></button>
        </div>
      </header>
      <main className="min-h-0 flex-1 overflow-auto"><Outlet /></main>
    </div>
  </div>;
}
