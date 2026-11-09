import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import csharp from "highlight.js/lib/languages/csharp";
import go from "highlight.js/lib/languages/go";
import java from "highlight.js/lib/languages/java";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import kotlin from "highlight.js/lib/languages/kotlin";
import python from "highlight.js/lib/languages/python";
import rust from "highlight.js/lib/languages/rust";
import sql from "highlight.js/lib/languages/sql";
import typescript from "highlight.js/lib/languages/typescript";
import yaml from "highlight.js/lib/languages/yaml";
import { Check, Copy, Maximize2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Button, Dialog, cn } from "@/components/ui";

for (const [name, lang] of Object.entries({ bash, csharp, go, java, javascript, json, kotlin, python, rust, sql, typescript, yaml })) hljs.registerLanguage(name, lang);

export interface Source { path: string; revision?: string; start: number; end: number; language: string; text: string; truncated?: boolean }

/** Split highlighted HTML into lines, closing and re-opening spans that cross line breaks (docstrings, block comments). */
export function splitHighlighted(html: string): string[] {
  const out: string[] = [];
  const open: string[] = [];
  for (const line of html.split("\n")) {
    const prefix = open.join("");
    for (const m of line.matchAll(/<span[^>]*>|<\/span>/g)) {
      if (m[0] === "</span>") open.pop(); else open.push(m[0]);
    }
    out.push(prefix + line + "</span>".repeat(open.length));
  }
  return out;
}

/** Highlighted source with real file line numbers (highlight.js escapes the code, so the HTML is safe to inject). */
function Lines({ src, highlight, className, maxHeight }: { src: Source; highlight?: [number, number]; className?: string; maxHeight?: number }) {
  const html = useMemo(() => {
    const lang = hljs.getLanguage(src.language) ? src.language : "plaintext";
    const out = lang === "plaintext" ? hljs.highlightAuto(src.text).value : hljs.highlight(src.text, { language: lang, ignoreIllegals: true }).value;
    return splitHighlighted(out);
  }, [src]);
  return <div style={maxHeight ? { maxHeight } : undefined}
    className={cn("hljs overflow-auto rounded-md border border-rule bg-[var(--code-bg)] font-mono text-[11.5px] leading-[1.55]", className)}>
    <table className="w-max min-w-full border-collapse"><tbody>{html.map((h, i) => {
      const n = src.start + i;
      const on = highlight && n >= highlight[0] && n <= highlight[1];
      return <tr key={n} className={on ? "bg-[var(--code-hl)]" : undefined}>
        <td className="select-none border-r border-rule px-2 text-right align-top text-soft">{n}</td>
        <td className="whitespace-pre px-3" dangerouslySetInnerHTML={{ __html: h || " " }} /></tr>;
    })}</tbody></table>
  </div>;
}

export function CodeBlock({ src, highlight, maxHeight = 320, title }: { src: Source; highlight?: [number, number]; maxHeight?: number; title?: string }) {
  const [copied, setCopied] = useState(false);
  const [big, setBig] = useState(false);
  return <div>
    <div className="mb-1 flex items-center gap-1 text-[11px] text-soft">
      <span className="truncate font-mono" title={src.path}>{src.path}:{src.start}–{src.end}</span>
      {src.revision && <span className="font-mono">@{src.revision.slice(0, 10)}</span>}
      <span className="ml-auto flex gap-0.5">
        <Button size="sm" variant="ghost" aria-label="Copy code" onClick={() => { void navigator.clipboard.writeText(src.text); setCopied(true); setTimeout(() => setCopied(false), 1200); }}>
          {copied ? <Check size={12} /> : <Copy size={12} />}</Button>
        <Button size="sm" variant="ghost" aria-label="Expand code" onClick={() => setBig(true)}><Maximize2 size={12} /></Button></span>
    </div>
    <Lines src={src} highlight={highlight} maxHeight={maxHeight} className="text-[11px]" />
    {src.truncated && <p className="mt-1 text-[10px] text-soft">Showing the first 400 lines.</p>}
    <Dialog open={big} onClose={() => setBig(false)} title={title ?? src.path} wide>
      <Lines src={src} highlight={highlight} className="max-h-[70vh] text-[12.5px]" />
    </Dialog>
  </div>;
}
