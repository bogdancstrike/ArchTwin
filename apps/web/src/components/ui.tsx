import clsx from "clsx";
import { X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type ButtonHTMLAttributes, type PointerEvent as ReactPointerEvent, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

export const cn = clsx;

export function Button({ variant = "default", size = "md", className, ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "primary" | "ghost" | "danger"; size?: "sm" | "md" }) {
  return <button {...p} className={cn("inline-flex items-center gap-1.5 rounded-lg border font-medium shadow-card transition active:translate-y-px disabled:opacity-50 disabled:cursor-not-allowed",
    size === "sm" ? "px-2 py-1 text-xs" : "px-3 py-1.5 text-sm",
    variant === "primary" && "border-ink bg-ink text-paper hover:bg-ink/90",
    variant === "default" && "border-rule bg-card text-ink hover:border-muted",
    variant === "ghost" && "!shadow-none border-transparent text-muted hover:bg-paper-2 hover:text-ink",
    variant === "danger" && "border-bad/40 text-bad hover:bg-bad/10", className)} />;
}

export function Card({ className, children, title, actions, eyebrow }: { className?: string; children: ReactNode; title?: ReactNode; actions?: ReactNode; eyebrow?: string }) {
  return <section className={cn("rounded-xl border border-rule bg-card shadow-card", className)}>
    {(title || actions) && <header className="flex items-center justify-between gap-2 px-4 pb-1 pt-3.5">
      <div>{eyebrow && <div className="eyebrow mb-0.5">{eyebrow}</div>}<h2 className="text-[15px] font-semibold tracking-tight">{title}</h2></div><div className="flex items-center gap-2">{actions}</div></header>}
    <div className="p-4">{children}</div>
  </section>;
}

const TONES: Record<string, string> = {
  ok: "bg-ok/12 text-ok border-ok/30", warn: "bg-warn/12 text-warn-ink border-warn/30", bad: "bg-bad/12 text-bad border-bad/30",
  accent: "bg-accent-tint text-accent-ink border-accent/40", muted: "bg-paper-2 text-muted border-rule", link: "bg-link/10 text-link border-link/30",
};
export function Badge({ tone = "muted", children, title }: { tone?: keyof typeof TONES | string; children: ReactNode; title?: string }) {
  return <span title={title} className={cn("inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider", TONES[tone] ?? TONES.muted)}>{children}</span>;
}

export function FreshnessBadge({ f }: { f?: { status: string; reason?: string } }) {
  const s = f?.status ?? "unknown";
  return <Badge tone={{ current: "ok", stale: "warn", incomplete: "warn", unknown: "muted" }[s]} title={f?.reason}>{s}</Badge>;
}

export function OriginBadges({ origins }: { origins: string[] }) {
  const tone: Record<string, string> = { static: "link", runtime: "ok", manual: "accent", desired: "accent", inferred: "muted" };
  return <span className="inline-flex flex-wrap gap-1">{origins.map((o) => <Badge key={o} tone={tone[o] ?? "muted"}>{o}</Badge>)}</span>;
}

export function Input(p: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...p} className={cn("w-full rounded-lg border border-rule bg-card px-2.5 py-1.5 text-sm outline-none transition focus:border-muted focus:ring-2 focus:ring-accent/15", p.className)} />;
}
export function Textarea(p: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...p} className={cn("w-full rounded-lg border border-rule bg-card px-2.5 py-1.5 text-sm outline-none transition focus:border-muted focus:ring-2 focus:ring-accent/15", p.className)} />;
}
export function Select(p: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...p} className={cn("rounded-lg border border-rule bg-card px-2 py-1.5 text-sm outline-none transition focus:border-muted focus:ring-2 focus:ring-accent/15", p.className)} />;
}
export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return <label className="block space-y-1"><span className="text-xs font-medium text-muted">{label}</span>{children}{hint && <span className="block text-xs text-soft">{hint}</span>}</label>;
}

