import { Activity, AlertTriangle, Coins, Download, Gauge, Hash, Users, Zap } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, ErrorBox, Select, Skeleton, StatTile, Table, cn } from "@/components/ui";
import { CapBar, StackedBars, compact, usd } from "@/components/charts";
import { getToken } from "@/lib/auth";
import { useApi } from "@/lib/hooks";

const OPS: Record<string, string> = { question_answering: "Data questions", general_chat: "General chat", integration_design: "Integration design",
  adrs: "ADR drafting", architecture_draft: "Architecture drafts", text_extend: "Extend with AI", architecture_review: "Reviews" };
const GROUPS = [["model", "Model"], ["operation", "Operation"], ["project", "Project"], ["user", "User"], ["status", "Status"]] as const;

function Delta({ cur, prev, invert }: { cur: number; prev: number; invert?: boolean }) {
  if (!prev && !cur) return <span className="text-soft">no activity</span>;
  if (!prev) return <span className="text-soft">new this period</span>;
  const d = (cur - prev) / prev;
  const up = d >= 0;
  const good = invert ? !up : up;
  return <span className={good ? "text-ok" : "text-bad"} aria-label={`${up ? "up" : "down"} ${Math.abs(Math.round(d * 100))} percent versus the previous period`}>
    {up ? "▲" : "▼"} {Math.abs(Math.round(d * 100))}% <span className="text-soft">vs previous</span></span>;
}

