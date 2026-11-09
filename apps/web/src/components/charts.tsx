/** Small, dependency-free SVG charts following the dataviz method: categorical hues in fixed order (never cycled; extra
 * series fold into "Other"), thin marks with a 2px surface gap, recessive axes, a legend for >= 2 series, a hover tooltip
 * per mark, and a table view next to every chart (contrast relief). Status colors are reserved and ship with a label. */
import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/components/ui";

export const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)", "var(--series-5)", "var(--series-6)"];
export const OTHER = "var(--series-other)";

/** Stable entity -> color: the slot is fixed by the order of `keys` (sorted by total, desc, by the caller). */
export function colorMap(keys: string[]): Record<string, string> {
  const m: Record<string, string> = {};
  keys.forEach((k, i) => { m[k] = i < SERIES.length ? SERIES[i] : OTHER; });
  return m;
}

export function Legend({ items }: { items: { key: string; label: string; color: string }[] }) {
  if (items.length < 2) return null;
  return <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label="Legend">{items.map((i) =>
    <li key={i.key} className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: i.color }} />{i.label}</li>)}</ul>;
}

export interface StackRow { x: string; key: string; value: number }

function topPath(x: number, y: number, w: number, h: number, r: number): string {
  if (r <= 0) return `M${x},${y}h${w}v${h}h${-w}z`;
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}z`;
}

/** Stacked bars over a categorical x (days). `format` renders values in the tooltip and on the y-axis. */
/** Width of an element, tracked with ResizeObserver (charts draw in real pixels: no viewBox scaling, fixed height). */
function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(640);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(240, Math.floor(e.contentRect.width))));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

export function StackedBars({ rows, keys, labels, height = 180, format, ariaLabel }: {
  rows: StackRow[]; keys: string[]; labels?: Record<string, string>; height?: number; format: (v: number) => string; ariaLabel: string;
}) {
  const [box, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<{ x: string; key: string; v: number; px: number; py: number } | null>(null);
  const xs = useMemo(() => [...new Set(rows.map((r) => r.x))].sort(), [rows]);
  const top = keys.slice(0, SERIES.length);
  const shown = keys.length > SERIES.length ? [...top, "__other"] : top;
  const colors: Record<string, string> = { ...colorMap(top), __other: OTHER };
  const stack = useMemo(() => {
    const by: Record<string, Record<string, number>> = {};
    for (const r of rows) {
      const k = top.includes(r.key) ? r.key : "__other";
      const day = (by[r.x] ??= {});
      day[k] = (day[k] ?? 0) + r.value;
    }
    return by;
  }, [rows, top.join("|")]);                                   // eslint-disable-line react-hooks/exhaustive-deps
  const total = (x: string) => Object.values(stack[x] ?? {}).reduce((a, b) => a + b, 0);
  const max = Math.max(0, ...xs.map(total));
  const W = width, H = height, L = 52, B = 20, T = 8;
  const step = xs.length ? (W - L - 8) / xs.length : 0;
  const bw = Math.max(3, Math.min(22, step * 0.7));
  const y = (v: number) => H - B - (max ? (v / max) * (H - B - T) : 0);
  const ticks = max ? [0, max / 2, max] : [0];
  if (!xs.length) return <div ref={box}><p className="py-10 text-center text-sm text-soft">No AI calls in this period.</p></div>;
  const label = (k: string) => (k === "__other" ? "Other" : labels?.[k] ?? k);
  return <div className="relative" ref={box}>
    <svg width={W} height={H} className="block" role="img" aria-label={ariaLabel} onMouseLeave={() => setHover(null)}>
      {ticks.map((t) => <g key={t}><line x1={L} x2={W - 4} y1={y(t)} y2={y(t)} stroke="var(--color-rule)" />
        <text x={L - 6} y={y(t) + 3} textAnchor="end" fontSize={10} fill="var(--color-soft)">{format(t)}</text></g>)}
      {xs.map((x, i) => {
        let acc = 0;
        const cx = L + i * step + (step - bw) / 2;
        const segs = shown.filter((k) => (stack[x]?.[k] ?? 0) > 0);
        return <g key={x}>
          {segs.map((k, j) => {
            const v = stack[x][k];
            const y0 = y(acc);
            acc += v;
            const y1 = y(acc);
            const h = Math.max(1, y0 - y1 - (j < segs.length - 1 ? 2 : 0));        // 2px surface gap between segments
            const isTop = j === segs.length - 1;
            const show = () => setHover({ x, key: k, v, px: cx + bw / 2, py: y1 });
            return <path key={k} d={topPath(cx, y1, bw, h, isTop ? Math.min(4, bw / 2) : 0)} fill={colors[k]}
              opacity={hover && (hover.x !== x || hover.key !== k) ? 0.55 : 1} onMouseEnter={show} onFocus={show}
              tabIndex={0} aria-label={`${x} ${label(k)}: ${format(v)}`} />;
          })}
          {(i % Math.max(1, Math.ceil(xs.length / Math.max(2, Math.floor(W / 70)))) === 0 || i === xs.length - 1) &&
            <text x={cx + bw / 2} y={H - 6} textAnchor="middle" fontSize={10} fill="var(--color-soft)">{x.slice(5)}</text>}
        </g>;
      })}
      <line x1={L} x2={W - 4} y1={H - B} y2={H - B} stroke="var(--color-muted)" strokeOpacity={0.4} />
    </svg>
    {hover && <div role="tooltip" className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-md border border-rule bg-card px-2 py-1 text-xs shadow-lift"
      style={{ left: hover.px, top: hover.py - 4 }}>
      <div className="font-medium text-ink">{hover.x}</div>
      <div className="flex items-center gap-1.5 text-muted"><span className="inline-block h-2 w-2 rounded-sm" style={{ background: colors[hover.key] }} />
        {label(hover.key)}: <b className="text-ink">{format(hover.v)}</b></div>
      <div className="text-soft">day total {format(total(hover.x))}</div>
    </div>}
    <div className="mt-2"><Legend items={shown.map((k) => ({ key: k, label: label(k), color: colors[k] }))} /></div>
  </div>;
}

/** Spend vs cap: status color + an explicit text label (never color alone). */
export function CapBar({ pct, warnAt = 0.8 }: { pct: number; warnAt?: number }) {
  const p = Math.max(0, pct);
  const state = p >= 1 ? "critical" : p >= warnAt ? "warning" : "good";
  const text = p >= 1 ? "at cap" : p >= warnAt ? "near cap" : "ok";
  return <div className="flex items-center gap-2" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(p * 100)}
    aria-label={`${Math.round(p * 100)} percent of the monthly limit used, ${text}`}>
    <div className="h-2 flex-1 overflow-hidden rounded-full bg-paper-2"><div className="h-2 rounded-full" style={{ width: `${Math.min(100, p * 100)}%`, background: `var(--status-${state})` }} /></div>
    <span className={cn("w-28 text-right text-xs tabular-nums", p >= 1 ? "text-bad" : p >= warnAt ? "text-warn-ink" : "text-muted")}>{Math.round(p * 100)}% · {text}</span>
  </div>;
}

export const usd = (v: number) => (v === 0 ? "$0" : v < 0.01 ? `$${v.toFixed(4)}` : v < 10 ? `$${v.toFixed(2)}` : `$${Math.round(v).toLocaleString()}`);
export const compact = (v: number) => (v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(1)}k` : String(Math.round(v)));


/** Ranked horizontal bars (magnitude by one categorical: sorted, single hue, value labels). */
export function RankBars({ items, format, max = 6 }: { items: { key: string; label: string; value: number; hint?: string }[]; format: (v: number) => string; max?: number }) {
  const top = items.slice(0, max);
  const rest = items.slice(max).reduce((a, b) => a + b.value, 0);
  const all = rest > 0 ? [...top, { key: "__other", label: `Other (${items.length - max})`, value: rest }] : top;
  const hi = Math.max(0, ...all.map((i) => i.value));
  if (!all.length) return <p className="py-4 text-sm text-soft">No data.</p>;
  return <ul className="space-y-2">{all.map((i) => <li key={i.key} className="text-sm">
    <div className="flex items-baseline justify-between gap-2"><span className="truncate" title={i.label}>{i.label}</span><span className="num shrink-0 text-xs text-muted">{format(i.value)}</span></div>
    <div className="mt-1 h-1.5 rounded-full bg-paper-2"><div className="h-1.5 rounded-full" style={{ width: `${hi ? Math.max(2, (i.value / hi) * 100) : 0}%`, background: "var(--series-1)" }} /></div>
  </li>)}</ul>;
}
