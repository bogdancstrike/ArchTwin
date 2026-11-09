/** Deep links that open the provider page where a credential is created, pre-filled with a read-only name and scopes
 * (like an IDE's "generate token" shortcut). Derived only from the connector configuration the user typed. */
export interface CredentialLink { href: string; label: string }

const enc = encodeURIComponent;

function origin(u: string | undefined): string | null {
  try { const x = new URL(String(u)); return x.protocol === "https:" || x.protocol === "http:" ? x.origin : null; } catch { return null; }
}

/** GitLab base + first project path from `url` / `projects` (URLs or group/sub/project paths). */
function gitlabTarget(cfg: Record<string, unknown>): { base: string | null; path: string | null } {
  const first = String((cfg.projects as unknown[] | undefined)?.[0] ?? (cfg.groups as unknown[] | undefined)?.[0] ?? "");
  let base = origin(cfg.url as string);
  let path: string | null = first || null;
  if (/^https?:\/\//.test(first)) {
    base = base ?? origin(first);
    path = new URL(first).pathname.split("/-/")[0].replace(/^\/+|\/+$/g, "").replace(/\.git$/, "") || null;
  }
  return { base, path };
}

function githubWeb(cfg: Record<string, unknown>): string {
  const api = origin(cfg.api_url as string);
  return !api || api === "https://api.github.com" ? "https://github.com" : api;   // GitHub Enterprise: same host as its API
}

export function newSecret(): string {
  const b = new Uint8Array(32);
  crypto.getRandomValues(b);
  return Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
}

export function credentialLinks(kind: string, cfg: Record<string, unknown>): Record<string, CredentialLink[]> {
  if (kind === "github") {
    const web = githubWeb(cfg);
    const repo = String((cfg.repos as unknown[] | undefined)?.[0] ?? "");
    const owner = repo.includes("/") ? repo.split("/")[0] : "";
    const q = `name=${enc("ArchTwin (read-only)")}&description=${enc("ArchTwin connector: read-only")}&expires_in=90` +
      (owner && owner !== "owner" ? `&target_name=${enc(owner)}` : "") + "&contents=read&issues=read&pull_requests=read&metadata=read";
    return {
      token: [{ href: `${web}/settings/personal-access-tokens/new?${q}`, label: "Create fine-grained token on GitHub" }],
      webhook_secret: repo.includes("/") && repo !== "owner/name" ? [{ href: `${web}/${repo}/settings/hooks/new`, label: "Open repository webhooks" }] : [],
    };
  }
  if (kind === "gitlab" || (kind === "git" && cfg.url && origin(cfg.url as string) !== "https://github.com")) {
    const t = kind === "gitlab" ? gitlabTarget(cfg) : { base: origin(cfg.url as string), path: null };
    if (kind === "git" && cfg.url) {
      try { t.path = new URL(String(cfg.url)).pathname.replace(/^\/+|\/+$/g, "").replace(/\.git$/, "") || null; } catch { /* ignore */ }
    }
    if (!t.base || t.base.includes("example.com")) return {};
    const scopes = kind === "gitlab" ? "read_api,read_repository" : "read_repository";
    const token: CredentialLink[] = [{ href: `${t.base}/-/user_settings/personal_access_tokens?name=${enc("ArchTwin (read-only)")}&scopes=${scopes}`,
      label: "Create personal access token on GitLab" }];
    if (t.path) token.push({ href: `${t.base}/${t.path}/-/settings/access_tokens`, label: "or a project access token (Reporter)" });
    return { token, webhook_secret: t.path ? [{ href: `${t.base}/${t.path}/-/hooks`, label: "Open project webhooks" }] : [] };
  }
  if (kind === "git" && origin(cfg.url as string) === "https://github.com") {
    return { token: [{ href: `https://github.com/settings/personal-access-tokens/new?name=${enc("ArchTwin (read-only)")}&expires_in=90&contents=read&metadata=read`,
      label: "Create fine-grained token on GitHub" }] };
  }
  if (kind === "taiga") {
    const raw = String(cfg.url ?? "");
    const web = origin(raw);
    const slug = (cfg.project as string) || raw.match(/\/project\/([^/]+)/)?.[1];
    if (!web || web.includes("example.com")) return {};
    return {
      password: [{ href: `${web}/user-settings/user-change-password`, label: "Taiga account settings" }],
      webhook_secret: slug ? [{ href: `${web}/project/${slug}/admin/third-parties/webhooks`, label: "Open project webhooks (admin)" }] : [],
    };
  }
  return {};
}
