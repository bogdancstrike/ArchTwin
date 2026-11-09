import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { cn } from "@/components/ui";

function useStoredBool(key: string, initial: boolean): [boolean, (v: boolean) => void] {
  const [v, setV] = useState(() => {
    try { const s = localStorage.getItem(key); return s === null ? initial : s === "1"; } catch { return initial; }
  });
  useEffect(() => { try { localStorage.setItem(key, v ? "1" : "0"); } catch { /* storage unavailable */ } }, [key, v]);
  return [v, setV];
}

/** Master/detail page layout whose side pane collapses to a slim rail (state remembered per page). */
export function SplitLayout({ storageKey, title, side, children, sideWidth = "xl:w-[420px]", className }: {
  storageKey: string; title: string; side: (collapseButton: ReactNode) => ReactNode; children: ReactNode; sideWidth?: string; className?: string;
}) {
  const [collapsed, setCollapsed] = useStoredBool(`archtwin.pane.${storageKey}`, false);
  return <div className={cn("flex h-full flex-col gap-4 p-6 xl:flex-row", className)}>
    {collapsed
      ? <aside aria-label={title} className="hidden shrink-0 xl:block">
          <button type="button" onClick={() => setCollapsed(false)} aria-label={`Show ${title}`} title={`Show ${title}`}
            className="flex h-full min-h-40 w-10 flex-col items-center gap-3 rounded-xl border border-rule bg-card py-3 text-muted shadow-card hover:text-ink">
            <PanelLeftOpen size={16} /><span className="eyebrow [writing-mode:vertical-rl]">{title}</span></button>
        </aside>
      : <aside aria-label={title} className={cn("min-w-0 shrink-0", sideWidth)}>
          {side(<button type="button" onClick={() => setCollapsed(true)} aria-label={`Hide ${title}`} title={`Hide ${title}`}
            className="hidden rounded-md p-1 text-soft hover:bg-paper-2 hover:text-ink xl:inline-flex"><PanelLeftClose size={15} /></button>)}
        </aside>}
    <section className="min-w-0 flex-1 space-y-4">{children}</section>
  </div>;
}
