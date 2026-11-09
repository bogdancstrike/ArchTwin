"""Feature grouping and diagram helpers shared by deterministic and AI-drafted documents.

A *feature* is the functional area an endpoint or flow belongs to, derived from its URL path or action name:
`/api/v1/category-sets/{id}` -> "Category sets", `ACTION investigations_append` -> "Investigations",
`ACTION qdata_create_investigation` -> "Investigations" (namespace `qdata` and verb `create` skipped, singular/plural merged).
Namespaces are learned from the project itself: a first segment shared by most endpoints (`/api`), or a broad prefix that
fans out into many different nouns (`qdata_*`), is skipped so the grouping stays meaningful.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable

GENERIC = {"api", "apis", "rest", "v1", "v2", "v3", "v4", "internal", "public", "private", "service", "services", "app", "http", "gate"}
VERBS = {"get", "list", "create", "update", "delete", "add", "remove", "set", "put", "post", "patch", "fetch", "find", "search", "save",
         "edit", "upsert", "append", "confirm", "download", "upload", "export", "import", "run", "start", "stop", "cancel", "send",
         "check", "count", "load", "read", "write", "do", "make", "new", "batch", "bulk", "sync", "async", "preview", "validate"}
SHARED_NAMESPACE = 0.5           # a first segment used by more than this share of all endpoints is a namespace, not a feature
BROAD_SHARE = 0.2                # ... or one used by more than this share that fans out into many nouns
BROAD_MIN = 25
BROAD_FANOUT = 4


def segments(path_or_action: str) -> list[str]:
    s = path_or_action.strip()
    if s.upper().startswith("ACTION "):
        return [w for w in re.split(r"[_\-\s.]+", s.split(" ", 1)[1].lower()) if w]
    path = s.split(" ", 1)[-1] if re.match(r"^[A-Z]+ /", s) else s
    return [p.lower() for p in path.split("/") if p and not p.startswith("{") and not p.startswith(":") and p.lower() not in GENERIC]


def titleize(seg: str) -> str:
    words = re.sub(r"[_\-]+", " ", seg).strip()
    return (words[:1].upper() + words[1:]) if words else "General"


def singular(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


class FeatureIndex:
    """Learns namespaces and labels from all endpoint paths/actions, then names the feature of any path, action or flow."""

    def __init__(self, paths: Iterable[str]):
        items = [segments(p) for p in paths]
        items = [s for s in items if s]
        n = len(items)
        firsts = Counter(s[0] for s in items)
        fan: dict[str, set[str]] = defaultdict(set)
        for s in items:
            rest = [w for w in s[1:] if w not in VERBS]
            if rest:
                fan[s[0]].add(singular(rest[0]))
        self.namespaces = {w for w, c in firsts.items() if n >= 4 and (c / n > SHARED_NAMESPACE or
                                                                         (c >= BROAD_MIN and c / n > BROAD_SHARE and len(fan[w]) >= BROAD_FANOUT))}
        forms: dict[str, Counter] = defaultdict(Counter)
        for s in items:
            w = self._head(s)
            if w:
                forms[singular(w)][w] += 1
        # label = the plural form when the project uses one ("Investigations"), else the most used form
        self.labels = {k: titleize(max(c.items(), key=lambda kv: (kv[0] != k, kv[1]))[0]) for k, c in forms.items()}

    def _head(self, segs: list[str]) -> str:
        segs = list(segs)
        while len(segs) > 1 and segs[0] in self.namespaces:
            segs = segs[1:]
        while len(segs) > 1 and segs[0] in VERBS:
            segs = segs[1:]
        return segs[0] if segs else ""

    def of(self, path_or_action: str) -> str:
        w = self._head(segments(path_or_action))
        if not w:
            return "General"
        return self.labels.get(singular(w), titleize(w))


def mermaid_label(s: str, limit: int = 48) -> str:
    s = re.sub(r'["\[\]{}()<>|#;`]', " ", str(s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return (s[: limit - 1] + "…") if len(s) > limit else (s or "?")


def mermaid_id(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", s)[:60] or "x"


def flowchart(nodes: list[tuple[str, str, str]], edges: list[tuple[str, str, str]], direction: str = "LR") -> str:
    """nodes: (id, label, shape: box|db|person|ext); edges: (from, to, label)."""
    shape = {"box": '["{}"]', "db": '[("{}")]', "person": '(["{}"])', "ext": '{{"{}"}}'}
    lines = [f"flowchart {direction}"]
    for nid, label, kind in nodes:
        lines.append(f"  {mermaid_id(nid)}{shape.get(kind, shape['box']).format(mermaid_label(label))}")
    for a, b, label in edges:
        lab = mermaid_label(label, 30)
        lines.append(f"  {mermaid_id(a)} -->|{lab}| {mermaid_id(b)}" if label else f"  {mermaid_id(a)} --> {mermaid_id(b)}")
    return "\n".join(lines)
