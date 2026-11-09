"""A small Markdown block parser shared by the DOCX and PDF renderers.

Markdown is the canonical export format; the binary renderers only need its structure: headings, paragraphs, bullet and
numbered lists, GFM tables, fenced code (```mermaid included), block quotes and rules. Inline markup is reduced to runs of
plain / bold / italic / code text (links keep their label and URL).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

MERMAID_CAPTION = "Mermaid diagram (render in Markdown viewers)"


@dataclass
class Block:
    kind: str                         # heading | para | bullets | numbers | table | code | quote | rule
    text: str = ""
    level: int = 0
    items: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    lang: str = ""


_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
_NUMBER = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _cells(line: str) -> list[str]:
    s = line.strip()
    s = s.removeprefix("|")
    s = s.removesuffix("|")
    return [c.strip() for c in re.split(r"(?<!\\)\|", s)]


def parse(md: str) -> list[Block]:
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[Block] = []
    i = 0
    para: list[str] = []

    def flush() -> None:
        if para:
            out.append(Block("para", " ".join(x.strip() for x in para)))
            para.clear()

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            flush()
            lang = line.strip()[3:].strip()
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            out.append(Block("code", "\n".join(body), lang=lang))
            i += 1
            continue
        if not line.strip():
            flush()
            i += 1
            continue
        if m := _HEADING.match(line):
            flush()
            out.append(Block("heading", m.group(2).strip().rstrip("#").strip(), level=len(m.group(1))))
        elif _RULE.match(line):
            flush()
            out.append(Block("rule"))
        elif "|" in line and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1]):
            flush()
            rows = [_cells(line)]
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(_cells(lines[i]))
                i += 1
            width = len(rows[0])
            out.append(Block("table", rows=[(r + [""] * width)[:width] for r in rows]))
            continue
        elif _BULLET.match(line) or _NUMBER.match(line):
            flush()
            ordered = bool(_NUMBER.match(line)) and not _BULLET.match(line)
            pat = _NUMBER if ordered else _BULLET
            items = []
            while i < len(lines) and (m := pat.match(lines[i])):
                item = m.group(1)
                i += 1
                while i < len(lines) and lines[i].startswith(("  ", "\t")) and lines[i].strip() and not pat.match(lines[i]):
                    item += " " + lines[i].strip()
                    i += 1
                items.append(item)
            out.append(Block("numbers" if ordered else "bullets", items=items))
            continue
        elif line.lstrip().startswith(">"):
            flush()
            q = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                q.append(lines[i].lstrip()[1:].strip())
                i += 1
            out.append(Block("quote", " ".join(q)))
            continue
        else:
            para.append(line)
        i += 1
    flush()
    return out


_INLINE = re.compile(r"(\*\*[^*]+\*\*|__[^_]+__|`[^`]+`|\*[^*\s][^*]*\*|\[[^\]]+\]\([^)]+\))")


def runs(text: str) -> list[tuple[str, str]]:
    """'a **b** `c`' -> [('a ', ''), ('b', 'bold'), (' ', ''), ('c', 'code')]."""
    out: list[tuple[str, str]] = []
    pos = 0
    for m in _INLINE.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], ""))
        t = m.group(0)
        if t.startswith(("**", "__")):
            out.append((t[2:-2], "bold"))
        elif t.startswith("`"):
            out.append((t[1:-1], "code"))
        elif t.startswith("["):
            label, url = re.match(r"\[([^\]]+)\]\(([^)]+)\)", t).groups()  # type: ignore[union-attr]
            out.append((label if label == url else f"{label} ({url})", ""))
        else:
            out.append((t[1:-1], "italic"))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], ""))
    return [(t.replace("\\|", "|"), s) for t, s in out if t]


def plain(text: str) -> str:
    return "".join(t for t, _ in runs(text))
