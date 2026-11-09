"""Git repository connector (read-only). Sources: a mounted local repository under an allowed root, or an HTTPS clone.

Any ref can be scanned without mutating the source: `git archive <ref>` is extracted into a private temp dir, so two
commits can be compared (phase-03 demo). Secret files are never read (see analyzers.common.SECRET_FILE).
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from archtwin.common.egress import EgressDenied, check_url
from archtwin.config import settings
from archtwin.connectors.analyzers.repo import analyze_repository
from archtwin.connectors.sdk import ScanResult, TestResult

REF_RX = re.compile(r"^[A-Za-z0-9._/\-~^]{1,200}$")


async def _git(*args: str, cwd: str | None = None, env: dict | None = None, timeout: float = 300) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec("git", "-c", "safe.directory=*", "-c", "core.hooksPath=/dev/null", *args, cwd=cwd,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})})
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except TimeoutError:
        proc.kill()
        raise
    return proc.returncode or 0, out, err


def _local_path(cfg: dict[str, Any]) -> Path:
    p = Path(str(cfg.get("path", ""))).resolve()
    roots = [Path(r).resolve() for r in settings().source_roots]
    if not any(p == r or str(p).startswith(str(r) + os.sep) for r in roots):
        raise ValueError(f"path must be under an allowed source root ({', '.join(map(str, roots))})")
    if not p.is_dir():
        raise ValueError(f"{p} is not a directory")
    return p


def _safe_extract(tar_bytes_path: Path, dest: Path) -> None:
    with tarfile.open(tar_bytes_path) as tf:
        tf.extractall(dest, filter="data")         # rejects absolute paths, '..', links outside dest


class GitRepoConnector:
    kind = "git"
    flag = "connector.git"
    manifest = {"name": "Git repository", "category": "code", "origin": "static", "scopes": ["contents:read"], "freshness_sla_s": 86400,
                "webhooks": ["push"],
                "config": {"path": "mounted repository path under /sources (local)", "url": "https HTTPS clone URL (remote)",
                           "ref": "branch, tag or commit (default HEAD)", "name": "system name override"},
                "secret": {"token": "optional read-only token for private HTTPS repositories",
                           "webhook_secret": "optional — enables signed push webhooks (X-ArchTwin-Signature)"}}

    async def test(self, cfg: dict[str, Any], secret: dict[str, Any]) -> TestResult:
        try:
            if cfg.get("path"):
                p = _local_path(cfg)
                rc, out, _ = await _git("rev-parse", "HEAD", cwd=str(p))
                return TestResult(ok=True, scopes=["filesystem:read (mounted read-only)"],
                                  details={"path": str(p), "head": out.decode().strip() if rc == 0 else "not a git repository"},
                                  warnings=[] if rc == 0 else ["not a git repository: refs/commit comparison unavailable"])
            url = str(cfg.get("url", ""))
            check_url(url)
            rc, out, err = await _git("ls-remote", "--symref", self._auth_url(url, secret), "HEAD", timeout=30)
            if rc != 0:
                return TestResult(ok=False, warnings=[err.decode()[:300].replace(secret.get("token", "\0"), "[REDACTED]")])
            return TestResult(ok=True, scopes=["contents:read"], details={"head": out.decode().split()[0] if out else ""})
        except (ValueError, EgressDenied) as e:
            return TestResult(ok=False, warnings=[str(e)])

    @staticmethod
    def _auth_url(url: str, secret: dict[str, Any]) -> str:
        tok = secret.get("token")
        return url.replace("https://", f"https://x-access-token:{tok}@", 1) if tok and url.startswith("https://") else url

    async def scan(self, cfg: dict[str, Any], secret: dict[str, Any], ref: str | None) -> ScanResult:
        ref = ref or cfg.get("ref") or "HEAD"
        if not REF_RX.match(ref):
            raise ValueError("invalid ref")
        work = Path(tempfile.mkdtemp(prefix="archtwin-scan-"))
        try:
            if cfg.get("path"):
                src = _local_path(cfg)
                name = cfg.get("name") or src.name
                rc, out, _ = await _git("rev-parse", "--verify", f"{ref}^{{commit}}", cwd=str(src))
                if rc == 0:
                    revision = out.decode().strip()
                    tarp = work / "src.tar"
                    rc2, _, err = await _git("archive", "--format=tar", "-o", str(tarp), revision, cwd=str(src))
                    if rc2 != 0:
                        raise RuntimeError(f"git archive failed: {err.decode()[:200]}")
                    tree = work / "tree"
                    tree.mkdir()
                    _safe_extract(tarp, tree)
                    root = tree
                else:
                    if ref != "HEAD":
                        raise ValueError(f"ref {ref!r} not found")
                    revision, root = "working-tree", src          # not a git repo: scan files as they are
            else:
                url = str(cfg["url"])
                check_url(url)
                name = cfg.get("name") or Path(url.rstrip("/").removesuffix(".git")).name
                root = work / "clone"
                args = ["clone", "--quiet", "--no-tags", "--filter=blob:limit=1m", self._auth_url(url, secret), str(root)]
                if ref == "HEAD":
                    args[1:1] = ["--depth", "1"]
                rc, _, err = await _git(*args, timeout=600)
                if rc != 0:
                    raise RuntimeError("clone failed: " + err.decode()[:200].replace(secret.get("token", "\0"), "[REDACTED]"))
                if ref != "HEAD":
                    rc, _, err = await _git("checkout", "--quiet", ref, cwd=str(root))
                    if rc != 0:
                        raise ValueError(f"ref {ref!r} not found")
                revision = (await _git("rev-parse", "HEAD", cwd=str(root)))[1].decode().strip()
            result = await asyncio.to_thread(analyze_repository, root, revision, name)
            result.stats["ref"] = ref
            return result
        finally:
            shutil.rmtree(work, ignore_errors=True)
