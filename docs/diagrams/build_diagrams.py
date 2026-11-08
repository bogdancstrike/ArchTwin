#!/usr/bin/env python3
"""Build ArchTwin documentation diagrams with the diagram-design system (MIT,
github.com/cathrynlavery/diagram-design), default skin (= ArchTwin brand palette).

Each diagram is written as a self-contained HTML file (source of truth) next to this script.
Export to SVG/PNG with export_diagrams.py. All coordinates sit on the 4px grid.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent
PAPER, INK, MUTED, SOFT, ACCENT, LINK = "#f5f5f5", "#2d3142", "#4f5d75", "#7a8399", "#eb6c36", "#2e5aa8"
SANS, MONO = "'Geist', sans-serif", "'Geist Mono', monospace"

KIND = {  # node type -> (fill, stroke, tag stroke, tag text, dash)
    "focal":    ("rgba(235,108,54,0.08)", ACCENT, "rgba(235,108,54,0.50)", ACCENT, None),
    "step":     ("#ffffff", INK, "rgba(45,49,66,0.40)", MUTED, None),
    "store":    ("rgba(45,49,66,0.05)", MUTED, "rgba(79,93,117,0.40)", MUTED, None),
    "external": ("rgba(45,49,66,0.03)", "rgba(45,49,66,0.30)", "rgba(45,49,66,0.22)", SOFT, None),
    "input":    ("rgba(79,93,117,0.10)", SOFT, "rgba(122,131,153,0.40)", SOFT, None),
    "async":    ("rgba(45,49,66,0.02)", "rgba(45,49,66,0.20)", "rgba(45,49,66,0.22)", SOFT, "4,3"),
}


def r4(v):
    return int(-(-v // 4) * 4)


def node(x, y, w, h, kind, tag, name, sub):
    fill, stroke, tstroke, ttext, dash = KIND[kind]
    tw = r4(len(tag) * 5 + 12)
    d = f' stroke-dasharray="{dash}"' if dash else ""
    cx = x + w // 2
    ny, sy = (y + h // 2 + 4, y + h // 2 + 19) if h > 56 else (y + 32, y + 47)
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{PAPER}"/>'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1"{d}/>'
            f'<rect x="{x+8}" y="{y+8}" width="{tw}" height="12" rx="2" fill="none" stroke="{tstroke}" stroke-width="0.8"/>'
            f'<text x="{x+8+tw//2}" y="{y+17}" fill="{ttext}" font-size="7" font-family="{MONO}" text-anchor="middle" letter-spacing="0.08em">{tag}</text>'
            f'<text x="{cx}" y="{ny}" fill="{INK}" font-size="12" font-weight="600" font-family="{SANS}" text-anchor="middle">{name}</text>'
            f'<text x="{cx}" y="{sy}" fill="{MUTED}" font-size="9" font-family="{MONO}" text-anchor="middle">{sub}</text>\n')


def arrow(d, color=MUTED, dashed=False, marker=None, width=1.2):
    m = marker or {MUTED: "arrow", ACCENT: "arrow-accent", LINK: "arrow-link"}[color]
    da = ' stroke-dasharray="5,4"' if dashed else ""
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"{da} marker-end="url(#{m})"/>\n'


def label(cx, y_line, text, color=SOFT, side_x=None, mid_y=None):
    """Masked arrow label: above a horizontal segment (6px gap) or beside a vertical one (side_x)."""
    w = r4(len(text) * 5.2 + 12)
    if side_x is not None:
        x, y = side_x, mid_y - 6
        tx = x + w // 2
    else:
        x, y = cx - w // 2, y_line - 20
        tx = cx
    return (f'<rect x="{x}" y="{y}" width="{w}" height="12" rx="2" fill="{PAPER}"/>'
            f'<text x="{tx}" y="{y+9}" fill="{color}" font-size="8" font-family="{MONO}" text-anchor="middle" letter-spacing="0.06em">{text}</text>\n')


def legend(y, width, items):
    s = (f'<line x1="32" y1="{y}" x2="{width-32}" y2="{y}" stroke="rgba(45,49,66,0.10)" stroke-width="0.8"/>'
         f'<text x="32" y="{y+24}" fill="{MUTED}" font-size="8" font-family="{MONO}" letter-spacing="0.14em">LEGEND</text>\n')
    x = 112
    for kind, text in items:
        if kind.startswith("line"):
            col = {"line": MUTED, "line-accent": ACCENT, "line-link": LINK}[kind.split(":")[0]]
            dash = ' stroke-dasharray="5,4"' if kind.endswith(":dash") else ""
            s += f'<line x1="{x}" y1="{y+20}" x2="{x+24}" y2="{y+20}" stroke="{col}" stroke-width="1.2"{dash}/>'
        else:
            fill, stroke, _, _, dash = KIND[kind]
            d = f' stroke-dasharray="{dash}"' if dash else ""
            s += f'<rect x="{x}" y="{y+14}" width="24" height="12" rx="2" fill="{fill}" stroke="{stroke}" stroke-width="1"{d}/>'
        s += f'<text x="{x+32}" y="{y+24}" fill="{MUTED}" font-size="8" font-family="{MONO}" letter-spacing="0.04em">{text}</text>\n'
        x += 40 + r4(len(text) * 5.2) + 16
    return s


HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Geist', system-ui, sans-serif; background: #f5f5f5; color: #2d3142;
           min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 3rem 2rem; }}
    .frame {{ max-width: 1200px; width: 100%; }}
    .eyebrow {{ font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.66rem; font-weight: 500;
               letter-spacing: 0.18em; text-transform: uppercase; color: #4f5d75; margin-bottom: 0.5rem; }}
    h1 {{ font-family: 'Instrument Serif', serif; font-size: clamp(1.5rem, 2.4vw + 0.75rem, 2rem);
         font-weight: 400; letter-spacing: -0.02em; line-height: 1.15; margin-bottom: 1.5rem; }}
    svg {{ width: 100%; min-width: 760px; display: block; }}
  </style>
</head>
<body>
  <div class="frame">
    <p class="eyebrow">{eyebrow} · ArchTwin</p>
    <h1>{title}</h1>
    <svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="{slug}-title {slug}-desc">
      <title id="{slug}-title">{title}</title>
      <desc id="{slug}-desc">{desc}</desc>
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#4f5d75"/></marker>
        <marker id="arrow-accent" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#eb6c36"/></marker>
        <marker id="arrow-link" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#2e5aa8"/></marker>
        <marker id="arrow-open" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polyline points="0 0, 8 3, 0 6" fill="none" stroke="#4f5d75" stroke-width="1.2"/></marker>
      </defs>
      <rect width="100%" height="100%" fill="#f5f5f5"/>
{body}    </svg>
  </div>
</body>
</html>
"""


