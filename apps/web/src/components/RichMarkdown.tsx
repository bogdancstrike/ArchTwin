import { useEffect, useId, useState, type ReactNode } from "react";
import Markdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { RankBars, StackedBars, compact } from "@/components/charts";
import { CodeBlock } from "@/components/CodeBlock";
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

function MermaidBlock({ code }: { code: string }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [svg, setSvg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    void loadMermaid().then(async (mermaid) => {
      const dark = document.documentElement.dataset.theme === "dark";
      mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: dark ? "dark" : "neutral", fontFamily: "inherit" });
      try {
        const out = await mermaid.render(`m${id}`, code);
        if (alive) setSvg(out.svg);
      } catch (e) {
        if (alive) setErr((e as Error).message.split("\n")[0]);
      }
    });
    return () => { alive = false; };
  }, [code, id]);
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