export function UsagePage() {
  const perms = useApi<Record<string, boolean>>(["me-perms"], "/me/permissions");
  const canAll = !!perms.data?.view_usage_all;
  const [scope, setScope] = useState<"me" | "all">("me");
  const [days, setDays] = useState(30);
  const [group, setGroup] = useState<string>("model");
  const q = `days=${days}&scope=${scope}`;
  const ov = useApi<any>(["usage-ov", q], `/usage/overview?${q}`);
  const br = useApi<any>(["usage-br", q, group], `/usage/breakdown?${q}&group_by=${group}&granularity=day`);
  const k = ov.data?.kpis, p = ov.data?.previous;
  const opsKeys: string[] = ov.data ? [...new Set<string>(ov.data.daily.map((d: any) => d.operation))]
    .sort((a, b) => ov.data.daily.filter((d: any) => d.operation === b).reduce((s: number, d: any) => s + d.cost_usd, 0)
      - ov.data.daily.filter((d: any) => d.operation === a).reduce((s: number, d: any) => s + d.cost_usd, 0)) : [];
  const download = async () => {
    const r = await fetch(`/api/v1/usage/export?${q}`, { headers: { Authorization: `Bearer ${getToken()}` } });
    const url = URL.createObjectURL(await r.blob());
    const a = document.createElement("a"); a.href = url; a.download = `archtwin-ai-usage-${days}d.csv`; a.click(); URL.revokeObjectURL(url);
  };
  return <div className="space-y-6 p-8">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div><div className="eyebrow">AI cost control</div><h1 className="serif text-4xl">Usage &amp; costs</h1>
        <p className="text-muted">Every model call through LiteLLM is recorded with tokens and cost (LiteLLM’s figure, checked against the price table).</p></div>
      <div className="flex flex-wrap items-center gap-2">
        {canAll && <div role="radiogroup" aria-label="Whose usage" className="flex rounded-lg border border-rule bg-card p-0.5 text-sm">
          {(["me", "all"] as const).map((s) => <button key={s} role="radio" aria-checked={scope === s} onClick={() => setScope(s)}
            className={cn("rounded-md px-3 py-1", scope === s ? "bg-ink text-paper" : "text-muted hover:text-ink")}>{s === "me" ? "You" : "Whole organization"}</button>)}</div>}
        <Select aria-label="Period" value={days} onChange={(e) => setDays(Number(e.target.value))}>
          {[7, 30, 90, 365].map((d) => <option key={d} value={d}>Last {d} days</option>)}</Select>
        <Button onClick={download}><Download size={14} /> Export CSV</Button>
      </div>
    </div>
    <ErrorBox error={ov.error} />
    {!k ? <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">{[0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-28 !rounded-xl" />)}</div> :
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        <StatTile label="Estimated spend" value={usd(k.cost_usd)} icon={<Coins size={16} />} hint={<Delta cur={k.cost_usd} prev={p.cost_usd} invert />} />
        <StatTile label="Tokens" value={compact(k.tokens)} tone="link" icon={<Hash size={16} />} hint={<Delta cur={k.tokens} prev={p.tokens} invert />} />
        <StatTile label="Calls" value={k.calls.toLocaleString()} tone="link" icon={<Zap size={16} />} hint={<Delta cur={k.calls} prev={p.calls} />} />
        <StatTile label="Errors" value={k.errors} tone={k.errors ? "bad" : "ok"} icon={<AlertTriangle size={16} />} hint={k.calls ? `${((k.errors / k.calls) * 100).toFixed(1)}% of calls` : "—"} />
        <StatTile label="Cache hit" value={`${Math.round(k.cache_hit * 100)}%`} tone="ok" icon={<Gauge size={16} />} hint="cached input tokens (cheaper)" />
        <StatTile label={scope === "all" ? "Active users" : "Avg latency"} value={scope === "all" ? k.active_users : `${(k.avg_latency_ms / 1000).toFixed(1)}s`}
          tone="link" icon={scope === "all" ? <Users size={16} /> : <Activity size={16} />} hint={scope === "all" ? <Delta cur={k.active_users} prev={p.active_users} /> : "per call"} />
      </section>}
    <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
      <Card eyebrow={`Last ${days} days`} title="Daily estimated spend by operation">
        {ov.data ? <StackedBars ariaLabel="Daily estimated spend by operation" rows={ov.data.daily.map((d: any) => ({ x: d.day, key: d.operation, value: d.cost_usd }))}
          keys={opsKeys} labels={OPS} format={usd} /> : <Skeleton className="h-56" />}
      </Card>
      <Card eyebrow={`This month · ${ov.data ? usd(ov.data.month.cost_usd) : "…"} · ${ov.data ? compact(ov.data.month.tokens) : "…"} tokens`} title="Monthly limits">
        {!ov.data ? <Skeleton className="h-32" /> : ov.data.limits.length === 0 ? <p className="text-sm text-soft">No monthly limit applies{scope === "me" ? " to you" : ""}. {perms.data?.manage_spend_limits &&
          <a className="text-link" href="/admin/system?tab=spend">Set limits in System › Spend limits</a>}</p> :
          <ul className="space-y-3">{ov.data.limits.map((l: any) => <li key={l.subject}><div className="mb-1 flex justify-between text-sm"><span><Badge>{l.kind}</Badge> {l.label}</span>
            <span className="tabular-nums text-muted">{usd(l.spent_usd)} / {usd(l.monthly_usd)}</span></div><CapBar pct={l.pct} warnAt={ov.data.warn_at} /></li>)}</ul>}
      </Card>
    </div>
    <Card eyebrow="Breakdown" title="Where the money goes" actions={<div role="radiogroup" aria-label="Group by" className="flex flex-wrap rounded-lg border border-rule bg-card p-0.5 text-xs">
      {GROUPS.filter(([g]) => g !== "user" || scope === "all").map(([g, l]) => <button key={g} role="radio" aria-checked={group === g} onClick={() => setGroup(g)}
        className={cn("rounded-md px-2.5 py-1", group === g ? "bg-ink text-paper" : "text-muted hover:text-ink")}>{l}</button>)}</div>}>
      <ErrorBox error={br.error} />
      {br.data && <StackedBars ariaLabel={`Daily spend by ${group}`} rows={br.data.series.map((s: any) => ({ x: s.bucket, key: s.key, value: s.cost_usd }))}
        keys={br.data.totals.map((t: any) => t.key)} labels={Object.fromEntries(br.data.totals.map((t: any) => [t.key, group === "operation" ? OPS[t.label] ?? t.label : t.label]))}
        format={usd} height={180} />}
      <div className="mt-4"><Table head={[GROUPS.find(([g]) => g === group)?.[1] ?? "Key", "Spend", "Input tokens", "Output tokens", "Cached", "Calls", "Errors", "Avg latency"]}>
        {br.data?.totals.map((t: any) => <tr key={t.key} className="border-b border-rule"><td className="px-2 py-1.5">{group === "operation" ? OPS[t.label] ?? t.label : t.label}</td>
          <td className="num px-2">{usd(t.cost_usd)}</td><td className="num px-2">{compact(t.input_tokens)}</td><td className="num px-2">{compact(t.output_tokens)}</td>
          <td className="num px-2">{compact(t.cached_input_tokens)}</td><td className="num px-2">{t.calls}</td><td className="num px-2">{t.errors}</td>
          <td className="num px-2">{(t.avg_latency_ms / 1000).toFixed(1)}s</td></tr>)}</Table>
        {br.data?.totals.length === 0 && <p className="py-6 text-center text-sm text-soft">No AI calls in this period.</p>}</div>
    </Card>
    <Card eyebrow="Pricing" title="Token prices (USD per 1M tokens)">
      <p className="mb-2 text-sm text-muted">Cost per call = uncached input × input + cached input × cached + output × output. LiteLLM’s reported cost is used when it is within 0.5–2.5× of this table;
        unpriced models use LiteLLM’s figure. Override or add prices with <code className="font-mono text-xs">ARCHTWIN_LLM_PRICES</code>.</p>
      <Table head={["Model", "Input", "Cached input", "Output", "Source"]}>{ov.data?.prices.map((m: any) => <tr key={m.model} className="border-b border-rule">
        <td className="px-2 py-1.5 font-mono text-xs">{m.model}</td><td className="num px-2">{m.priced ? `$${m.input_per_1m}` : "—"}</td>
        <td className="num px-2">{m.priced ? `$${m.cached_input_per_1m}` : "—"}</td><td className="num px-2">{m.priced ? `$${m.output_per_1m}` : "—"}</td>
        <td className="px-2">{m.priced ? <Badge tone="ok">{m.source}</Badge> : <Badge tone="warn">unpriced · {m.source}</Badge>}</td></tr>)}</Table>
    </Card>
  </div>;
}
