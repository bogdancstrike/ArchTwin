import { useSyncExternalStore } from "react";

/** App theme (light | dark), shared by the top-bar toggle, the command palette and theme-aware renderers. */
export type Theme = "light" | "dark";
const KEY = "at-theme";
const listeners = new Set<() => void>();

function read(): Theme {
  try { return localStorage.getItem(KEY) === "dark" ? "dark" : "light"; } catch { return "light"; }
}

let current: Theme = read();
document.documentElement.setAttribute("data-theme", current);

export function setTheme(t: Theme) {
  current = t;
  document.documentElement.setAttribute("data-theme", t);
  try { localStorage.setItem(KEY, t); } catch { /* storage unavailable */ }
  listeners.forEach((l) => l());
}

export const toggleTheme = () => setTheme(current === "dark" ? "light" : "dark");

export function useTheme(): Theme {
  return useSyncExternalStore((l) => { listeners.add(l); return () => { listeners.delete(l); }; }, () => current);
}
