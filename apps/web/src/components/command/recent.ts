/** Recently opened command-palette destinations (per browser, best effort). */
export interface RecentItem { id: string; label: string; hint?: string; kind: string; to: string; search?: Record<string, string> }

const KEY = "archtwin.cmdk.recent";
const MAX = 6;

export function readRecent(): RecentItem[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(v) ? v.filter((x) => x && typeof x.id === "string" && typeof x.to === "string").slice(0, MAX) : [];
  } catch { return []; }
}

export function pushRecent(item: RecentItem): void {
  try {
    localStorage.setItem(KEY, JSON.stringify([item, ...readRecent().filter((x) => x.id !== item.id)].slice(0, MAX)));
  } catch { /* storage unavailable */ }
}
