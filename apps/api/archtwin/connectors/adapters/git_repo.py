"""Git repository / local directory connector (read-only).

Sources:
  * a mounted local directory under an allowed source root (ARCHTWIN_LOCAL_SOURCE_ROOTS), which may be
      - a single Git repository (scanned at any ref with `git archive`, so commits can be compared),
      - a folder of Git repositories, e.g. `qsint/backend` holding one repository per service (each child repository is
        scanned at HEAD as its own software system), or
      - a plain folder without Git (scanned as it is on disk, revision `working-tree`);
  * an HTTPS clone (self-hosted GitLab, Gitea, …).

`content` picks the analyzers: `auto` (code + conventional doc folders + ADR folders anywhere), `code`, or `docs` (every
Markdown/text/diagram source anywhere, ADRs, contracts; no runtime wiring) — for a documentation or architecture folder.
PDF/DOCX files are parsed through docling-serve when the `documents` profile runs, otherwise counted and skipped.
The source is never mutated; secret files are never read (see analyzers.common.SECRET_FILE).
"""
from __future__ import annotations

import asyncio
import fnmatch
import os
import re
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from archtwin.common.egress import EgressDenied, check_url
from archtwin.common.logging import log
from archtwin.config import settings
from archtwin.connectors.analyzers.common import SKIP_DIRS
from archtwin.connectors.analyzers.repo import CONTENT_MODES, analyze_repository
from archtwin.connectors.sdk import DocumentOut, ScanResult, TestResult

REF_RX = re.compile(r"^[A-Za-z0-9._/\-~^]{1,200}$")
USER_RX = re.compile(r"^[A-Za-z0-9._\-]{1,100}$")
MAX_REPOS = 100
MAX_DEPTH = 4
MAX_BINARY_DOCS = 50


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
        raise ValueError(f"path must be under an allowed source root ({', '.join(map(str, roots))}); "
                         "mount the directory read-only and add it to ARCHTWIN_SOURCE_WORKSPACE")
    if not p.is_dir():
        raise ValueError(f"{p} is not a directory")
    return p


def _is_repo(p: Path) -> bool:
    return (p / ".git").exists()


def discover_repos(root: Path, include: list[str] | None = None, exclude: list[str] | None = None) -> list[str]:
    """Relative paths of Git repositories below `root` (not descending into a repository), filtered by glob patterns."""
    found: list[str] = []
    stack = [(root, 0)]
    while stack:
        d, depth = stack.pop()
        try:
            children = sorted((c for c in d.iterdir() if c.is_dir() and not c.is_symlink()), reverse=True)
        except OSError:
            continue
        for c in children:
            if c.name in SKIP_DIRS or c.name.startswith("."):
                continue
            if _is_repo(c):
                found.append(str(c.relative_to(root)))
            elif depth + 1 < MAX_DEPTH:
                stack.append((c, depth + 1))
    found.sort()
    if include:
        found = [r for r in found if any(fnmatch.fnmatch(r, g) or fnmatch.fnmatch(Path(r).name, g) for g in include)]
    if exclude:
        found = [r for r in found if not any(fnmatch.fnmatch(r, g) or fnmatch.fnmatch(Path(r).name, g) for g in exclude)]
    return found


MAX_BROWSE = 500
DOC_MARKERS = ("docs", "doc", "documentation", "adr", "adrs", "architecture", "openspec")


def browse(path: str | None) -> dict[str, Any]:
    """Folder picker for the local-directory datasource: subfolders of an allowed source root (names only, never file
    contents). Hidden/dependency folders are skipped; symlinks are not followed out of the roots."""
    roots = [Path(r).resolve() for r in settings().source_roots]
    roots = [r for r in dict.fromkeys(roots) if r.is_dir()]
    places = [{"name": r.name or str(r), "path": str(r)} for r in roots]
    if not path:
        return {"path": "", "name": "Sources", "parent": None, "root": None, "places": places, "layout": None, "markers": [],
                "folders": [{"name": str(r), "path": str(r), "is_repo": _is_repo(r), "has_children": True} for r in roots]}
    p = _local_path({"path": path})
    root = max((r for r in roots if p == r or str(p).startswith(str(r) + os.sep)), key=lambda r: len(str(r)))
    folders: list[dict[str, Any]] = []
    try:
        entries = sorted((c for c in p.iterdir() if c.is_dir() and not c.is_symlink()), key=lambda c: c.name.lower())
    except OSError as e:
        raise ValueError(f"cannot list {p}: {e.strerror}") from e
    for c in entries:
        if c.name in SKIP_DIRS or c.name.startswith("."):
            continue
        try:
            has_children = any(g.is_dir() and not g.name.startswith(".") and g.name not in SKIP_DIRS for g in c.iterdir())
        except OSError:
            has_children = False
        folders.append({"name": c.name, "path": str(c), "is_repo": _is_repo(c), "has_children": has_children})
        if len(folders) >= MAX_BROWSE:
            break
    repos_here = sum(1 for f in folders if f["is_repo"])
    names = {f["name"].lower() for f in folders}
    try:
        files = [f.name for f in p.iterdir() if f.is_file()]
    except OSError:
        files = []
    markers = sorted({m for m in DOC_MARKERS if m in names}
                     | ({"compose"} if any(re.fullmatch(r"(docker-)?compose(\.[\w\-]+)?\.ya?ml", f) for f in files) else set())
                     | ({"markdown"} if any(f.lower().endswith((".md", ".mdx")) for f in files) else set()))
    layout = "repository" if _is_repo(p) else "folder of repositories" if repos_here else "plain directory"
    return {"path": str(p), "name": p.name, "parent": str(p.parent) if p != root else "", "root": str(root), "places": places,
            "layout": layout, "repositories": repos_here, "markers": markers, "truncated": len(folders) >= MAX_BROWSE,
            "folders": folders, "suggested_content": "docs" if not _is_repo(p) and not repos_here and "markdown" in markers else "auto"}


