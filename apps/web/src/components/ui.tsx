import clsx from "clsx";
import { X } from "lucide-react";
import { useEffect, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

export const cn = clsx;

export function Button({ variant = "default", size = "md", className, ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "primary" | "ghost" | "danger"; size?: "sm" | "md" }) {
  return <button {...p} className={cn("inline-flex items-center gap-1.5 rounded-md border font-medium transition disabled:opacity-50 disabled:cursor-not-allowed",
    size === "sm" ? "px-2 py-1 text-xs" : "px-3 py-1.5 text-sm",
    variant === "primary" && "border-ink bg-ink text-paper hover:opacity-90",
    variant === "default" && "border-rule bg-card text-ink hover:border-muted",
    variant === "ghost" && "border-transparent text-muted hover:bg-paper-2 hover:text-ink",
    variant === "danger" && "border-bad/40 text-bad hover:bg-bad/10", className)} />;
}

export function Card({ className, children, title, actions, eyebrow }: { className?: string; children: ReactNode; title?: ReactNode; actions?: ReactNode; eyebrow?: string }) {
  return <section className={cn("rounded-lg border border-rule bg-card", className)}>
    {(title || actions) && <header className="flex items-center justify-between gap-2 border-b border-rule px-4 py-2.5">
      <div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h2 className="font-semibold">{title}</h2></div><div className="flex gap-2">{actions}</div></header>}
    <div className="p-4">{children}</div>
  </section>;
}

const TONES: Record<string, string> = {
  ok: "bg-ok/12 text-ok border-ok/30", warn: "bg-warn/12 text-warn border-warn/30", bad: "bg-bad/12 text-bad border-bad/30",
  accent: "bg-accent-tint text-accent border-accent/40", muted: "bg-paper-2 text-muted border-rule", link: "bg-link/10 text-link border-link/30",
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
  return <input {...p} className={cn("w-full rounded-md border border-rule bg-card px-2.5 py-1.5 text-sm outline-none focus:border-muted", p.className)} />;
}
export function Textarea(p: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...p} className={cn("w-full rounded-md border border-rule bg-card px-2.5 py-1.5 text-sm outline-none focus:border-muted", p.className)} />;
}
export function Select(p: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...p} className={cn("rounded-md border border-rule bg-card px-2 py-1.5 text-sm outline-none focus:border-muted", p.className)} />;
}
export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return <label className="block space-y-1"><span className="text-xs font-medium text-muted">{label}</span>{children}{hint && <span className="block text-xs text-soft">{hint}</span>}</label>;
}

export function Dialog({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  if (!open) return null;
  return <div className="fixed inset-0 z-50 grid place-items-center bg-ink/30 p-4" onMouseDown={onClose}>
    <div role="dialog" aria-modal="true" aria-label={title} onMouseDown={(e) => e.stopPropagation()}
      className={cn("max-h-[90vh] w-full overflow-auto rounded-lg border border-rule bg-card shadow-xl", wide ? "max-w-3xl" : "max-w-lg")}>
      <header className="flex items-center justify-between border-b border-rule px-4 py-3"><h2 className="serif text-xl">{title}</h2>
        <button aria-label="Close" onClick={onClose} className="text-muted hover:text-ink"><X size={18} /></button></header>
      <div className="p-4">{children}</div>
    </div>
  </div>;
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="rounded-lg border border-dashed border-rule p-8 text-center"><p className="serif text-xl">{title}</p>{children && <div className="mt-2 text-sm text-muted">{children}</div>}</div>;
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return <div role="status" className="p-6 text-sm text-soft">{label}</div>;
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const e = error as { message?: string; problem?: { code?: string } };
  return <div role="alert" className="rounded-md border border-bad/30 bg-bad/10 p-3 text-sm text-bad">{e.message ?? String(error)}{e.problem?.code && <span className="ml-2 font-mono text-xs opacity-70">{e.problem.code}</span>}</div>;
}

export function Table({ head, children }: { head: ReactNode[]; children: ReactNode }) {
  return <div className="overflow-auto"><table className="w-full text-sm"><thead><tr className="border-b border-rule text-left">{head.map((h, i) => <th key={i} className="eyebrow px-2 py-2 font-medium">{h}</th>)}</tr></thead><tbody>{children}</tbody></table></div>;
}

export const ago = (iso?: string | null) => {
  if (!iso) return "—";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return `${Math.max(0, Math.round(s))}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
};
