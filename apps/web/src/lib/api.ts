import { getToken, renewToken } from "./auth";

export interface Problem { title: string; status: number; code: string; detail?: string | null; [k: string]: unknown }

export class ApiError extends Error {
  constructor(public problem: Problem) {
    super(problem.detail ? `${problem.title}: ${problem.detail}` : problem.title);
  }
  get status() { return this.problem.status; }
  get code() { return this.problem.code; }
}

let orgId: string | null = localStorage.getItem("at-org");
export const setOrg = (id: string | null) => { orgId = id; if (id) localStorage.setItem("at-org", id); else localStorage.removeItem("at-org"); };
export const getOrg = () => orgId;

type Init = Omit<RequestInit, "body"> & { json?: unknown; body?: BodyInit; idempotent?: boolean; text?: boolean; headers?: Record<string, string> };

export async function api<T = unknown>(path: string, init: Init = {}): Promise<T> {
  const go = async () => {
    const h: Record<string, string> = { ...(init.headers ?? {}) };
    const t = getToken();
    if (t) h.Authorization = `Bearer ${t}`;
    if (orgId) h["X-ArchTwin-Org"] = orgId;
    if (init.json !== undefined) h["Content-Type"] = "application/json";
    if (init.idempotent) h["Idempotency-Key"] = crypto.randomUUID();
    return fetch(`/api/v1${path}`, { ...init, headers: h, body: init.json !== undefined ? JSON.stringify(init.json) : init.body });
  };
  let r = await go();
  if (r.status === 401 && (await renewToken())) r = await go();
  if (!r.ok) {
    let p: Problem;
    try { p = await r.json(); } catch { p = { title: r.statusText || "Request failed", status: r.status, code: "AT-HTTP" }; }
    if (r.status === 404 && p.code === "AT-NOT-FOUND" && orgId && path === "/me") setOrg(null);
    throw new ApiError(p);
  }
  if (r.status === 204) return undefined as T;
  if (init.text) return (await r.text()) as T;
  const ct = r.headers.get("content-type") ?? "";
  return (ct.includes("json") ? r.json() : r.text()) as Promise<T>;
}

export async function download(path: string, filename: string) {
  const r = await fetch(`/api/v1${path}`, { headers: { Authorization: `Bearer ${getToken()}`, ...(orgId ? { "X-ArchTwin-Org": orgId } : {}) } });
  if (!r.ok) { let p: Problem; try { p = await r.json(); } catch { p = { title: r.statusText, status: r.status, code: "AT-HTTP" }; } throw new ApiError(p); }
  const blob = await r.blob();
  const a = document.createElement("a");
  const named = /filename="([^"]+)"/.exec(r.headers.get("content-disposition") ?? "")?.[1];       // the server's name wins
  a.href = URL.createObjectURL(blob); a.download = named ?? filename; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
