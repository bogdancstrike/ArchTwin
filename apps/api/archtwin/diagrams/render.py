"""Export renderer + linter for the diagram-design system (AT-DIAGRAM_STUDIO-005/006).

Deterministic layered grid layout → orthogonal router (one dedicated channel per edge in each column gap and one lane per
edge in each row gap, so connectors never overlap collinearly and never pass behind boxes) → rounded bends → masked
labels. The linter re-checks every rule on the routed geometry; on violation the router retries with perturbations and,
if still failing, the export is refused with the report (never publish a non-conforming diagram).
"""
from __future__ import annotations

import html
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TOKENS = json.loads((Path(__file__).parent / "tokens.json").read_text())
W, H = 184, 68
MARGIN = 48
CH_SP, LANE_SP = 12, 12
LABEL_PAD = 7          # mask padding (rule: 6–10 px gap)
RADIUS = TOKENS["rules"]["corner_radius"]
CHAR_W = 5.0           # 8 px Geist Mono advance


@dataclass
class Box:
    id: str
    x: float
    y: float
    w: float = W
    h: float = H

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2


@dataclass
class Routed:
    id: str
    points: list[tuple[float, float]]
    attach: list[tuple[str, str, float]]           # (node, side, y)
    label: str = ""
    label_box: tuple[float, float, float, float] | None = None
    pad: float = LABEL_PAD


@dataclass
class Layout:
    boxes: dict[str, Box]
    routes: list[Routed]
    width: float
    height: float
    violations: list[dict[str, Any]] = field(default_factory=list)


def _ranks(ids: list[str], edges: list[tuple[str, str]], persons: set[str]) -> dict[str, int]:
    out = defaultdict(list)
    for s, t in edges:
        out[s].append(t)
    # break cycles: DFS, drop back edges
    state: dict[str, int] = {}
    dag: list[tuple[str, str]] = []

    def dfs(u: str):
        state[u] = 1
        for v in sorted(out[u]):
            if state.get(v) == 1:
                continue
            dag.append((u, v))
            if v not in state:
                dfs(v)
        state[u] = 2

    for u in sorted(ids, key=lambda i: (i not in persons, i)):
        if u not in state:
            dfs(u)
    rank = {i: 0 for i in ids}
    for _ in range(len(ids)):
        changed = False
        for s, t in dag:
            if rank[t] < rank[s] + 1:
                rank[t] = rank[s] + 1
                changed = True
        if not changed:
            break
    for p in persons:
        rank[p] = 0
    return rank


