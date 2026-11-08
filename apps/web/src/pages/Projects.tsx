import { Link, useNavigate } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, Dialog, Empty, ErrorBox, Field, Input, Spinner, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useAction, useApi, useMe } from "@/lib/hooks";
import type { Project } from "@/lib/types";

export function NewProjectDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const nav = useNavigate();
  const [f, setF] = useState({ title: "", purpose: "", tags: "", environments: "production" });
  const create = useAction((b: typeof f) => api<Project>("/projects", { method: "POST", idempotent: true, json: {
    title: b.title, purpose: b.purpose, tags: b.tags.split(",").map((t) => t.trim()).filter(Boolean),
    environments: b.environments.split(",").map((t) => t.trim()).filter(Boolean) } }), [["projects"]], "Project created");
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
  const projects = useApi<Project[]>(["projects", me.data?.org_id], me.data ? "/projects" : null);
  const [open, setOpen] = useState(false);
  return <div className="mx-auto max-w-5xl space-y-6 p-8">
    <div className="flex items-end justify-between">
      <div><div className="eyebrow">{me.data?.orgs.find((o) => o.id === me.data?.org_id)?.name}</div><h1 className="serif text-4xl">Projects</h1>
        <p className="mt-1 text-muted">Each project is a living twin of one architecture: what was designed, what the code says and what is running.</p></div>
      <Button variant="primary" onClick={() => setOpen(true)}><Plus size={16} /> New project</Button>
    </div>
    {projects.isLoading && <Spinner />}<ErrorBox error={projects.error} />
    {projects.data?.length === 0 && <Empty title="No projects yet">Create one, connect a repository and the platform builds the architecture from evidence.</Empty>}
    <div className="grid gap-4 sm:grid-cols-2">{projects.data?.map((p) => <Link key={p.id} to="/projects/$projectId" params={{ projectId: p.id }}>
      <Card className="h-full transition hover:border-muted"><div className="flex items-start justify-between"><h2 className="text-lg font-semibold">{p.title}</h2>{p.my_role && <Badge>{p.my_role.replace("_", " ")}</Badge>}</div>
        <p className="mt-1 line-clamp-2 text-sm text-muted">{p.purpose || "No purpose stated."}</p>
        <div className="mt-3 flex flex-wrap gap-1">{p.tags.map((t) => <Badge key={t} tone="link">{t}</Badge>)}</div></Card></Link>)}</div>
    <NewProjectDialog open={open} onClose={() => setOpen(false)} />
  </div>;
}