def write(slug, eyebrow, title, desc, w, h, body):
    (OUT / f"{slug}.html").write_text(HEAD.format(slug=slug, eyebrow=eyebrow, title=title, desc=desc, w=w, h=h, body=body))


# ---------------------------------------------------------------- 1. How it works
def how_it_works():
    b = ""
    # arrows first
    b += arrow("M 192,224 H 240")                                   # sources -> observations
    b += arrow("M 400,224 H 448")                                   # observations -> graph
    b += arrow("M 624,212 H 672")                                   # graph -> drift
    b += arrow("M 752,116 V 188")                                   # baseline -> drift
    b += arrow("M 832,224 H 880")                                   # drift -> triage
    b += arrow("M 536,260 V 316")                                   # graph -> diagrams
    b += arrow("M 624,240 H 640 Q 648,240 648,248 V 336 Q 648,344 656,344 H 672")  # graph -> AI
    # AI proposals -> baseline (dashed, hops over drift->triage at y=224)
    b += arrow("M 832,344 H 848 Q 856,344 856,336 V 232 a 8,8 0 0,1 0,-16 V 96 Q 856,88 848,88 H 832",
               dashed=True, width=1)
    b += label(0, 0, "INTENT", side_x=760, mid_y=152)
    b += label(0, 0, "PROPOSALS", side_x=864, mid_y=152)
    b += label(0, 0, "CITED", side_x=656, mid_y=292)
    # nodes
    b += node(32, 188, 160, 72, "external", "EXT", "Read-only sources", "git · k8s · db · otel")
    b += node(240, 188, 160, 72, "store", "STORE", "Observations", "immutable evidence")
    b += node(448, 188, 176, 72, "focal", "CORE", "Architecture graph", "temporal · postgres")
    b += node(672, 60, 160, 56, "input", "INTENT", "Baseline + ADRs", "approved design")
    b += node(672, 188, 160, 72, "focal", "RULES", "Drift engine", "deterministic")
    b += node(880, 188, 128, 72, "step", "OUT", "Triage", "alerts · SARIF")
    b += node(448, 316, 176, 56, "step", "VIEW", "C4 diagrams · docs", "zoom · diff · export")
    b += node(672, 316, 160, 56, "step", "AI", "Grounded AI", "cited proposals")
    b += legend(404, 1040, [("focal", "focal"), ("step", "step"), ("store", "store"), ("external", "external"),
                            ("input", "intent"), ("line:dash", "needs approval")])
    write("how-it-works", "Architecture", "How ArchTwin works",
          "Read-only sources become immutable observations that build a temporal architecture graph; a deterministic "
          "drift engine compares it with the approved baseline, while diagrams, triage and grounded AI proposals are derived from it.",
          1040, 452, b)