def layout(view: dict[str, Any], attempt: int = 0) -> Layout:
    ids = [n["id"] for n in view["nodes"]]
    persons = {n["id"] for n in view["nodes"] if n["kind"] == "person"}
    pairs = [(e["source"], e["target"]) for e in view["edges"]]
    rank = _ranks(ids, pairs, persons)
    cols: dict[int, list[str]] = defaultdict(list)
    for i in sorted(ids):
        cols[rank[i]].append(i)
    # barycenter ordering (2 sweeps)
    pos = {i: k for c in cols.values() for k, i in enumerate(c)}
    nbr = defaultdict(list)
    for s, t in pairs:
        nbr[s].append(t)
        nbr[t].append(s)
    for _ in range(2):
        for r in sorted(cols):
            cols[r].sort(key=lambda i: (sum(pos[j] for j in nbr[i]) / len(nbr[i]) if nbr[i] else pos[i], i))
            for k, i in enumerate(cols[r]):
                pos[i] = k
    ncols, nrows = (max(cols) + 1 if cols else 1), max((len(c) for c in cols.values()), default=1)
    # classify edges to size gaps
    gap_ch: dict[int, int] = defaultdict(int)      # gap index g = between col g-1 and g (0 = left margin)
    lane_use: dict[int, int] = defaultdict(int)    # row gap index r = above row r (nrows = bottom margin)
    plan = []
    for e in view["edges"]:
        s, t = e["source"], e["target"]
        rs, rt, ys, yt = rank[s], rank[t], pos[s], pos[t]
        if rt == rs + 1:
            plan.append((e, "adjacent", None))
            gap_ch[rs + 1] += 1
        elif rt == rs:
            plan.append((e, "same", None))
            gap_ch[rs + 1] += 1
        else:
            lo, hi = sorted((ys, yt))
            lane = hi if hi > lo else min(lo + 1, nrows)        # a row gap between the two rows (or just below)
            lane = (lo + hi + 1) // 2 if hi - lo > 1 else lane
            lane = (lane + attempt) % (nrows + 1) if attempt else lane
            plan.append((e, "lane", lane))
            gap_ch[rs + 1] += 1
            gap_ch[rt] += 1
            lane_use[lane] += 1
    longest = max((len(e.get("label", "")) for e in view["edges"]), default=0) * CHAR_W + 2 * LABEL_PAD + 20
    gap_w = {g: max(72, longest, (gap_ch[g] + 1) * CH_SP + 24) + 28 * attempt for g in range(ncols + 1)}
    row_h = {r: max(44, (lane_use[r] + 1) * LANE_SP + 24) + 16 * attempt for r in range(nrows + 1)}
    xcol, x = {}, MARGIN
    for c in range(ncols):
        x += gap_w[c] if c else 0
        xcol[c] = x
        x += W
    width = x + gap_w[ncols] + MARGIN
    yrow, y = {}, MARGIN + row_h[0]
    for r in range(nrows):
        yrow[r] = y
        y += H + row_h[r + 1]
    height = y + MARGIN
    boxes = {i: Box(i, xcol[rank[i]], yrow[pos[i]]) for i in ids}
    # attach points (fanned): per node side, ordered by the other end's y
    sides: dict[tuple[str, str], list[tuple[float, str]]] = defaultdict(list)
    for e, mode, _ in plan:
        s, t = e["source"], e["target"]
        sides[(s, "R")].append((boxes[t].cy, e["id"]))
        sides[(t, "R" if mode == "same" else "L")].append((boxes[s].cy, e["id"]))
    attach_y: dict[tuple[str, str, str], float] = {}
    for (nid, side), lst in sides.items():
        lst.sort()
        n = len(lst)
        for k, (_, eid) in enumerate(lst):
            jitter = (3 + 2 * attempt) * (1 if side == "L" else -1)
            attach_y[(nid, side, eid)] = boxes[nid].y + boxes[nid].h * (k + 1) / (n + 1) + (jitter if n > 0 else 0)
    # de-conflict: stubs sharing a column gap must not sit on the same horizontal line (no collinear overlap)
    by_gap: dict[int, list[tuple[str, str, str]]] = defaultdict(list)
    for (nid, side, eid) in sorted(attach_y, key=lambda k: attach_y[k]):
        by_gap[rank[nid] + 1 if side == "R" else rank[nid]].append((nid, side, eid))
    for keys in by_gap.values():
        taken: list[float] = []
        for k in keys:
            y0, b = attach_y[k], boxes[k[0]]
            y, step = y0, 0
            while any(abs(y - t) < 4 for t in taken) and step < 40:
                step += 1
                y = y0 + (5 * ((step + 1) // 2)) * (1 if step % 2 else -1)
                if not (b.y + 6 <= y <= b.y + b.h - 6):
                    y = y0
            attach_y[k] = y
            taken.append(y)
    ch_next: dict[int, int] = defaultdict(int)
    lane_next: dict[int, int] = defaultdict(int)

    def channel(g: int) -> float:
        ch_next[g] += 1
        left = (xcol[g - 1] + W) if g > 0 else MARGIN
        return left + 12 + ch_next[g] * CH_SP

    def lane_y(r: int) -> float:
        lane_next[r] += 1
        top = (yrow[r - 1] + H) if r > 0 else MARGIN
        return top + 8 + lane_next[r] * LANE_SP

    routes = []
    for e, mode, lane in plan:
        s, t = boxes[e["source"]], boxes[e["target"]]
        rs, rt = rank[s.id], rank[t.id]
        ys = attach_y[(s.id, "R", e["id"])]
        if mode == "adjacent":
            yt = attach_y[(t.id, "L", e["id"])]
            c = channel(rs + 1)
            pts = [(s.x + s.w, ys), (c, ys), (c, yt), (t.x, yt)]
            att = [(s.id, "R", ys), (t.id, "L", yt)]
        elif mode == "same":
            yt = attach_y[(t.id, "R", e["id"])]
            c = channel(rs + 1)
            pts = [(s.x + s.w, ys), (c, ys), (c, yt), (t.x + t.w, yt)]
            att = [(s.id, "R", ys), (t.id, "R", yt)]
        else:
            yt = attach_y[(t.id, "L", e["id"])]
            c1, c2, ly = channel(rs + 1), channel(rt), lane_y(lane)
            pts = [(s.x + s.w, ys), (c1, ys), (c1, ly), (c2, ly), (c2, yt), (t.x, yt)]
            att = [(s.id, "R", ys), (t.id, "L", yt)]
        routes.append(Routed(e["id"], _dedupe(pts), att, e.get("label", "")))
    lay = Layout(boxes, routes, width, height)
    _place_labels(lay)
    return lay


def _dedupe(pts):
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) > 0.01 or abs(p[1] - out[-1][1]) > 0.01:
            out.append(p)
    # drop collinear midpoints
    res = [out[0]]
    for i in range(1, len(out) - 1):
        a, b, c = res[-1], out[i], out[i + 1]
        if not ((abs(a[0] - b[0]) < .01 and abs(b[0] - c[0]) < .01) or (abs(a[1] - b[1]) < .01 and abs(b[1] - c[1]) < .01)):
            res.append(b)
    res.append(out[-1])
    return res


def _intersects(a, b, inflate=0.0) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax - inflate < bx + bw and bx < ax + aw + inflate and ay - inflate < by + bh and by < ay + ah + inflate


def _place_labels(lay: Layout) -> None:
    placed = []
    boxes = [(b.x, b.y, b.w, b.h) for b in lay.boxes.values()]
    for r in lay.routes:
        if not r.label:
            continue
        tw = len(r.label) * CHAR_W
        lw, lh = tw + 2 * LABEL_PAD, 8 + 2 * 3
        segs = sorted(zip(r.points, r.points[1:], strict=False), key=lambda s: -(abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1])))
        for (x1, y1), (x2, y2) in segs:
            for frac in (0.5, 0.35, 0.65, 0.2, 0.8, 0.1, 0.9, 0.45, 0.55, 0.28, 0.72):
                mx, my = x1 + (x2 - x1) * frac, y1 + (y2 - y1) * frac
                cand = (mx - lw / 2, my - lh / 2, lw, lh)
                if not any(_intersects(cand, b, 2) for b in boxes) and not any(_intersects(cand, p, 1) for p in placed):
                    r.label_box = cand
                    placed.append(cand)
                    break
            if r.label_box:
                break


