import { useQuery } from "@tanstack/react-query";
import { Coins } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge, Table, cn } from "@/components/ui";
import { usd } from "@/components/charts";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

export interface Estimate {
  operation: string; purpose: string; model: string; reasoning_effort: string; max_output_tokens: number; overridden: boolean;
  input_tokens: number; output_tokens: { expected: number; high: number; max: number };
  cost_usd: { expected: number | null; high: number | null; max: number | null }; priced: boolean;
  basis: { input: string; output: string };
}

const MODEL_LABEL: Record<string, string> = { "gpt-6-luna": "Luna", "gpt-6-terra": "Terra" };
export const modelLabel = (m: string) => MODEL_LABEL[m] ?? m;
const money = (v: number | null) => v === null ? "unpriced" : v < 0.0001 ? "<$0.0001" : v < 0.01 ? `$${v.toFixed(4)}` : usd(v);

/** Pre-flight estimate of one AI call (no model is called): debounced on the text the user is writing. */
export function useEstimate(operation: string, text = "", model?: string | null, enabled = true) {
  const [t, setT] = useState(text);
  useEffect(() => { const h = setTimeout(() => setT(text), 600); return () => clearTimeout(h); }, [text]);
  return useQuery({
    queryKey: ["ai-estimate", operation, model ?? "", t.length > 0 ? t.slice(0, 4000) : ""],
    queryFn: () => api<Estimate>("/ai/estimate", { method: "POST", json: { operation, model: model || null, text: t } }),
    enabled, staleTime: 60_000, placeholderData: (p) => p,
  });
}

/** "≈ $0.002 · up to $0.006 · Terra · high reasoning", with the token breakdown and basis on hover. */
export function CostEstimate({ operation, text, model, className }: { operation: string; text?: string; model?: string | null; className?: string }) {
  const e = useEstimate(operation, text, model).data;
  if (!e) return null;
  const tip = `${e.purpose}\nModel ${e.model} · ${e.reasoning_effort} reasoning${e.overridden ? " (your choice)" : ""}\n`
    + `Input ≈ ${e.input_tokens.toLocaleString()} tokens (${e.basis.input})\nOutput ≈ ${e.output_tokens.expected.toLocaleString()} expected, `
    + `${e.output_tokens.high.toLocaleString()} high, ${e.output_tokens.max.toLocaleString()} max incl. reasoning (${e.basis.output})\n`
    + `Cost: ${money(e.cost_usd.expected)} expected · ${money(e.cost_usd.high)} high · ${money(e.cost_usd.max)} worst case`;
  return <span className={cn("inline-flex items-center gap-1 text-[11px] text-soft", className)} title={tip} aria-label={`Estimated cost: ${tip}`}>
    <Coins size={11} aria-hidden />≈ {money(e.cost_usd.expected)}{e.cost_usd.high !== null && <> · up to {money(e.cost_usd.high)}</>}
    <span className="text-muted">· {modelLabel(e.model)} · {e.reasoning_effort}</span></span>;
}

interface RoutingRow {
  operation: string; purpose: string; model: string; configured_model: string; reasoning_effort: string; max_output_tokens: number; user_selectable: boolean;
  price: { input_per_1m: number; cached_input_per_1m: number; output_per_1m: number } | null;
  estimate: { expected: number | null; high: number | null };
  history: { calls: number; avg_input_tokens: number; avg_output_tokens: number; avg_reasoning_tokens: number; avg_cost_usd: number; cache_hit_ratio: number };
}
const EFFORT_TONE: Record<string, string> = { high: "accent", medium: "link", low: "muted", minimal: "muted" };

/** Usage page: which model and reasoning effort each AI task runs on, and what one call typically costs. */
export function ModelRouting() {
  const r = useApi<{ tasks: RoutingRow[]; blocked_models: string[]; history_days: number }>(["ai-routing"], "/ai/routing");
  return <section className="rounded-xl border border-rule bg-card p-4 shadow-card">
    <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
      <div><div className="eyebrow">Cost control</div><h3 className="text-lg font-semibold">Model routing per task</h3></div>
      {r.data && <span className="text-xs text-soft">Blocked: {r.data.blocked_models.map((m) => <code key={m} className="ml-1 font-mono">{m}</code>)}</span>}
    </div>
    <p className="mb-2 text-sm text-muted">Deep multi-hop work (architecture, flows, drift, integration design) runs on Terra with high reasoning; grounded answers on Luna/medium;
      rewriting and page search on Luna/low. Evidence is trimmed to each task's token budget. Estimates learn from the last {r.data?.history_days ?? 30} days of calls.</p>
    <Table head={["Task", "Model", "Reasoning", "Output cap", "Est. per call", "Avg actual", "Calls", "Avg tokens in / out"]}>{r.data?.tasks.map((t) =>
      <tr key={t.operation} className="border-b border-rule align-top">
        <td className="px-2 py-1.5"><div className="font-mono text-xs">{t.operation}</div><div className="text-xs text-soft">{t.purpose}</div></td>
        <td className="px-2"><span className="font-medium">{modelLabel(t.model)}</span>{t.user_selectable && <div className="text-[10px] text-soft">user may pick</div>}
          {t.model !== t.configured_model && <div className="text-[10px] text-warn">fallback from {modelLabel(t.configured_model)}</div>}</td>
        <td className="px-2"><Badge tone={EFFORT_TONE[t.reasoning_effort]}>{t.reasoning_effort}</Badge></td>
        <td className="num px-2">{t.max_output_tokens.toLocaleString()}</td>
        <td className="num px-2">{money(t.estimate.expected)}<div className="text-[10px] text-soft">up to {money(t.estimate.high)}</div></td>
        <td className="num px-2">{t.history.calls ? money(t.history.avg_cost_usd) : "—"}</td>
        <td className="num px-2">{t.history.calls}</td>
        <td className="num px-2">{t.history.calls ? `${t.history.avg_input_tokens.toLocaleString()} / ${t.history.avg_output_tokens.toLocaleString()}` : "—"}
          {t.history.avg_reasoning_tokens > 0 && <div className="text-[10px] text-soft">{t.history.avg_reasoning_tokens.toLocaleString()} reasoning</div>}</td>
      </tr>)}</Table>
    {r.data?.tasks.some((t) => !t.price) && <p className="mt-2 text-xs text-soft">Unpriced models (no list price configured) are estimated from the cost LiteLLM reported for past calls;
      set <code className="font-mono">ARCHTWIN_LLM_PRICES</code> for exact pre-flight estimates.</p>}
  </section>;
}
