import { CodeBlock, type Source } from "@/components/CodeBlock";
import { ErrorBox, Spinner } from "@/components/ui";
import { useApi } from "@/lib/hooks";

interface Obs { id: string; origin: string; source_ref: string; evidence: { path?: string; line_start?: number } }
export interface FlowStep { from: string; to: string; kind: string; edge: string; label: string }

const isCode = (o: Obs) => o.origin !== "runtime" && !!(o.evidence?.path || o.source_ref) && !(o.source_ref || "").includes("://")
  && !!o.evidence?.line_start;

/** The code behind one flow step: the call site from the step's own evidence (a call to another service, a query, a
 *  published message); for steps derived from imports (`handles`, `uses`) the handler / component source instead. */
export function StepCode({ projectId, step }: { projectId: string; step: FlowStep }) {
  const synthetic = ["handles", "uses"].includes(step.kind);
  const obs = useApi<Obs[]>(["obs", projectId, step.edge], synthetic ? null : `/projects/${projectId}/observations?key=${encodeURIComponent(step.edge)}`);
  const site = obs.data?.find(isCode);
  const where = site ? { path: site.evidence.path || site.source_ref, line: site.evidence.line_start! } : null;
  const src = useApi<Source>(["source", projectId, where?.path, where?.line],
    where ? `/projects/${projectId}/source?path=${encodeURIComponent(where.path)}&around=${where.line}` : null);
  const elementKey = synthetic ? (step.kind === "handles" ? step.from : step.to) : (!obs.isLoading && !site ? step.from : null);
  const el = useApi<any>(["element-detail", projectId, elementKey], elementKey ? `/projects/${projectId}/elements/detail?key=${encodeURIComponent(elementKey)}` : null);
  if (obs.isLoading || src.isLoading || el.isLoading) return <Spinner />;
  if (src.error) return <ErrorBox error={src.error} />;
  if (src.data && where) return <CodeBlock src={src.data} highlight={[where.line, where.line]} maxHeight={340} title={`${where.path}:${where.line}`} />;
  const s = el.data?.source as Source | undefined;
  if (s) {
    const a = el.data.attributes ?? {};
    return <div><p className="mb-1 text-[11px] text-soft">{synthetic ? "Derived from the route module's imports — the source of" : "No call site recorded — the source of"} <b>{el.data.name}</b>:</p>
      <CodeBlock src={s} highlight={a.line_start ? [a.line_start, a.line_start] : undefined} maxHeight={340} title={el.data.name} /></div>;
  }
  return <p className="text-xs text-soft">No source code is linked to this step (configuration, runtime or documentation evidence only).</p>;
}
