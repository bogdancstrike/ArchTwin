import { createRootRoute, createRoute, createRouter, redirect, useParams } from "@tanstack/react-router";
import type { ReactElement } from "react";
import { AppShell } from "@/components/AppShell";
import { AuditPage, FlagsPage } from "@/pages/Admin";
import { RolesPage } from "@/pages/Roles";
import { SystemPage } from "@/pages/System";
import { UsagePage } from "@/pages/Usage";
import { ArchitecturePage } from "@/pages/Architecture";
import { AssistantPage } from "@/pages/Assistant";
import { DecisionsPage } from "@/pages/Decisions";
import { DocsPage } from "@/pages/Docs";
import { DriftPage } from "@/pages/Drift";
import { HomePage } from "@/pages/Home";
import { InventoryPage } from "@/pages/Inventory";
import { OverviewPage } from "@/pages/Overview";
import { ProjectLayout } from "@/pages/ProjectLayout";
import { ProjectsPage } from "@/pages/Projects";
import { SettingsPage } from "@/pages/Settings";

function usePid() { return (useParams({ strict: false }) as { projectId: string }).projectId; }
const root = createRootRoute({ component: AppShell });
const index = createRoute({ getParentRoute: () => root, path: "/", beforeLoad: () => { throw redirect({ to: "/home" }); } });
const home = createRoute({ getParentRoute: () => root, path: "/home", component: HomePage });
const projectsList = createRoute({ getParentRoute: () => root, path: "/projects", component: ProjectsPage });
const flags = createRoute({ getParentRoute: () => root, path: "/admin/flags", component: FlagsPage });
const audit = createRoute({ getParentRoute: () => root, path: "/admin/audit", component: AuditPage });
const system = createRoute({ getParentRoute: () => root, path: "/admin/system", component: SystemPage });
const roles = createRoute({ getParentRoute: () => root, path: "/admin/roles", component: RolesPage });
const usagePage = createRoute({ getParentRoute: () => root, path: "/usage", component: UsagePage });
const project = createRoute({ getParentRoute: () => root, path: "/projects/$projectId", component: ProjectLayout });
function sub(path: string, C: (p: { projectId: string }) => ReactElement) {
  return createRoute({ getParentRoute: () => project, path, component: function Sub() { return <C projectId={usePid()} />; } });
}
const architecture = createRoute({ getParentRoute: () => project, path: "architecture", component: function Arch() { return <ArchitecturePage projectId={usePid()} />; },
  validateSearch: (s: Record<string, unknown>) => ({ view: s.view as string | undefined, snapshot: s.snapshot as string | undefined,
    compare: s.compare as string | undefined, full: s.full ? true : undefined, deps: s.deps ? true : undefined, table: s.table ? true : undefined }) });

const tree = root.addChildren([index, home, projectsList, flags, audit, system, roles, usagePage, project.addChildren([sub("/", OverviewPage), architecture, sub("datasources", InventoryPage),
  sub("inventory", InventoryPage) /* old bookmark path */,
  sub("drift", DriftPage), sub("drift/$findingId", DriftPage), sub("decisions", DecisionsPage), sub("docs", DocsPage), sub("assistant", AssistantPage),
  sub("settings", SettingsPage)])]);
export const router = createRouter({ routeTree: tree, defaultPreload: "intent" });
