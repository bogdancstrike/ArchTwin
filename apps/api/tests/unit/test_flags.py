"""AT-FEATURE_FLAGS-001..003: precedence, immutable security invariants, catalog in sync, no unregistered keys in code."""
import re
import subprocess
import sys
from pathlib import Path

from archtwin.flags.service import catalog, evaluate

O, P = "org-1", "proj-1"


def ov(key, kind, sid, value, enforce=False):
    return {"flag_key": key, "scope_kind": kind, "scope_id": sid, "value": value, "enforce": enforce}


def test_defaults_are_off_for_optional_modules():
    assert evaluate("module.drift-engine", O, P, []) == (False, "default")


def test_security_invariants_cannot_be_disabled():
    for k in ("security.oidc_required", "security.cerbos_required", "security.audit_required"):
        assert evaluate(k, O, P, [ov(k, "org", O, False), ov("security.emergency_kill_switch", "global", "", True)])[0] is True


def test_project_override_beats_org_override():
    o = [ov("module.drift-engine", "org", O, True), ov("module.drift-engine", "project", P, False)]
    assert evaluate("module.drift-engine", O, P, o) == (False, "project_override")


def test_enforced_org_policy_beats_project():
    o = [ov("module.drift-engine", "org", O, False, enforce=True), ov("module.drift-engine", "project", P, True)]
    assert evaluate("module.drift-engine", O, P, o) == (False, "org_policy")


def test_kill_switch_turns_optional_functionality_off():
    o = [ov("module.drift-engine", "project", P, True), ov("security.emergency_kill_switch", "org", O, True)]
    assert evaluate("module.drift-engine", O, P, o) == (False, "emergency_off:org")


def test_other_org_overrides_do_not_apply():
    assert evaluate("module.drift-engine", O, P, [ov("module.drift-engine", "org", "other-org", True)])[0] is False


def test_unregistered_flag_is_off():
    assert evaluate("module.nope", O, P, []) == (False, "unregistered")


def test_catalog_generated_from_docs_is_current():
    root = Path(__file__).resolve().parents[4]
    r = subprocess.run([sys.executable, str(root / "scripts/gen-flag-catalog.py"), "--check"], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr or r.stdout


def test_code_references_only_registered_flags():
    src = Path(__file__).resolve().parents[2] / "archtwin"
    keys = set()
    flag_rx = r"""["']((?:module|connector|connectors|ai|drift|docs|security|ui|search|architecture|projects)\.[a-z0-9_.\-]+)["']"""
    for f in src.rglob("*.py"):
        text = f.read_text()
        # flag call sites: flags.require/enabled(...), `flag = "..."`, MODULE_FLAG / PILOT_FLAGS tables, KILL_SWITCH
        for m in re.finditer(r"(?:flags\.(?:require|enabled)|_on|on)\(([^)]*)\)|flag\s*=\s*([^\n]+)|MODULE_FLAG\s*=\s*\{([^}]*)\}|PILOT_FLAGS\s*=\s*\[([^\]]*)\]", text, re.DOTALL):
            keys |= set(re.findall(flag_rx, " ".join(x for x in m.groups() if x)))
    known = set(catalog())
    unknown = {k for k in keys if k not in known and not k.endswith((".py", ".yaml"))}
    assert not unknown, unknown
