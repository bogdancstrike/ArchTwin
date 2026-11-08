import { Link, Outlet, useParams } from "@tanstack/react-router";
import { ErrorBox, Spinner } from "@/components/ui";
import { useApi } from "@/lib/hooks";
import type { Project } from "@/lib/types";

const TABS = [["", "Overview"], ["architecture", "Architecture"], ["inventory", "Inventory"], ["drift", "Drift"], ["decisions", "Decisions"],
  ["docs", "Docs"], ["assistant", "Assistant"], ["settings", "Settings"]] as const;

export function ProjectLayout() {
  const { projectId } = useParams({ strict: false }) as { projectId: string };
  const p = useApi<Project>(["project", projectId], `/projects/${projectId}`);
  if (p.isLoading) return <Spinner />;
  if (p.error) return <div className="p-8"><ErrorBox error={p.error} /></div>;
  return <div className="flex h-full flex-col">
    <div className="border-b border-rule bg-card/40 px-6 pt-4">
      <div className="eyebrow">Project · {p.data!.my_role?.replace("_", " ") ?? "member"}</div>
      <h1 className="serif text-3xl">{p.data!.title}</h1>
      <nav className="mt-2 flex gap-1 text-sm" aria-label="Project">{TABS.map(([path, label]) =>
        <Link key={path} to={`/projects/$projectId${path ? "/" + path : ""}`} params={{ projectId }} activeOptions={{ exact: path === "" }}
          className="rounded-t-md border-b-2 border-transparent px-3 py-2 text-muted hover:text-ink" activeProps={{ className: "!border-accent !text-ink font-medium" }}>{label}</Link>)}</nav>
    </div>
    <div className="min-h-0 flex-1 overflow-auto"><Outlet /></div>
  </div>;
}