# ---------------------------------------------------------------- 2. System context (C4 L1)
def system_context():
    b = ""
    b += arrow("M 192,196 H 236 Q 244,196 244,204 V 240 Q 244,248 252,248 H 296")
    b += arrow("M 192,340 H 236 Q 244,340 244,332 V 296 Q 244,288 252,288 H 296")
    ext = [  # (attach y, lane x, target centre y)
        (236, 516, 68), (248, 532, 148), (260, 548, 228),
        (276, 548, 308), (288, 532, 388), (300, 516, 468),
    ]
    for ay, lx, ty in ext:
        if ty < ay:
            d = f"M 496,{ay} H {lx-8} Q {lx},{ay} {lx},{ay-8} V {ty+8} Q {lx},{ty} {lx+8},{ty} H 600"
        else:
            d = f"M 496,{ay} H {lx-8} Q {lx},{ay} {lx},{ay+8} V {ty-8} Q {lx},{ty} {lx+8},{ty} H 600"
        b += arrow(d, color=LINK)
    b += node(32, 168, 160, 56, "input", "USER", "Architect · tech lead", "design · review")
    b += node(32, 312, 160, 56, "input", "USER", "Security · platform", "policy · operations")
    b += node(296, 224, 200, 88, "focal", "SYSTEM", "ArchTwin", "living architecture twin")
    specs = [("IDP", "Keycloak", "single sign-on · OIDC"), ("GIT", "GitHub · GitLab", "repos · PRs · webhooks"),
             ("WORK", "Jira · Taiga", "issues · status"), ("RUNTIME", "Kubernetes · OpenTelemetry", "workloads · call graph"),
             ("DATA", "Postgres · Kafka", "schemas · topics"), ("LLM", "OpenAI via LiteLLM", "luna · terra · sol")]
    for i, (tag, name, sub) in enumerate(specs):
        b += node(600, 40 + 80 * i, 240, 56, "external", tag, name, sub)
    b += legend(528, 880, [("focal", "the system"), ("input", "people"), ("external", "external system"),
                           ("line-link:", "read-only / API")])
    write("system-context", "C4 · Level 1 system context", "ArchTwin system context",
          "C4 system context: architects and security or platform engineers use ArchTwin, which reads from Git providers, "
          "work trackers, Kubernetes and telemetry, data catalogs, signs users in with Keycloak and reaches OpenAI only through LiteLLM.",
          880, 576, b)


# ---------------------------------------------------------------- 3. Containers (C4 L2)
def containers():
    b = ""
    b += arrow("M 152,116 H 200")
    b += arrow("M 344,116 H 392")
    b += arrow("M 552,116 H 600", color=LINK)
    b += arrow("M 432,144 V 240")
    b += arrow("M 512,144 V 184 Q 512,192 520,192 H 672 Q 680,192 680,200 V 240")
    b += arrow("M 552,272 H 600")
    b += arrow("M 392,272 H 344")
    b += arrow("M 432,296 V 384")
    b += arrow("M 528,296 V 404 Q 528,412 536,412 H 600", color=LINK)
    b += label(0, 0, "WORKFLOWS", side_x=440, mid_y=192)
    b += label(596, 192, "SQL")
    b += label(0, 0, "READ-ONLY", side_x=536, mid_y=348, color=LINK)
    b += node(32, 88, 120, 56, "input", "USER", "Architect", "browser")
    b += node(200, 88, 144, 56, "step", "UI", "Web UI", "React · React Flow")
    b += node(392, 88, 160, 56, "focal", "API", "API", "FastAPI monolith")
    b += node(600, 88, 176, 56, "external", "AUTH", "Keycloak · Cerbos", "OIDC · policy")
    b += node(200, 240, 144, 56, "external", "LLM", "LiteLLM", "OpenAI · Langfuse")
    b += node(392, 240, 160, 56, "step", "JOBS", "Temporal workers", "scan · drift · AI")
    b += node(600, 240, 176, 56, "focal", "DB", "PostgreSQL", "graph · evidence · audit")
    b += node(392, 384, 112, 56, "store", "S3", "Object store", "raw artifacts")
    b += node(600, 384, 176, 56, "external", "SRC", "Read-only sources", "git · k8s · otel")
    b += legend(472, 816, [("focal", "core"), ("step", "container"), ("store", "store"), ("external", "adopted / external"),
                           ("line-link:", "external call")])
    write("containers", "C4 · Level 2 containers", "ArchTwin containers",
          "C4 container view: the web UI calls a FastAPI modular monolith that authorizes through Keycloak and Cerbos, stores "
          "everything in PostgreSQL and starts Temporal workers, which read sources read-only, keep raw artifacts in object storage and call models through LiteLLM.",
          816, 520, b)