def _safe_extract(tar_bytes_path: Path, dest: Path) -> None:
    with tarfile.open(tar_bytes_path) as tf:
        tf.extractall(dest, filter="data")         # rejects absolute paths, '..', links outside dest


def _content(cfg: dict[str, Any]) -> str:
    c = str(cfg.get("content") or "auto")
    if c not in CONTENT_MODES:
        raise ValueError(f"content must be one of {', '.join(CONTENT_MODES)}")
    return c


class GitRepoConnector:
    kind = "git"
    flag = "connector.git"
    manifest = {"name": "Local directory / Git repository", "category": "code", "origin": "static", "scopes": ["contents:read"],
                "freshness_sla_s": 86400, "webhooks": ["push"],
                "config": {"path": "local directory under a mounted source root: one repo, a folder of repos, or plain files",
                           "url": "https HTTPS clone URL (remote)", "content": "auto | code | docs",
                           "ref": "branch, tag or commit (single repository; default HEAD)", "name": "system name override",
                           "include": ["glob of child repositories to scan (folder of repos)"], "exclude": ["glob to skip"],
                           "system_names": {"child/repo": "system name override"}},
                "secret": {"token": "optional read-only token for private HTTPS repositories",
                           "username": "optional clone username for the token (GitLab: oauth2)",
                           "webhook_secret": "optional — enables signed push webhooks (X-ArchTwin-Signature)"}}

    async def test(self, cfg: dict[str, Any], secret: dict[str, Any]) -> TestResult:
        try:
            _content(cfg)
            if cfg.get("path"):
                p = _local_path(cfg)
                if _is_repo(p):
                    rc, out, _ = await _git("rev-parse", "HEAD", cwd=str(p))
                    return TestResult(ok=True, scopes=["filesystem:read (mounted read-only)"],
                                      details={"path": str(p), "layout": "repository", "head": out.decode().strip() if rc == 0 else "no commits"})
                repos = discover_repos(p, cfg.get("include"), cfg.get("exclude"))
                if repos:
                    warnings = [f"{len(repos)} repositories found; only the first {MAX_REPOS} are scanned"] if len(repos) > MAX_REPOS else []
                    return TestResult(ok=True, scopes=["filesystem:read (mounted read-only)"], warnings=warnings,
                                      details={"path": str(p), "layout": "folder of repositories", "repositories": repos[:MAX_REPOS]})
                return TestResult(ok=True, scopes=["filesystem:read (mounted read-only)"],
                                  details={"path": str(p), "layout": "plain directory"},
                                  warnings=["not a git repository: files are scanned as they are; refs/commit comparison unavailable"])
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
        user = str(secret.get("username") or "x-access-token")
        if not USER_RX.match(user):
            raise ValueError("invalid clone username")
        return url.replace("https://", f"https://{user}:{tok}@", 1) if tok and url.startswith("https://") else url

    async def scan(self, cfg: dict[str, Any], secret: dict[str, Any], ref: str | None) -> ScanResult:
        ref = ref or cfg.get("ref") or "HEAD"
        if not REF_RX.match(ref):
            raise ValueError("invalid ref")
        content = _content(cfg)
        work = Path(tempfile.mkdtemp(prefix="archtwin-scan-"))
        try:
            if cfg.get("path"):
                src = _local_path(cfg)
                if not _is_repo(src):
                    repos = discover_repos(src, cfg.get("include"), cfg.get("exclude"))
                    if repos:
                        if ref != "HEAD":
                            raise ValueError("a ref applies to a single repository: add the child directory as its own source to pick a ref")
                        return await self._scan_many(src, repos, cfg, content, work)
                    if ref != "HEAD":
                        raise ValueError(f"ref {ref!r} not found (not a git repository)")
                    result = await asyncio.to_thread(analyze_repository, src, "working-tree", cfg.get("name") or src.name, content)
                    await self._binary_docs(result, src)
                    result.stats["ref"] = ref
                    return result
                root, revision = await self._archive(src, ref, work / "tree")
                result = await asyncio.to_thread(analyze_repository, root, revision, cfg.get("name") or src.name, content)
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
                result = await asyncio.to_thread(analyze_repository, root, revision, name, content)
            await self._binary_docs(result, root)
            result.stats["ref"] = ref
            return result
        finally:
            shutil.rmtree(work, ignore_errors=True)

    @staticmethod
    async def _archive(src: Path, ref: str, dest: Path) -> tuple[Path, str]:
        """Extract `ref` of the local repository `src` into `dest` (never touching the source)."""
        rc, out, _ = await _git("rev-parse", "--verify", f"{ref}^{{commit}}", cwd=str(src))
        if rc != 0:
            if ref != "HEAD":
                raise ValueError(f"ref {ref!r} not found")
            return src, "working-tree"                     # repository without commits: scan files as they are
        revision = out.decode().strip()
        dest.mkdir(parents=True)
        tarp = dest.with_suffix(".tar")
        rc2, _, err = await _git("archive", "--format=tar", "-o", str(tarp), revision, cwd=str(src))
        if rc2 != 0:
            raise RuntimeError(f"git archive failed: {err.decode()[:200]}")
        _safe_extract(tarp, dest)
        tarp.unlink(missing_ok=True)
        return dest, revision

    async def _scan_many(self, src: Path, repos: list[str], cfg: dict[str, Any], content: str, work: Path) -> ScanResult:
        """A folder of repositories: each child repository is its own system, scanned at HEAD; results are merged."""
        names = dict(cfg.get("system_names") or {})
        out = ScanResult()
        revs: list[str] = []
        if len(repos) > MAX_REPOS:
            out.warnings.append(f"{len(repos)} repositories found; scanned the first {MAX_REPOS} (narrow with include/exclude)")
            out.complete = False
        for i, rel in enumerate(repos[:MAX_REPOS]):
            system = names.get(rel) or Path(rel).name
            try:
                root, revision = await self._archive(src / rel, "HEAD", work / f"r{i}")
                r = await asyncio.to_thread(analyze_repository, root, revision, system, content)
                await self._binary_docs(r, root)
            except Exception as e:  # noqa: BLE001 — one broken repository must not hide the others
                out.complete = False
                out.warnings.append(f"{rel}: {type(e).__name__}: {str(e)[:160]} — partial scan, its evidence is kept (not tombstoned)")
                continue
            finally:
                shutil.rmtree(work / f"r{i}", ignore_errors=True)
            out.observations += r.observations
            for d in r.documents:
                d.path = f"{rel}/{d.path}"
                out.documents.append(d)
            out.warnings += [f"{rel}: {w}" for w in r.warnings]
            out.complete = out.complete and r.complete
            revs.append(f"{rel}@{revision[:12]}")
            for k, v in r.stats.items():
                if isinstance(v, int | float):
                    out.stats[k] = out.stats.get(k, 0) + v
            cov = r.coverage or {}
            out.coverage.setdefault("prefixes", []).extend(cov.get("prefixes", []))
            out.coverage.setdefault("systems", []).extend(cov.get("systems", []))
        out.coverage["origin"] = "static"
        out.revision = ",".join(revs)[:2000]
        out.stats.update({"repositories": len(revs), "ref": "HEAD"})
        return out

    @staticmethod
    async def _binary_docs(result: ScanResult, root: Path) -> None:
        """PDF/DOCX found by the analyzer -> Markdown through docling-serve (the `documents` profile), else counted."""
        paths = [p for a in result.artifacts if a.get("kind") == "binary-documents" for p in a.get("paths", [])]
        result.artifacts = [a for a in result.artifacts if a.get("kind") != "binary-documents"]
        if not paths:
            return
        result.stats["binary_documents"] = len(paths)
        if not settings().docling_url:
            result.warnings.append(f"{len(paths)} PDF/DOCX file(s) not parsed: start the 'documents' profile (docling-serve)")
            return
        from archtwin.documents.service import parse_upload  # documents module service interface
        parsed = 0
        for rel in paths[:MAX_BINARY_DOCS]:
            try:
                data = (root / rel).read_bytes()
                mime, text, _ = await parse_upload(data, Path(rel).name)
            except Exception as e:  # noqa: BLE001 — a bad file is skipped, never fatal
                log.info("binary_doc_skipped", path=rel, error=type(e).__name__)
                continue
            result.documents.append(DocumentOut(path=rel, title=Path(rel).stem[:200], text=text, mime=mime,
                                                tags=["adr"] if re.search(r"(^|/)(adrs?|decisions?)(/|$)", rel, re.IGNORECASE) else []))
            parsed += 1
        result.stats["binary_documents_parsed"] = parsed
        if len(paths) > MAX_BINARY_DOCS:
            result.warnings.append(f"only the first {MAX_BINARY_DOCS} PDF/DOCX files were parsed")
