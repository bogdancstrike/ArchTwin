import { Star } from "lucide-react";
import { cn } from "@/components/ui";
import { useFavorites } from "@/lib/hooks";

export function FavoriteStar({ projectId, title, className, size = 16 }: { projectId: string; title: string; className?: string; size?: number }) {
  const { isFav, toggle } = useFavorites();
  const on = isFav(projectId);
  return <button type="button" aria-pressed={on} aria-label={on ? `Remove ${title} from favorites` : `Add ${title} to favorites`}
    title={on ? "Remove from favorites" : "Add to favorites (shown in the sidebar)"}
    onClick={(e) => { e.preventDefault(); e.stopPropagation(); void toggle(projectId); }}
    className={cn("rounded-md p-1 transition hover:bg-paper-2", on ? "text-[var(--status-warning)]" : "text-soft hover:text-ink", className)}>
    <Star size={size} fill={on ? "currentColor" : "none"} strokeWidth={on ? 1.5 : 2} />
  </button>;
}