def lint(view: dict[str, Any], lay: Layout) -> list[dict[str, Any]]:
    v: list[dict[str, Any]] = []
    rules = TOKENS["rules"]
    prim = [n for n in view["nodes"] if n.get("primary")]
    if len(prim) > rules["max_primary_nodes"]:
        v.append({"rule": "complexity-budget", "detail": f"{len(prim)} primary nodes > {rules['max_primary_nodes']} (needs overview/detail split)"})
    focal = [x for x in view["nodes"] + view["edges"] if x.get("focal")]
    if len(focal) > rules["max_focal"]:
        v.append({"rule": "focal-budget", "detail": f"{len(focal)} focal elements > {rules['max_focal']}"})
    segs = []
    for r in lay.routes:
        for (x1, y1), (x2, y2) in zip(r.points, r.points[1:], strict=False):
            if abs(x1 - x2) > 0.01 and abs(y1 - y2) > 0.01:
                v.append({"rule": "orthogonal-rounded", "edge": r.id, "detail": "diagonal segment"})
            segs.append((r.id, (x1, y1), (x2, y2)))
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            a, b = segs[i], segs[j]
            if a[0] == b[0]:
                continue
            (ax1, ay1), (ax2, ay2) = a[1], a[2]
            (bx1, by1), (bx2, by2) = b[1], b[2]
            if abs(ay1 - ay2) < .01 and abs(by1 - by2) < .01 and abs(ay1 - by1) < 1:
                lo, hi = max(min(ax1, ax2), min(bx1, bx2)), min(max(ax1, ax2), max(bx1, bx2))
                if hi - lo > 1:
                    v.append({"rule": "no-overlapping-connectors", "edges": [a[0], b[0]], "detail": f"collinear at y={ay1:.0f}"})
            if abs(ax1 - ax2) < .01 and abs(bx1 - bx2) < .01 and abs(ax1 - bx1) < 1:
                lo, hi = max(min(ay1, ay2), min(by1, by2)), min(max(ay1, ay2), max(by1, by2))
                if hi - lo > 1:
                    v.append({"rule": "no-overlapping-connectors", "edges": [a[0], b[0]], "detail": f"collinear at x={ax1:.0f}"})
    seen: dict[tuple[str, str, int], str] = {}
    for r in lay.routes:
        for nid, side, y in r.attach:
            k = (nid, side, round(y))
            if k in seen and seen[k] != r.id:
                v.append({"rule": "fanned-attach-points", "edges": [seen[k], r.id], "detail": f"{nid} {side} y={y:.0f}"})
            seen[k] = r.id
    edge_ends = {e["id"]: (e["source"], e["target"]) for e in view["edges"]}
    for rid, (x1, y1), (x2, y2) in segs:
        rect = (min(x1, x2), min(y1, y2), abs(x2 - x1) or 0.5, abs(y2 - y1) or 0.5)
        for b in lay.boxes.values():
            if b.id in edge_ends.get(rid, ()):
                continue
            if _intersects(rect, (b.x + 1, b.y + 1, b.w - 2, b.h - 2)):
                v.append({"rule": "no-transit-behind-box", "edge": rid, "detail": f"passes behind {b.id}"})
    for r in lay.routes:
        if r.label and r.label_box is None:
            v.append({"rule": "label-masked-gap", "edge": r.id, "detail": "no free position for the masked label"})
        if r.label_box:
            if not (TOKENS["rules"]["label_gap_min"] <= r.pad <= TOKENS["rules"]["label_gap_max"]):
                v.append({"rule": "label-masked-gap", "edge": r.id, "detail": f"mask padding {r.pad}px outside 6–10px"})
            for b in lay.boxes.values():
                if _intersects(r.label_box, (b.x, b.y, b.w, b.h)):
                    v.append({"rule": "no-label-under-node", "edge": r.id, "detail": f"label mask under {b.id}"})
    return v


