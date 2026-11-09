import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "./api";
import type { Me } from "./types";

export const useMe = () => useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me"), staleTime: 30_000 });

export function useApi<T>(key: QueryKey, path: string | null, opts: { refetchInterval?: number | false; enabled?: boolean; keepPrevious?: boolean } = {}) {
  return useQuery({ queryKey: key, queryFn: () => api<T>(path!), enabled: !!path && opts.enabled !== false, refetchInterval: opts.refetchInterval,
    placeholderData: opts.keepPrevious ? keepPreviousData : undefined });
}

export function useAction<TIn, TOut = unknown>(fn: (v: TIn) => Promise<TOut>, invalidate: QueryKey[] = [], ok?: string | ((r: TOut) => string)) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (r: TOut) => { invalidate.forEach((k) => qc.invalidateQueries({ queryKey: k })); if (ok) toast.success(typeof ok === "function" ? ok(r) : ok); },
    onError: (e: Error) => toast.error(e.message),
  });
}


/** Starred projects (per user, stored in preferences): the sidebar lists only these. Optimistic toggle. */
export function useFavorites() {
  const me = useMe();
  const qc = useQueryClient();
  const favs: string[] = (me.data?.preferences as { favorite_projects?: string[] } | undefined)?.favorite_projects ?? [];
  const toggle = async (id: string) => {
    const next = favs.includes(id) ? favs.filter((x) => x !== id) : [...favs, id];
    qc.setQueryData(["me"], (old: Me | undefined) => old ? { ...old, preferences: { ...old.preferences, favorite_projects: next } } : old);
    try { await api("/me/preferences", { method: "PUT", json: { favorite_projects: next } }); }
    catch (e) { void qc.invalidateQueries({ queryKey: ["me"] }); toast.error((e as Error).message); }
  };
  return { favs, isFav: (id: string) => favs.includes(id), toggle };
}
