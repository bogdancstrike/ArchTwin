/** One-shot query parameters used by deep links (command palette, Home activity): `?new=1`, `?flow=<id>`, `?doc=<id>`.
 *  Read once when a page mounts; the parameter is then removed so a reload or back navigation does not re-trigger it. */
export function takeParam(name: string): string | null {
  const url = new URL(window.location.href);
  const v = url.searchParams.get(name);
  if (v !== null) {
    url.searchParams.delete(name);
    window.history.replaceState(window.history.state, "", url.pathname + (url.search ? url.search : "") + url.hash);
  }
  return v;
}

export const takeFlag = (name: string) => takeParam(name) !== null;