def layout_and_lint(view: dict[str, Any], max_attempts: int = 6) -> Layout:
    best = None
    for attempt in range(max_attempts):
        lay = layout(view, attempt)
        lay.violations = lint(view, lay)
        if not lay.violations:
            return lay
        if best is None or len(lay.violations) < len(best.violations):
            best = lay
    return best  # type: ignore[return-value]


def _rounded_path(pts: list[tuple[float, float]], r: float = RADIUS) -> str:
    if len(pts) < 3:
        return "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    d = [f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"]
    for i in range(1, len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[i + 1]
        r1 = min(r, abs(x1 - x0) / 2 + abs(y1 - y0) / 2, abs(x2 - x1) / 2 + abs(y2 - y1) / 2)
        ax = x1 - (r1 if x1 > x0 else -r1) if abs(x1 - x0) > .01 else x1
        ay = y1 - (r1 if y1 > y0 else -r1) if abs(y1 - y0) > .01 else y1
        bx = x1 + (r1 if x2 > x1 else -r1) if abs(x2 - x1) > .01 else x1
        by = y1 + (r1 if y2 > y1 else -r1) if abs(y2 - y1) > .01 else y1
        d.append(f"L {ax:.1f} {ay:.1f} Q {x1:.1f} {y1:.1f} {bx:.1f} {by:.1f}")
    d.append(f"L {pts[-1][0]:.1f} {pts[-1][1]:.1f}")
    return " ".join(d)


def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def to_svg(view: dict[str, Any], lay: Layout, tokens: dict[str, str] | None = None, title: str | None = None) -> str:
    t = {**TOKENS["light"], **(tokens or {})}
    e = html.escape
    nodes = {n["id"]: n for n in view["nodes"]}
    out = [(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {lay.width:.0f} {lay.height + 40:.0f}" width="{lay.width:.0f}" '
           f'height="{lay.height + 40:.0f}" font-family="Geist, system-ui, sans-serif" role="img" aria-label="{e(title or view["title"])}">'),
           f'<title>{e(title or view["title"])}</title>',
           '<defs>',
           f'<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{t["muted"]}"/></marker>',
           f'<marker id="arrow-accent" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{t["accent"]}"/></marker>',
           f'<marker id="arrow-link" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{t["link"]}"/></marker>',
           '</defs>',
           f'<rect width="100%" height="100%" fill="{t["paper"]}"/>',
           f'<text x="{MARGIN}" y="30" font-family="Instrument Serif, Georgia, serif" font-size="22" fill="{t["ink"]}">{e(title or view["title"])}</text>']
    edges = {x["id"]: x for x in view["edges"]}
    for r in lay.routes:
        ed = edges[r.id]
        color, marker = (t["accent"], "arrow-accent") if ed.get("focal") else ((t["link"], "arrow-link") if ed["kind"] == "calls" else (t["muted"], "arrow"))
        dash = ' stroke-dasharray="5 4"' if ed["kind"] == "depends-on" or ed.get("inferred_only") or ed.get("confidence", 1) < 0.6 else ""
        out.append(f'<path d="{_rounded_path(r.points)}" fill="none" stroke="{color}" stroke-width="{1.8 if ed.get("focal") else 1.2}"{dash} marker-end="url(#{marker})"><title>{e(ed["label"])}</title></path>')
    for n in view["nodes"]:
        b = lay.boxes[n["id"]]
        focal = n.get("focal")
        fill = t["accent-tint"] if focal else (t["paper-2"] if not n.get("primary") else "#ffffff")
        stroke = t["accent"] if focal else (t["ink"] if n.get("primary") else t["muted"])
        dash = ' stroke-dasharray="5 3"' if n.get("inferred_only") or n["kind"] == "group" else ""
        eyebrow = {"person": "PERSON", "external": "EXTERNAL SYSTEM", "system": "SOFTWARE SYSTEM", "group": "GROUP",
                   "component": "COMPONENT"}.get(n["kind"], (n.get("subtype") or "container").upper())
        out.append(f'<g><rect x="{b.x:.1f}" y="{b.y:.1f}" width="{b.w}" height="{b.h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="{1.6 if focal else 1}"{dash}/>')
        out.append(f'<text x="{b.x + 12:.1f}" y="{b.y + 17:.1f}" font-family="Geist Mono, ui-monospace, monospace" font-size="8" letter-spacing="1.4" fill="{t["soft"]}">{e(eyebrow)}</text>')
        out.append(f'<text x="{b.x + 12:.1f}" y="{b.y + 37:.1f}" font-size="12" font-weight="600" fill="{t["ink"]}">{e(_clip(n["name"], 24))}</text>')
        if n.get("technology"):
            out.append(f'<text x="{b.x + 12:.1f}" y="{b.y + 54:.1f}" font-family="Geist Mono, ui-monospace, monospace" font-size="9" fill="{t["muted"]}">{e(_clip(n["technology"], 30))}</text>')
        out.append("</g>")
    for r in lay.routes:
        if r.label and r.label_box:
            x, y, w, h = r.label_box
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{t["paper"]}" rx="2"/>')
            out.append(f'<text x="{x + w / 2:.1f}" y="{y + h / 2 + 3:.1f}" text-anchor="middle" font-family="Geist Mono, ui-monospace, monospace" font-size="8" letter-spacing="0.5" fill="{t["muted"]}">{e(r.label)}</text>')
    legend_y = lay.height + 20
    out.append(f'<text x="{MARGIN}" y="{legend_y}" font-family="Geist Mono, ui-monospace, monospace" font-size="8" fill="{t["soft"]}">'
               f'{e("SOLID = OBSERVED/DECLARED · DASHED = DEPENDS-ON, INFERRED OR LOW CONFIDENCE · ACCENT = FOCAL")}</text>')
    _ = nodes
    out.append("</svg>")
    return "\n".join(out)
