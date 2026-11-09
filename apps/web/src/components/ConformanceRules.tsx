import { Plus, ShieldAlert, Trash2 } from "lucide-react";
import { Button, Input, Select } from "@/components/ui";

export interface Constraint { type: "forbid" | "require" | "only-via" | "technology"; from?: string; to?: string; via?: string; allow?: string;
  relation?: string; element?: string; technology?: string; description?: string }

const HELP: Record<Constraint["type"], string> = {
  forbid: "must not depend on", require: "must depend on", "only-via": "is reached only through", technology: "must use technology",
};

/** Machine-checkable rules of a decision. The drift engine checks them deterministically against the discovered architecture
 *  once the ADR is accepted (elements by key, key prefix ending in *, or name). */
export function ConformanceRules({ value, onChange, readOnly }: { value: Constraint[]; onChange?: (v: Constraint[]) => void; readOnly?: boolean }) {
  const set = (i: number, patch: Partial<Constraint>) => onChange?.(value.map((c, j) => (j === i ? { ...c, ...patch } : c)));
  if (readOnly) {
    if (!value.length) return null;
    return <div className="mt-3 rounded-lg border border-rule bg-paper-2/50 p-3 text-sm">
      <div className="eyebrow mb-1 flex items-center gap-1"><ShieldAlert size={12} /> Conformance rules (checked by drift)</div>
      <ul className="space-y-1">{value.map((c, i) => <li key={i}><code className="text-xs">{describe(c)}</code>{c.description && <span className="text-xs text-soft"> — {c.description}</span>}</li>)}</ul>
    </div>;
  }
  return <div className="space-y-2">
    {value.map((c, i) => <div key={i} className="flex flex-wrap items-center gap-2 rounded-lg border border-rule p-2">
      <Select aria-label="Rule type" value={c.type} onChange={(e) => set(i, { type: e.target.value as Constraint["type"] })}>
        {(Object.keys(HELP) as Constraint["type"][]).map((t) => <option key={t} value={t}>{t}</option>)}</Select>
      {c.type === "technology"
        ? <><Input aria-label="Element" placeholder="element (key or name)" value={c.element ?? ""} onChange={(e) => set(i, { element: e.target.value })} className="w-56" />
            <span className="text-xs text-soft">{HELP[c.type]}</span>
            <Input aria-label="Technology" placeholder="e.g. PostgreSQL" value={c.technology ?? ""} onChange={(e) => set(i, { technology: e.target.value })} className="w-40" /></>
        : <>{c.type !== "only-via" && <Input aria-label="From" placeholder="from (key, prefix*, name)" value={c.from ?? ""} onChange={(e) => set(i, { from: e.target.value })} className="w-52" />}
            <span className="text-xs text-soft">{c.type === "only-via" ? "Anything that reaches" : HELP[c.type]}</span>
            <Input aria-label="To" placeholder="to (key, prefix*, name)" value={c.to ?? ""} onChange={(e) => set(i, { to: e.target.value })} className="w-52" />
            {c.type === "only-via" && <><span className="text-xs text-soft">must go through</span>
              <Input aria-label="Via" placeholder="intermediary" value={c.via ?? ""} onChange={(e) => set(i, { via: e.target.value })} className="w-44" /></>}</>}
      <button type="button" aria-label="Remove rule" className="ml-auto rounded p-1 text-soft hover:text-bad" onClick={() => onChange?.(value.filter((_, j) => j !== i))}><Trash2 size={14} /></button>
    </div>)}
    <Button type="button" size="sm" variant="ghost" onClick={() => onChange?.([...value, { type: "forbid", from: "", to: "" }])}><Plus size={13} /> Add conformance rule</Button>
    <p className="text-xs text-soft">Example: only-via <code>external:openai</code> through <code>container:app/llm-gateway</code> — any service calling the provider directly becomes a drift finding citing this ADR.</p>
  </div>;
}

export function describe(c: Constraint): string {
  if (c.type === "technology") return `${c.element} must use ${c.technology}`;
  if (c.type === "only-via") return `${c.to} only through ${c.via}`;
  return `${c.from || "*"} ${c.type === "forbid" ? "must not depend on" : "must depend on"} ${c.to}${c.relation && c.relation !== "any" ? ` (${c.relation})` : ""}`;
}
