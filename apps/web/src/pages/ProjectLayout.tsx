import { Link, Outlet, useParams } from "@tanstack/react-router";
import { AlertTriangle, Bot, FileText, LayoutDashboard, Network, Radar, ScrollText, Settings, Workflow } from "lucide-react";
import { Avatar, Badge, ErrorBox, Spinner } from "@/components/ui";
import { FavoriteStar } from "@/components/FavoriteStar";
import { useApi } from "@/lib/hooks";
import type { Project } from "@/lib/types";

const TABS = [["", "Overview", LayoutDashboard], ["architecture", "Architecture", Network], ["flows", "Flows", Workflow], ["drift", "Drift", AlertTriangle],
  ["decisions", "Decisions", ScrollText], ["docs", "Docs", FileText], ["assistant", "Assistant", Bot], ["datasources", "Datasources", Radar],
  ["settings", "Settings", Settings]] as const;

export function ProjectLayout() {
  const { projectId } = useParams({ strict: false }) as { projectId: string };
  const p = useApi<Project>(["project", projectId], `/projects/${projectId}`);
  if (p.isLoading) return <Spinner />;
  if (p.error) return <div className="p-8"><ErrorBox error={p.error} /></div>;
  const d = p.data!;
  return <div className="flex h-full flex-col">
    <div className="border-b border-rule bg-card/60 px-6 pt-4">
      <div className="flex items-center gap-3">
        <Avatar name={d.title} size={40} />
        <div className="min-w-0">
          <div className="flex items-center gap-2"><Link to="/projects" className="eyebrow hover:text-link">Projects</Link><span className="eyebrow">/</span>
            <span className="eyebrow">{d.my_role?.replace("_", " ") ?? "member"}</span></div>
          <div className="flex items-baseline gap-3"><h1 className="serif truncate text-3xl leading-tight">{d.title}</h1>
            <FavoriteStar projectId={d.id} title={d.title} size={18} className="self-center" />
            <span className="hidden gap-1 md:flex">{d.tags.map((t) => <Badge key={t} tone="link">{t}</Badge>)}</span></div>
        </div>
        {d.purpose && <p className="ml-auto hidden max-w-md text-right text-sm text-muted lg:block">{d.purpose}</p>}
      </div>
      <nav className="-mb-px mt-3 flex gap-1 overflow-x-auto text-sm" aria-label="Project">{TABS.map(([path, label, I]) =>
        <Link key={path} to={`/projects/$projectId${path ? "/" + path : ""}`} params={{ projectId }} activeOptions={{ exact: path === "" }}
          className="flex items-center gap-1.5 whitespace-nowrap border-b-2 border-transparent px-3 py-2.5 text-muted transition hover:text-ink"
          activeProps={{ className: "!border-accent !text-ink font-medium" }}><I size={15} className="opacity-70" />{label}</Link>)}</nav>
    </div>
    <div className="min-h-0 flex-1 overflow-auto"><Outlet /></div>
  </div>;
}
