#!/usr/bin/env python3
"""Generate apps/api/archtwin/flags/catalog.yaml from the normative docs/feature-flags/FLAG_CATALOG.md (task 4.1)."""
import re
import sys
from pathlib import Path

import yaml

root = Path(__file__).resolve().parents[1]
md = (root / "docs/feature-flags/FLAG_CATALOG.md").read_text()
flags = []
for line in md.splitlines():
    m = re.match(r"\|\s*`([a-z0-9_.\-]+)`\s*\|\s*`(true|false)`\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|", line)
    if m:
        k, d, phase, scope, enf = m.groups()
        flags.append({"key": k, "default": d == "true", "phase": phase.strip(), "scope": scope.strip(),
                      "enforcement": enf.strip(), "immutable": scope.strip() == "immutable-security"})
out = root / "apps/api/archtwin/flags/catalog.yaml"
text = yaml.safe_dump({"generated_from": "docs/feature-flags/FLAG_CATALOG.md", "flags": flags}, sort_keys=False)
if "--check" in sys.argv:
    sys.exit(0 if out.read_text() == text else "catalog.yaml is stale: run scripts/gen-flag-catalog.py")
out.write_text(text)
print(f"{len(flags)} flags")
