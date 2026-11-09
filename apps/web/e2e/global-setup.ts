/** Creates (once) the project the UI smoke test browses: ArchTwin scanning its own repository (mounted at /sources/archtwin). */
const API = process.env.ARCHTWIN_E2E_API ?? "http://localhost:8200/api/v1";
const KC = process.env.ARCHTWIN_E2E_KEYCLOAK ?? "http://localhost:8280/realms/archtwin/protocol/openid-connect/token";
export const SELF_PROJECT = "ArchTwin (self)";

async function call<T>(token: string, method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(API + path, { method, headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
                                      body: body === undefined ? undefined : JSON.stringify(body) });
  if (!r.ok) throw new Error(`${method} ${path} -> ${r.status} ${await r.text()}`);
  return r.status === 204 ? (undefined as T) : r.json() as Promise<T>;
}

export default async function globalSetup() {
  const tok = await fetch(KC, { method: "POST", body: new URLSearchParams({ grant_type: "password", client_id: "archtwin-cli", username: "admin", password: "admin" }) });
  const token = (await tok.json()).access_token as string;
  await call(token, "GET", "/me");
  const projects = await call<{ id: string; title: string }[]>(token, "GET", "/projects");
  let p = projects.find((x) => x.title === SELF_PROJECT);
  if (!p) {
    p = await call<{ id: string; title: string }>(token, "POST", "/projects", { title: SELF_PROJECT, purpose: "UI smoke test: the platform scanning its own repository" });
    const c = await call<{ id: string }>(token, "POST", `/projects/${p.id}/connectors`, { kind: "git", name: "archtwin", config: { path: "/sources/archtwin", name: "archtwin" } });
    await call(token, "POST", `/projects/${p.id}/connectors/${c.id}/scan`, {});
  }
  for (let i = 0; i < 90; i++) {                       // wait for the first snapshot (scan -> graph build)
    const snaps = await call<unknown[]>(token, "GET", `/projects/${p.id}/snapshots`);
    if (snaps.length) return;
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error("no snapshot for the smoke-test project after 180s");
}