export function Dialog({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => {            // stacked dialogs: Escape closes only the top-most one
      const all = document.querySelectorAll('[role="dialog"]');
      if (e.key === "Escape" && all[all.length - 1] === ref.current) onClose();
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  if (!open) return null;
  return <div className="fixed inset-0 z-50 grid place-items-center bg-ink/35 p-4 backdrop-blur-[2px]" onMouseDown={onClose}>
    <div ref={ref} role="dialog" aria-modal="true" aria-label={title} onMouseDown={(e) => e.stopPropagation()}
      className={cn("fade-up max-h-[90vh] w-full overflow-auto rounded-xl border border-rule bg-card shadow-lift", wide ? "max-w-3xl" : "max-w-lg")}>
      <header className="flex items-center justify-between border-b border-rule px-4 py-3"><h2 className="serif text-xl">{title}</h2>
        <button aria-label="Close" onClick={onClose} className="text-muted hover:text-ink"><X size={18} /></button></header>
      <div className="p-4">{children}</div>
    </div>
  </div>;
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="rounded-xl border border-dashed border-rule bg-card/50 p-10 text-center"><p className="serif text-2xl">{title}</p>{children && <div className="mt-2 text-sm text-muted">{children}</div>}</div>;
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return <div role="status" aria-label={label} className="space-y-3 p-6"><span className="sr-only">{label}</span>
    <div className="skeleton h-5 w-48" /><div className="skeleton h-4 w-full max-w-xl" /><div className="skeleton h-4 w-full max-w-md" /></div>;
}

export function Skeleton({ className }: { className?: string }) { return <div aria-hidden className={cn("skeleton", className)} />; }

// [hue, AA-contrast ink on a light tint of that hue]
const HUES: [string, string][] = [["#eb6c36", "#a8431a"], ["#2e5aa8", "#234a8f"], ["#3c7a55", "#2c5e41"], ["#8a5cc2", "#64399c"],
  ["#b8822a", "#7d5410"], ["#c2477a", "#9a2c5a"], ["#2f8f9d", "#1c6470"], ["#5c6579", "#444c5e"]];
function pick(s: string) { let h = 0; for (const ch of s) h = (h * 31 + ch.charCodeAt(0)) >>> 0; return HUES[h % HUES.length]; }
export function hueFor(s: string) { return pick(s)[0]; }

export function Avatar({ name, size = 28, className, onDark }: { name: string; size?: number; className?: string; onDark?: boolean }) {
  const initials = name.split(/[\s_-]+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("") || "?";
  const [c, ink] = pick(name);
  return <span aria-hidden className={cn("avatar inline-grid shrink-0 place-items-center rounded-lg font-semibold", onDark && "avatar-dark", className)}
    style={{ width: size, height: size, fontSize: size * 0.4, ["--av" as string]: c, ["--av-ink" as string]: ink }}>{initials}</span>;
}

export function StatTile({ label, value, hint, tone, icon, to }: { label: string; value: ReactNode; hint?: ReactNode; tone?: "accent" | "ok" | "warn" | "bad" | "link"; icon?: ReactNode; to?: string }) {
  const color = { accent: "text-accent", ok: "text-ok", warn: "text-warn", bad: "text-bad", link: "text-link" }[tone ?? "accent"];
  const body = <div className="group relative h-full overflow-hidden rounded-xl border border-rule bg-card p-4 shadow-card transition hover:shadow-lift">
    <div className="flex items-center justify-between"><span className="eyebrow">{label}</span>{icon && <span className={cn("opacity-70", tone ? color : "text-soft")}>{icon}</span>}</div>
    <div className={cn("num mt-2 font-serif text-4xl leading-none", tone ? color : "text-ink")}>{value}</div>
    {hint && <div className="mt-1.5 text-xs text-muted">{hint}</div>}
  </div>;
  return to ? <a href={to} className="block">{body}</a> : body;
}

export function SeverityBar({ counts }: { counts: Record<string, number> }) {
  const order = [["critical", "bg-bad"], ["high", "bg-accent"], ["medium", "bg-warn"], ["low", "bg-link/60"]] as const;
  const total = order.reduce((a, [k]) => a + (counts[k] ?? 0), 0);
  if (!total) return <div className="h-1.5 rounded-full bg-ok/25" title="No open drift" />;
  return <div className="flex h-1.5 overflow-hidden rounded-full bg-paper-2" title={order.map(([k]) => `${k}: ${counts[k] ?? 0}`).join(" · ")}>
    {order.map(([k, c]) => (counts[k] ?? 0) > 0 && <div key={k} className={c} style={{ width: `${((counts[k] ?? 0) / total) * 100}%` }} />)}</div>;
}

export function StatusDot({ status, className }: { status: string; className?: string }) {
  const c = { current: "bg-ok", complete: "bg-ok", approved: "bg-ok", accepted: "bg-ok", stale: "bg-warn", incomplete: "bg-warn", partial: "bg-warn",
    proposed: "bg-link", running: "bg-link", queued: "bg-link", failed: "bg-bad", rejected: "bg-bad", critical: "bg-bad", high: "bg-accent",
    medium: "bg-warn", low: "bg-link" }[status] ?? "bg-soft/60";
  return <span aria-hidden className={cn("inline-block h-2 w-2 shrink-0 rounded-full", c, className)} />;
}

export function PageHeader({ eyebrow, title, children, actions }: { eyebrow?: ReactNode; title: ReactNode; children?: ReactNode; actions?: ReactNode }) {
  return <div className="flex flex-wrap items-end justify-between gap-4">
    <div className="min-w-0">{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h1 className="serif mt-0.5 text-[2.6rem] leading-[1.05]">{title}</h1>
      {children && <p className="mt-1.5 max-w-2xl text-muted">{children}</p>}</div>
    {actions && <div className="flex items-center gap-2">{actions}</div>}
  </div>;
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const e = error as { message?: string; problem?: { code?: string } };
  return <div role="alert" className="rounded-md border border-bad/30 bg-bad/10 p-3 text-sm text-bad">{e.message ?? String(error)}{e.problem?.code && <span className="ml-2 font-mono text-xs opacity-70">{e.problem.code}</span>}</div>;
}

/** Columns start split by `weights` (equal by default) and can be resized by dragging the right edge of a header cell
 *  (keyboard: ←/→ on the handle). */
export function Table({ head, children, weights }: { head: ReactNode[]; children: ReactNode; weights?: number[] }) {
  const [widths, setWidths] = useState<number[] | null>(null);       // percentages; null = initial split
  const ref = useRef<HTMLTableElement>(null);
  const n = head.length;
  const wsum = weights && weights.length === n ? weights.reduce((a, b) => a + b, 0) : 0;
  const w = widths && widths.length === n ? widths
    : wsum > 0 ? weights!.map((x) => (x / wsum) * 100) : Array.from({ length: n }, () => 100 / n);
  useLayoutEffect(() => {          // Chrome does not always re-run fixed table layout on a cell width change: force it (pre-paint)
    const t = ref.current;
    if (!t || !widths) return;
    t.style.display = "none";
    void t.offsetWidth;
    t.style.display = "";
  }, [widths]);
  const resize = (i: number, deltaPct: number) => {
    if (i >= n - 1) return;
    setWidths((prev) => {                         // functional: successive pointer moves accumulate
      const next = prev && prev.length === n ? [...prev] : Array.from({ length: n }, () => 100 / n);
      const d = Math.max(-(next[i] - 5), Math.min(next[i + 1] - 5, deltaPct));     // keep every column >= 5 %
      next[i] += d; next[i + 1] -= d;
      return next;
    });
  };
  const start = (i: number) => (e: ReactPointerEvent) => {
    e.preventDefault();
    const total = ref.current?.getBoundingClientRect().width || 1;
    let last = e.clientX;
    const move = (ev: PointerEvent) => { resize(i, ((ev.clientX - last) / total) * 100); last = ev.clientX; };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };
  return <div className="overflow-auto"><table ref={ref} className="w-full table-fixed text-sm">
    <thead><tr className="border-b border-rule text-left">{head.map((h, i) => <th key={i} style={{ width: `${w[i]}%` }} className="eyebrow relative truncate px-2 py-2 font-medium">{h}
      {i < n - 1 && <span role="separator" aria-orientation="vertical" aria-label="Resize column" tabIndex={0} onPointerDown={start(i)}
        onKeyDown={(e) => { if (e.key === "ArrowLeft") resize(i, -2); if (e.key === "ArrowRight") resize(i, 2); }}
        onDoubleClick={() => setWidths(null)}
        className="absolute right-0 top-0 h-full w-1.5 cursor-col-resize select-none hover:bg-accent/40 focus:bg-accent/40 focus:outline-none" />}</th>)}</tr></thead>
    <tbody className="[&_td]:break-words">{children}</tbody></table></div>;
}

export const ago = (iso?: string | null) => {
  if (!iso) return "—";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return `${Math.max(0, Math.round(s))}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
};
