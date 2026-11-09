import { Link, useNavigate } from "@tanstack/react-router";
import { Plus, Search } from "lucide-react";
import { useState } from "react";
import { Button, Dialog, Empty, ErrorBox, Field, Input, PageHeader, Select, Skeleton, Textarea } from "@/components/ui";
import { type HomeData, ProjectHealthCard } from "./Home";
import { api } from "@/lib/api";
import { useAction, useApi, useMe } from "@/lib/hooks";
import type { Project } from "@/lib/types";

export function NewProjectDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const nav = useNavigate();
  const [f, setF] = useState({ title: "", purpose: "", tags: "", environments: "production" });
  const create = useAction((b: typeof f) => api<Project>("/projects", { method: "POST", idempotent: true, json: {
    title: b.title, purpose: b.purpose, tags: b.tags.split(",").map((t) => t.trim()).filter(Boolean),
    environments: b.environments.split(",").map((t) => t.trim()).filter(Boolean) } }), [["projects"], ["home"]], "Project created");
  return <Dialog open={open} onClose={onClose} title="New project">
    <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); const p = await create.mutateAsync(f); onClose(); nav({ to: "/projects/$projectId", params: { projectId: p.id } }); }}>
      <Field label="Title"><Input required minLength={2} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="e.g. Payments platform" autoFocus /></Field>
      <Field label="Purpose" hint="What this architecture is for — shown to everyone in the project."><Textarea rows={3} value={f.purpose} onChange={(e) => setF({ ...f, purpose: e.target.value })} /></Field>
      <Field label="Tags" hint="Comma separated"><Input value={f.tags} onChange={(e) => setF({ ...f, tags: e.target.value })} /></Field>
      <Field label="Environments" hint="Comma separated"><Input value={f.environments} onChange={(e) => setF({ ...f, environments: e.target.value })} /></Field>
      <p className="text-xs text-soft">You become the project owner. Projects are isolated: nothing is shared with other projects unless explicitly granted.</p>
      <ErrorBox error={create.error} />
      <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" disabled={create.isPending}>Create project</Button></div>
    </form>
  </Dialog>;
}

export function ProjectsPage() {
  const me = useMe();
  const h = useApi<HomeData>(["home", me.data?.org_id], me.data ? "/home" : null);
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"activity" | "name" | "drift">("activity");
  const matches = (p: { title: string; purpose: string; tags: string[] }) => !q || `${p.title} ${p.purpose} ${p.tags.join(" ")}`.toLowerCase().includes(q.toLowerCase());
  const truncated = !!h.data?.totals.truncated;
  const all = useApi<Project[]>(["projects", me.data?.org_id], truncated ? "/projects" : null);   // home caps at the 60 most recent
  const shown = new Set((h.data?.projects ?? []).map((p) => p.id));
  const rest = (all.data ?? []).filter((p) => !shown.has(p.id) && matches(p)).sort((a, b) => a.title.localeCompare(b.title));
  const list = (h.data?.projects ?? []).filter(matches)
    .sort((a, b) => sort === "name" ? a.title.localeCompare(b.title) : sort === "drift" ? (b.drift?.open ?? 0) - (a.drift?.open ?? 0) : b.last_activity.localeCompare(a.last_activity));
  return <div className="hero-wash min-h-full"><div className="mx-auto max-w-7xl space-y-6 p-8">
    <PageHeader eyebrow={me.data?.orgs.find((o) => o.id === me.data?.org_id)?.name} title="Projects"
      actions={<Button variant="primary" onClick={() => setOpen(true)}><Plus size={16} /> New project</Button>}>
      Each project is a living twin of one architecture: what was designed, what the code says and what is running.</PageHeader>
    <div className="flex flex-wrap items-center gap-2">
      <div className="relative w-full max-w-sm"><Search size={15} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-soft" />
        <Input aria-label="Search projects" placeholder="Search projects, purposes, tags…" value={q} onChange={(e) => setQ(e.target.value)} className="pl-8" /></div>
      <Select aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}>
        <option value="activity">Recent activity</option><option value="name">Name</option><option value="drift">Most drift</option></Select>
      {h.data && <span className="ml-auto text-sm text-soft">{list.length + rest.length} of {h.data.totals.visible_projects ?? h.data.projects.length}</span>}
    </div>
    <ErrorBox error={h.error} />
    {h.data?.projects.length === 0 && <Empty title="No projects yet">Create one, connect a repository and the platform builds the architecture from evidence.</Empty>}
    {h.data && h.data.projects.length > 0 && list.length === 0 && <Empty title="No match">Nothing matches “{q}”.</Empty>}
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {!h.data ? [0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-48 !rounded-xl" />) : list.map((p) => <ProjectHealthCard key={p.id} p={p} />)}
    </div>
    {rest.length > 0 && <section aria-label="Other projects" className="space-y-2">
      <h2 className="text-sm font-semibold text-soft">Other projects <span className="font-normal">(no recent activity)</span></h2>
      <ul className="divide-y divide-rule overflow-hidden rounded-xl border border-rule bg-card">
        {rest.map((p) => <li key={p.id}><Link to="/projects/$projectId" params={{ projectId: p.id }} className="flex items-baseline gap-3 px-4 py-2.5 hover:bg-paper-2">
          <span className="font-medium">{p.title}</span><span className="truncate text-sm text-soft">{p.purpose}</span></Link></li>)}
      </ul>
    </section>}
    <NewProjectDialog open={open} onClose={() => setOpen(false)} />
  </div></div>;
}
