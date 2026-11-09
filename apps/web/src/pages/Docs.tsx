import { FileText, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { Badge, Button, Card, ErrorBox, Select, Spinner, Table } from "@/components/ui";
import { RichMarkdown } from "@/components/RichMarkdown";
import { api, download } from "@/lib/api";
import { takeParam } from "@/lib/deeplink";
import { useAction, useApi } from "@/lib/hooks";
import { DataTable } from "@/components/DataTable";
import { SplitLayout } from "@/components/SplitLayout";
import { modelLabel } from "@/components/CostEstimate";
import { PageAsk } from "@/components/PageAsk";

interface DocEstimateData { sections: number; outline: string[]; model?: string; reasoning_effort?: string; input_tokens?: number;
  output_tokens?: { expected: number; high: number; max: number }; cost_usd: { expected: number | null; high: number | null; max: number | null } }
const money = (v: number | null | undefined) => v == null ? "unpriced" : v < 0.01 ? `$${v.toFixed(4)}` : `$${v.toFixed(2)}`;

/** AI drafts are written section by section: show the planned outline for this project and its pre-flight cost. */
function DocEstimate({ projectId, template }: { projectId: string; template: string }) {
  const e = useApi<DocEstimateData>(["doc-estimate", projectId, template], `/projects/${projectId}/generated-docs/estimate?template=${encodeURIComponent(template)}`);
  if (!e.data || !e.data.sections) return null;
  const d = e.data;
  return <details className="mt-1 text-[11px] text-soft">
    <summary className="cursor-pointer" title={`Input ≈ ${(d.input_tokens ?? 0).toLocaleString()} tokens; output ≈ ${(d.output_tokens?.expected ?? 0).toLocaleString()} expected, ${(d.output_tokens?.max ?? 0).toLocaleString()} max`}>
      {d.sections} sections · ≈ {money(d.cost_usd.expected)} · up to {money(d.cost_usd.high)} · {modelLabel(d.model ?? "")} · {d.reasoning_effort} reasoning</summary>
    <ol className="mt-1 list-decimal pl-5">{d.outline.map((t) => <li key={t}>{t}</li>)}</ol>
  </details>;
}

export function DocsPage({ projectId }: { projectId: string }) {
  const gen = useApi<any[]>(["gen", projectId], `/projects/${projectId}/generated-docs`);
  const types = useApi<{ key: string; title: string; audience: string; description: string; mode: "evidence" | "ai" }[]>(["doc-types"], "/doc-types");
  const [tpl, setTpl] = useState("system-overview");
  const [sel, setSel] = useState<string | null>(null);
  const [diff, setDiff] = useState("");
  const [docSel, setDocSel] = useState<string | null>(() => takeParam("doc"));
  const doc = useApi<any>(["doc", docSel], docSel ? `/projects/${projectId}/documents/${docSel}` : null);
  const cur = useApi<any>(["gendoc", sel], sel ? `/projects/${projectId}/generated-docs/${sel}` : null);
  const fileRef = useRef<HTMLInputElement>(null);
  const curType = types.data?.find((t) => t.key === tpl);
  const titleOf = (k: string) => types.data?.find((t) => t.key === k)?.title ?? k;
  const generate = useAction(() => api<any>(`/projects/${projectId}/generated-docs`, { method: "POST", json: { template: tpl } }), [["gen", projectId]], "Documentation generated");
  const upload = useAction((f: File) => { const fd = new FormData(); fd.append("file", f); return api(`/projects/${projectId}/documents`, { method: "POST", body: fd }); }, [["docs", projectId]], "Document ingested");
  return <SplitLayout storageKey="docs" title="Documentation" sideWidth="xl:w-[420px]" side={(toggle) => <div className="space-y-4">
      <PageAsk projectId={projectId} page="docs" selected={docSel} onPick={(m) => { setDocSel(m.id); setSel(null); }} />
      <Card eyebrow="Generated from evidence" title="Documentation" actions={toggle}>
        <div className="flex gap-2"><Select aria-label="Document type" className="flex-1" value={tpl} onChange={(e) => setTpl(e.target.value)}>
          {(["evidence", "ai"] as const).map((m) => <optgroup key={m} label={m === "evidence" ? "Cited from evidence (deterministic)" : "AI drafts (cited, review required)"}>
            {types.data?.filter((t) => t.mode === m).map((t) => <option key={t.key} value={t.key}>{t.title}</option>)}</optgroup>)}</Select>
          <Button variant="primary" size="sm" disabled={generate.isPending} onClick={async () => { const r = await generate.mutateAsync(undefined as never); setSel(r.id); setDiff(r.diff ?? ""); }}>
            {generate.isPending ? (curType?.mode === "ai" ? "Drafting…" : "Generating…") : "Generate"}</Button></div>
        {curType?.mode === "ai" && <DocEstimate projectId={projectId} template={curType.key} />}
        {curType && <p className="mt-1.5 text-xs text-muted">{curType.mode === "ai" && <Badge tone="link">AI draft</Badge>} {curType.description} <span className="text-soft">· for {curType.audience}</span></p>}
        <ErrorBox error={generate.error} />
        <ul className="mt-3 space-y-1 text-sm">{gen.data?.map((g) => <li key={g.id}><button className={"w-full rounded px-2 py-1 text-left hover:bg-paper-2 " + (sel === g.id ? "bg-paper-2" : "")} onClick={() => { setSel(g.id); setDiff(""); setDocSel(null); }}>
          <FileText size={12} className="mr-1 inline" />{titleOf(g.template)} <span className="text-soft">v{g.version}</span>{" "}
          {g.coverage?.ai_draft ? <Badge tone="link">AI draft</Badge> : <Badge tone={g.coverage?.ratio >= 0.95 ? "ok" : "warn"}>{Math.round((g.coverage?.ratio ?? 0) * 100)}% cited</Badge>}</button></li>)}</ul>
      </Card>
      <Card eyebrow="Ingested" title="Source documents" actions={<><input ref={fileRef} type="file" hidden accept=".md,.txt,.pdf,.docx" onChange={(e) => e.target.files?.[0] && upload.mutate(e.target.files[0])} />
        <Button size="sm" onClick={() => fileRef.current?.click()}><Upload size={14} /> Upload</Button></>}>
        <DataTable<any> queryKey={["docs", projectId]} endpoint={`/projects/${projectId}/documents`} rowKey={(d) => d.id} selected={docSel}
          onRowClick={(d) => { setDocSel(d.id); setSel(null); }} defaultSort="path" defaultDir="asc" searchPlaceholder="Search title or path"
          columns={[{ key: "title", label: "Title", sortable: true, render: (d) => <span className="text-xs">{d.title}</span> },
            { key: "path", label: "Path", sortable: true, render: (d) => <span className="font-mono text-[10px] text-soft" title={d.path}>{d.path}</span> }]} />
      </Card>
    </div>}>
    <Card title={docSel ? doc.data?.title : sel ? `${titleOf(cur.data?.template ?? "")} v${cur.data?.version ?? ""}` : "Preview"} actions={sel && cur.data && <Button size="sm" onClick={() => download(`/projects/${projectId}/generated-docs/${sel}/markdown`, `${cur.data.template}-v${cur.data.version}.md`)}>Export Markdown</Button>}>
      {(cur.isLoading || doc.isLoading) && <Spinner />}
      {diff && <details className="mb-3"><summary className="cursor-pointer text-sm text-link">Changes since previous version</summary><pre className="mt-2 max-h-72 overflow-auto rounded bg-paper-2 p-2 text-xs">{diff}</pre></details>}
      {sel && cur.data && <RichMarkdown>{cur.data.content}</RichMarkdown>}
      {docSel && doc.data && <div><p className="mb-2 font-mono text-xs text-soft">{doc.data.path} · v{doc.data.version} · rev {doc.data.revision?.slice(0, 10)} · {doc.data.parser_version}</p>
        <Table head={["Lines", "Section", "Passage"]}>{doc.data.passages.map((p: any) => <tr key={p.id} className="border-b border-rule align-top"><td className="px-2 py-1 font-mono text-[10px]">{p.line_start}–{p.line_end}</td><td className="px-2 text-xs font-medium">{p.heading}</td><td className="px-2 text-xs whitespace-pre-wrap">{p.text.slice(0, 600)}</td></tr>)}</Table></div>}
      {!sel && !docSel && <p className="text-sm text-soft">Generate a document or open a source document.</p>}
    </Card>
  </SplitLayout>;
}