# ---------------------------------------------------------------- sequence helpers
def seq_frame(actors, top, bottom, bars):
    s = ""
    for _, _, _, _, cx in actors:
        s += f'<line x1="{cx}" y1="{top}" x2="{cx}" y2="{bottom}" stroke="rgba(45,49,66,0.22)" stroke-width="1" stroke-dasharray="3,3"/>\n'
    for cx, y1, y2 in bars:
        s += f'<rect x="{cx-4}" y="{y1}" width="8" height="{y2-y1}" fill="rgba(45,49,66,0.06)" stroke="{MUTED}" stroke-width="0.8"/>\n'
    return s


def msg(x1, x2, y, text, color=MUTED, dashed=False, open_=False):
    m = "arrow-open" if open_ else None
    s = arrow(f"M {x1},{y} H {x2}", color=color, dashed=dashed, marker=m, width=1.4 if color == ACCENT else 1.2)
    return s + label((x1 + x2) // 2, y, text, color=color if color != MUTED else SOFT)


def self_msg(cx, y, text):
    return (arrow(f"M {cx+4},{y} H {cx+40} V {y+32} H {cx+4}")
            + label(0, 0, text, side_x=cx + 48, mid_y=y + 16))


def actors_md(actors):
    return "".join(node(cx - 72, 72, 144, 56, kind, tag, name, sub) for kind, tag, name, sub, cx in actors)


SEQ_LEGEND = [("line", "call"), ("line:dash", "return / async"), ("line-accent:", "headline result")]


def drift_sequence():
    A = [("external", "GIT", "GitHub · GitLab", "provider", 112), ("step", "WORKER", "Connector", "Temporal activity", 304),
         ("store", "DB", "PostgreSQL", "evidence · outbox", 496), ("focal", "RULES", "Drift engine", "versioned rules", 688),
         ("input", "UI", "Architect UI", "SSE", 880)]
    b = seq_frame(A, 128, 584, [(304, 176, 292), (496, 288, 340), (688, 336, 552)])
    b += msg(112, 300, 176, "SIGNED WEBHOOK", color=LINK)
    b += self_msg(304, 224, "VERIFY · DEDUPE")
    b += msg(308, 492, 288, "OBSERVATIONS")
    b += msg(500, 684, 336, "OUTBOX EVENT", dashed=True, open_=True)
    b += msg(684, 500, 384, "READ SNAPSHOTS")
    b += msg(500, 684, 432, "3-WAY EVIDENCE", dashed=True)
    b += self_msg(688, 472, "APPLY RULES")
    b += msg(692, 880, 552, "DRIFT FINDING", color=ACCENT)
    b += actors_md(A)
    b += legend(604, 1000, SEQ_LEGEND)
    write("drift-sequence", "Sequence", "Drift detection after a merged change",
          "Sequence: a signed Git webhook is verified and deduplicated by a connector worker, stored as observations in PostgreSQL, "
          "and an outbox event triggers the drift engine, which reads desired, code and runtime snapshots and sends a drift finding to the architect UI.",
          1000, 648, b)


def ai_sequence():
    A = [("input", "UI", "Architect UI", "question", 112), ("external", "PDP", "Cerbos", "policy", 304),
         ("step", "RETRIEVE", "Scoped retriever", "graph tools", 496), ("focal", "LLM", "LiteLLM", "luna (default)", 688),
         ("async", "TRACE", "Langfuse", "traces · evals", 880)]
    b = seq_frame(A, 128, 640, [(304, 176, 224), (496, 272, 596), (688, 384, 484)])
    b += msg(112, 300, 176, "AUTHORIZE A + B")
    b += msg(300, 112, 224, "ALLOWED SCOPES", dashed=True)
    b += msg(112, 492, 272, "QUESTION·SCOPE")
    b += self_msg(496, 320, "BUILD EVIDENCE")
    b += msg(500, 684, 384, "EVIDENCE PACK")
    b += msg(692, 880, 432, "TRACE", dashed=True, open_=True)
    b += msg(684, 500, 480, "OPTIONS + REFS", dashed=True)
    b += self_msg(496, 528, "VALIDATE REFS")
    b += msg(492, 112, 592, "CITED OPTIONS", color=ACCENT)
    b += actors_md(A)
    b += legend(660, 1000, SEQ_LEGEND)
    write("ai-design-sequence", "Sequence", "Grounded cross-platform design",
          "Sequence: the architect UI authorizes projects A and B with Cerbos, a scoped retriever builds an evidence pack and sends it "
          "through LiteLLM, which traces to Langfuse and returns options with references that are validated before cited options reach the UI.",
          1000, 704, b)


# ---------------------------------------------------------------- 6. Milestones (Gantt)
def milestones():
    months = ["NOV", "DEC", "JAN 27", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG"]
    b = ""
    for i, m in enumerate(months):
        x = 200 + 76 * i
        b += f'<line x1="{x}" y1="64" x2="{x}" y2="352" stroke="rgba(45,49,66,0.08)" stroke-width="0.8"/>'
        b += f'<text x="{x+38}" y="56" fill="{MUTED}" font-size="8" font-family="{MONO}" text-anchor="middle" letter-spacing="0.1em">{m}</text>\n'
    b += f'<line x1="200" y1="64" x2="960" y2="64" stroke="rgba(45,49,66,0.20)" stroke-width="0.8"/>\n'
    zones = [(72, 96, "DISCOVERY"), (176, 176, "DELIVERY")]
    for y, h, lab in zones:
        b += (f'<rect x="16" y="{y}" width="952" height="{h}" rx="8" fill="rgba(45,49,66,0.02)" stroke="rgba(45,49,66,0.10)" stroke-width="0.8"/>'
              f'<text x="28" y="{y+14}" fill="rgba(45,49,66,0.45)" font-size="7" font-family="{MONO}" letter-spacing="0.14em">{lab}</text>\n')
    rows = [(88, "M0 · Design partners", 240, 292, None, False), (128, "Skeleton + spikes", 240, 292, None, False),
            (192, "M1 · Proof of value", 292, 468, "phases 01–03", True), (232, "M2 · Drift + traceability", 468, 612, "phases 04–05", False),
            (272, "M3 · Grounded AI", 612, 752, "phase 06", False), (312, "M4 · Enterprise beta", 752, 956, "phase 07", False)]
    for y, name, x1, x2, inner, focal in rows:
        b += f'<text x="32" y="{y+24}" fill="{INK}" font-size="12" font-weight="600" font-family="{SANS}">{name}</text>'
        fill, stroke, tc = ("rgba(235,108,54,0.12)", ACCENT, ACCENT) if focal else ("rgba(79,93,117,0.15)", MUTED, INK)
        b += f'<rect x="{x1}" y="{y+8}" width="{x2-x1}" height="24" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
        if inner:
            b += f'<text x="{x1+8}" y="{y+24}" fill="{tc}" font-size="9" font-family="{MONO}" letter-spacing="0.04em">{inner}</text>'
        b += "\n"
    b += f'<line x1="220" y1="64" x2="220" y2="356" stroke="{MUTED}" stroke-width="1" stroke-dasharray="4,3"/>'
    b += label(220, 380, "TODAY")
    b += legend(392, 1000, [("line-accent:", "go / no-go: proof of value"), ("line", "milestone"), ("line:dash", "today")])
    write("milestones", "Gantt", "Delivery milestones",
          "Gantt chart of indicative milestones from November 2026 to August 2027: design-partner discovery and the walking skeleton, "
          "then proof of value (phases 01–03), drift and traceability, grounded AI and an enterprise beta.",
          1000, 436, b)


if __name__ == "__main__":
    for f in (how_it_works, system_context, containers, drift_sequence, ai_sequence, milestones):
        f()
    print("built", sorted(p.name for p in OUT.glob("*.html")))
