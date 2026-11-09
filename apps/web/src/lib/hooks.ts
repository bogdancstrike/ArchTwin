import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "./api";
import type { Me } from "./types";

export const useMe = () => useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me"), staleTime: 30_000 });

export function useApi<T>(key: QueryKey, path: string | null, opts: { refetchInterval?: number | false; enabled?: boolean; keepPrevious?: boolean } = {}) {
  return useQuery({ queryKey: key, queryFn: () => api<T>(path!), enabled: !!path && opts.enabled !== false, refetchInterval: opts.refetchInterval,
    placeholderData: opts.keepPrevious ? keepPreviousData : undefined });
}

export function useAction<TIn, TOut = unknown>(fn: (v: TIn) => Promise<TOut>, invalidate: QueryKey[] = [], ok?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => { invalidate.forEach((k) => qc.invalidateQueries({ queryKey: k })); if (ok) toast.success(ok); },
    onError: (e: Error) => toast.error(e.message),
  });
}
