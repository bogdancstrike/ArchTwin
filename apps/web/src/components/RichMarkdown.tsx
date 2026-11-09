import { useEffect, useId, useState, type ReactNode } from "react";
import Markdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { RankBars, StackedBars, compact } from "@/components/charts";
import { CodeBlock } from "@/components/CodeBlock";
import { useTheme } from "@/lib/theme";
import { Table, cn } from "@/components/ui";

/** Markdown with rendered visual blocks — used by the Assistant, generated docs and decision records.
 *  ```mermaid   any Mermaid diagram (flowchart, sequence, class, state, ER, gantt, …), rendered with securityLevel=strict
 *  ```chart     {"type": "bar"|"stacked", "title": "…", "unit": "…", "data": [{"label": "…", "value": 1, "series": "…"}]}
 *  other code   syntax-highlighted
 */

let mermaidReady: Promise<typeof import("mermaid").default> | null = null;
function loadMermaid() {
  mermaidReady ??= import("mermaid").then((m) => m.default);
  return mermaidReady;
}

/** Neutral graphite variables for mermaid's "base" theme in night mode (its built-in "dark" theme has a blue cast). */
const MERMAID_DARK = { background: "transparent", primaryColor: "#262626", primaryTextColor: "#ecebe8", primaryBorderColor: "#5a5751",
  secondaryColor: "#2c2c2c", tertiaryColor: "#1f1f1f", lineColor: "#9d9991", textColor: "#ecebe8", mainBkg: "#262626", nodeBorder: "#5a5751",
  clusterBkg: "#1f1f1f", clusterBorder: "#3a3a3a", titleColor: "#ecebe8", edgeLabelBackground: "#1b1b1b", actorBkg: "#262626",
  actorBorder: "#5a5751", actorTextColor: "#ecebe8", signalColor: "#c2bfb8", signalTextColor: "#ecebe8", labelBoxBkgColor: "#262626",
  noteBkgColor: "#3a3227", noteTextColor: "#ecebe8", noteBorderColor: "#6b5a43", darkMode: true };

function MermaidBlock({ code }: { code: string }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [svg, setSvg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const theme = useTheme();
  useEffect(() => {
    let alive = true;
    void loadMermaid().then(async (mermaid) => {
      const dark = theme === "dark";
      mermaid.initialize({ startOnLoad: false, securityLevel: "strict", fontFamily: "inherit",
        ...(dark ? { theme: "base", themeVariables: MERMAID_DARK } : { theme: "neutral" }) });
      try {
        const out = await mermaid.render(`m${id}`, code);
        if (alive) setSvg(out.svg);
      } catch (e) {
        if (alive) setErr((e as Error).message.split("\n")[0]);
      }
    });
    return () => { alive = false; };
  }, [code, id, theme]);
  if (err) return <div className="my-2"><p className="text-xs text-bad">Diagram could not be rendered: {err}</p>
    <pre className="overflow-auto rounded bg-paper-2 p-2 text-xs">{code}</pre></div>;
  if (!svg) return <div className="my-2 h-24 animate-pulse rounded-lg bg-paper-2" aria-label="Rendering diagram" />;
  return <figure className="my-3 overflow-auto rounded-lg border border-rule bg-card p-3 [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full"
    aria-label="Diagram" dangerouslySetInnerHTML={{ __html: svg }} />;
}

interface ChartSpec { type?: "bar" | "stacked"; title?: string; unit?: string; data?: { label?: string; x?: string; value: number; series?: string }[] }

function ChartBlock({ code }: { code: string }) {
  let spec: ChartSpec;
  try { spec = JSON.parse(code); } catch { return <pre className="overflow-auto rounded bg-paper-2 p-2 text-xs">{code}</pre>; }
  const data = (spec.data ?? []).filter((d) => typeof d.value === "number");
  const fmt = (v: number) => `${compact(v)}${spec.unit ? ` ${spec.unit}` : ""}`;
  const label = (d: { label?: string; x?: string }) => d.label ?? d.x ?? "";
  return <figure className="my-3 rounded-lg border border-rule bg-card p-3">
    {spec.title && <figcaption className="mb-2 text-sm font-medium">{spec.title}</figcaption>}
    {spec.type === "stacked"
      ? <StackedBars ariaLabel={spec.title ?? "Chart"} format={fmt} height={180}
          rows={data.map((d) => ({ x: label(d), key: d.series ?? "value", value: d.value }))}
          keys={[...new Set(data.map((d) => d.series ?? "value"))]} />
      : <RankBars format={fmt} max={12} items={data.map((d, i) => ({ key: `${label(d)}-${i}`, label: label(d), value: d.value }))} />}
    <details className="mt-2"><summary className="cursor-pointer text-xs text-link">Data</summary>
      <Table head={["Label", ...(spec.type === "stacked" ? ["Series"] : []), "Value"]}>{data.map((d, i) => <tr key={i} className="border-b border-rule">
        <td className="px-2 py-1">{label(d)}</td>{spec.type === "stacked" && <td className="px-2">{d.series}</td>}<td className="num px-2">{fmt(d.value)}</td></tr>)}</Table></details>
  </figure>;
}

export function RichMarkdown({ children, className }: { children: string; className?: string }) {
  return <article className={cn("prose-at", className)}>
    <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]} components={{
      pre: ({ children: c }) => <>{c}</>,
      code: ({ className: cls, children: c }) => {
        const lang = /language-([\w-]+)/.exec(cls ?? "")?.[1];
        const text = String(c ?? "").replace(/\n$/, "");
        if (!lang && !text.includes("\n")) return <code>{c as ReactNode}</code>;               // inline code
        if (lang === "mermaid") return <MermaidBlock code={text} />;
        if (lang === "chart") return <ChartBlock code={text} />;
        return <div className="my-2"><CodeBlock src={{ path: lang ?? "code", start: 1, end: text.split("\n").length, language: lang ?? "plaintext", text }} maxHeight={420} /></div>;
      },
    }}>{children}</Markdown>
  </article>;
}
