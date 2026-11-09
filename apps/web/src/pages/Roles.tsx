import { Check, Copy, FileCode2, Minus, ShieldCheck } from "lucide-react";
import { Fragment, useState } from "react";
import { Badge, Button, Card, ErrorBox, Input, Skeleton, cn } from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { CodeBlock } from "@/components/CodeBlock";

const ROLE_HELP: Record<string, string> = {
  project_owner: "Owns a project: everything in it, including members and deletion.",
  architect: "Designs and approves: edits architecture, ADRs, baselines (not their own).",
  tech_lead: "Edits architecture and datasources; cannot approve.",
  contributor: "Edits content; cannot approve or manage members.",
  reviewer: "Reviews and approves others' work; read-only otherwise.",
  viewer: "Reads everything in the project.",
  org_owner: "Organization owner: every project, admin pages, spend limits.",
  org_admin: "Organization administrator: every project, admin pages, spend limits.",
  member: "Organization member without a project role: sees only projects they belong to.",
};
const KIND_LABEL: Record<string, string> = { project: "Project", connector: "Datasources", architecture: "Architecture", diagram: "Diagrams",
  drift_finding: "Drift", adr: "Decisions (ADRs)", document: "Documents", assistant: "Assistant", org: "Organization" };

export function RolesPage() {
  const [tab, setTab] = useState<"matrix" | "policies">("matrix");
  return <div className="space-y-5 p-8">
    <div><div className="eyebrow">Organization</div><h1 className="serif text-4xl">Roles &amp; permissions</h1>
      <p className="text-muted">Who may do what, decided by Cerbos policies on every request. Users and their organization role live in Keycloak; project roles are set per project (Settings › Members).</p></div>
    <nav role="tablist" className="flex gap-1 border-b border-rule text-sm">{([["matrix", "Effective permissions"], ["policies", "Authorization policies"]] as const).map(([k, l]) =>
      <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
        className={cn("-mb-px border-b-2 px-3 py-2", tab === k ? "border-accent font-medium text-ink" : "border-transparent text-muted hover:text-ink")}>{l}</button>)}</nav>
    {tab === "matrix" ? <Matrix /> : <Policies />}
  </div>;
}

function Matrix() {
  const m = useApi<any>(["access-matrix"], "/admin/access");
  if (m.error) return <ErrorBox error={m.error} />;
  if (!m.data) return <Skeleton className="h-96 !rounded-xl" />;
  const roles: any[] = m.data.roles;
  const groups: [string, string[]][] = [...Object.entries(m.data.resources as Record<string, string[]>), ["org", m.data.org_actions]];
  return <Card eyebrow={m.data.notes.source} title="What each role can do">
    <p className="mb-3 text-xs text-soft">{m.data.notes.author_rule} Each cell is a live decision; nothing is granted by this page.</p>
    <div className="overflow-auto">
      <table className="w-full table-fixed text-xs">
        <thead><tr className="border-b border-rule text-left"><th className="eyebrow w-48 px-2 py-2">Resource · action</th>
          {roles.map((r) => <th key={r.role} className="eyebrow px-1 py-2 text-center" title={ROLE_HELP[r.role]}>{r.role.replace("_", " ")}</th>)}</tr></thead>
        <tbody>{groups.map(([kind, actions]) => <Fragment key={kind}>
          <tr><td colSpan={roles.length + 1} className="bg-paper/70 px-2 py-1 font-medium">{KIND_LABEL[kind] ?? kind}</td></tr>
          {actions.map((a) => <tr key={kind + a} className="border-b border-rule">
            <td className="px-2 py-1 font-mono">{a.replace(/_/g, " ")}</td>
            {roles.map((r) => { const ok = r.decisions[kind]?.[a];
              return <td key={r.role} className="px-1 text-center">{ok ? <span className="inline-flex items-center gap-0.5 text-ok" aria-label="allowed"><Check size={13} /></span>
                : <span className="inline-flex text-soft" aria-label="denied"><Minus size={13} /></span>}</td>; })}
          </tr>)}</Fragment>)}</tbody>
      </table>
    </div>
    <ul className="mt-4 grid gap-1 text-xs text-muted md:grid-cols-2">{roles.map((r) => <li key={r.role}><b className="text-ink">{r.role.replace("_", " ")}</b> — {ROLE_HELP[r.role]}</li>)}</ul>
  </Card>;
}

function Policies() {
  const p = useApi<any>(["policies"], "/admin/policies");
  const [sel, setSel] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [copied, setCopied] = useState(false);
  if (p.error) return <ErrorBox error={p.error} />;
  if (!p.data) return <Skeleton className="h-96 !rounded-xl" />;
  if (!p.data.available) return <Card><p className="text-sm text-soft">Policy files are not mounted into the API container.</p></Card>;
  const files: any[] = p.data.files.filter((f: any) => !q || f.path.includes(q) || f.content.includes(q));
  const cur = p.data.files.find((f: any) => f.path === sel) ?? files[0];
  return <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
    <Card eyebrow={`revision ${p.data.revision}`} title={<span className="flex items-center gap-2"><ShieldCheck size={16} /> Policies {p.data.pdp_healthy ? <Badge tone="ok">PDP healthy</Badge> : <Badge tone="bad">PDP down</Badge>}</span>}>
      <Input placeholder="Search policies" aria-label="Search policies" value={q} onChange={(e) => setQ(e.target.value)} />
      <ul className="mt-2 space-y-0.5 text-sm">{files.map((f) => <li key={f.path}><button onClick={() => setSel(f.path)}
        className={cn("flex w-full items-center gap-2 rounded px-2 py-1 text-left", cur?.path === f.path ? "bg-paper-2 font-medium" : "hover:bg-paper-2")}>
        <FileCode2 size={13} className="shrink-0 text-soft" /><span className="truncate font-mono text-xs">{f.path}</span></button></li>)}</ul>
    </Card>
    {cur && <Card eyebrow={`sha256 ${cur.sha256.slice(0, 16)}… · ${cur.lines} lines · read-only`} title={<span className="font-mono text-base">{cur.path}</span>}
      actions={<Button size="sm" onClick={() => { void navigator.clipboard.writeText(cur.content); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
        {copied ? <Check size={12} /> : <Copy size={12} />} {copied ? "Copied" : "Copy"}</Button>}>
      <CodeBlock src={{ path: cur.path, start: 1, end: cur.lines, language: /\.ya?ml$/.test(cur.path) ? "yaml" : /\.json$/.test(cur.path) ? "json" : "plaintext", text: cur.content }}
        maxHeight={Math.round(window.innerHeight * 0.65)} />
      <p className="mt-2 text-xs text-soft">Policies are code: change them in <code className="font-mono">deploy/cerbos/policies</code>, run <code className="font-mono">make policy-test</code>, and redeploy.</p>
    </Card>}
  </div>;
}
