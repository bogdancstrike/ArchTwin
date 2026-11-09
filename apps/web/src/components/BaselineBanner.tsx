import { CheckCircle2, Clock, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { Button, ErrorBox, ago } from "@/components/ui";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";

interface Baseline { id: string; version: number; status: string; author_id: string; proposed_at: string; decided_at?: string | null; note?: string; mine?: boolean; can_approve?: boolean }
interface BaselineStatus {
  state: "approved" | "pending" | "none" | "no_snapshot";
  latest_snapshot: { id: string; version: number; created_at: string; node_count: number } | null;
  approved: Baseline | null; pending: Baseline[]; outdated: boolean; can_propose: boolean; can_self_approve: boolean;
}

/** One place that explains the baseline (the approved, desired architecture drift is measured against) and makes setting,
 *  reviewing or updating it a single action — on the Drift and Architecture pages. */
export function BaselineBanner({ projectId, compact }: { projectId: string; compact?: boolean }) {
  const st = useApi<BaselineStatus>(["baseline-status", projectId], `/projects/${projectId}/baselines/status`);
  const keys = [["baseline-status", projectId], ["baselines", projectId], ["drift", projectId], ["overview", projectId]];
  const [approveNow, setApproveNow] = useState(true);
  const quick = useAction((approve: boolean) => api(`/projects/${projectId}/baselines/from-latest`, { method: "POST", json: { approve_now: approve } }),
    keys, "Baseline saved");
  const decide = useAction((b: { id: string; d: "approve" | "reject" }) => api(`/projects/${projectId}/baselines/${b.id}/${b.d}`, { method: "POST", json: { note: "" } }),
    keys, "Baseline decided");
  const s = st.data;
  if (!s || s.state === "no_snapshot") return null;
  const latest = s.latest_snapshot;
  const tone = s.state === "approved" && !s.outdated ? "border-ok/30 bg-ok/5" : "border-accent/30 bg-accent-tint/40";
  const pending = s.pending[0];
  const setNow = (label: string) => <div className="flex flex-wrap items-center gap-2">
    {s.can_self_approve && <label className="flex items-center gap-1.5 text-xs text-muted" title="Organization admins may approve their own proposal; the exception is audited">
      <input type="checkbox" checked={approveNow} onChange={(e) => setApproveNow(e.target.checked)} /> approve now</label>}
    <Button size="sm" variant="primary" disabled={quick.isPending || !s.can_propose} onClick={() => quick.mutate(s.can_self_approve && approveNow)}
      title={s.can_propose ? "" : "Your role cannot propose baselines"}>{label}</Button>
  </div>;
  return <section aria-label="Baseline" className={`rounded-xl border p-3 ${tone} ${compact ? "text-xs" : "text-sm"}`}>
    <div className="flex flex-wrap items-center gap-3">
      {s.state === "approved" ? <ShieldCheck size={18} className={s.outdated ? "text-accent" : "text-ok"} /> : s.state === "pending" ? <Clock size={18} className="text-accent" /> : <Sparkles size={18} className="text-accent" />}
      <div className="min-w-0 flex-1">
        {s.state === "none" && <><b>No baseline yet.</b> <span className="text-muted">A baseline is the approved architecture; drift is what changes against it (and against your accepted decisions). Start from what ArchTwin discovered (v{latest?.version}, {latest?.node_count} elements) — you can refine it later.</span></>}
        {s.state === "pending" && pending && <><b>Baseline v{pending.version} awaits review</b> <span className="text-muted">· proposed {ago(pending.proposed_at)}{pending.mine ? " by you — another approver (architect, reviewer or owner) accepts it" : ""}.</span></>}
        {s.state === "approved" && s.approved && <><b>Measuring against baseline v{s.approved.version}</b> <span className="text-muted">· approved {ago(s.approved.decided_at)}.</span>
          {s.outdated && latest && <span className="text-muted"> The architecture has moved on to v{latest.version}; update the baseline once the changes are intended.</span>}</>}
      </div>
      {s.state === "none" && setNow("Use current architecture as baseline")}
      {s.state === "pending" && pending && <div className="flex gap-2">
        {pending.can_approve && <><Button size="sm" variant="primary" onClick={() => decide.mutate({ id: pending.id, d: "approve" })}><CheckCircle2 size={14} /> Approve</Button>
          <Button size="sm" variant="ghost" onClick={() => decide.mutate({ id: pending.id, d: "reject" })}>Reject</Button></>}
        {pending.mine && s.can_self_approve && <Button size="sm" onClick={() => decide.mutate({ id: pending.id, d: "approve" })} title="Audited exception to four-eyes">Approve (admin)</Button>}
      </div>}
      {s.state === "approved" && s.outdated && setNow(`Update baseline to v${latest?.version}`)}
    </div>
    <ErrorBox error={quick.error ?? decide.error} />
  </section>;
}
