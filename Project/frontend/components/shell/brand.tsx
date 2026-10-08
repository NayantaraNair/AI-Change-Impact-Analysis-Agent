import { cn } from "@/lib/utils";

/** Concentric rings around a core: a change and how far it reaches. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className={cn("size-6", className)}>
      <circle cx="12" cy="12" r="10.5" fill="none" stroke="var(--line-strong)" strokeWidth="1" />
      <circle cx="12" cy="12" r="6.5" fill="none" stroke="var(--impact-med)" strokeOpacity="0.7" strokeWidth="1.25" />
      <circle cx="12" cy="12" r="2.75" fill="var(--impact-high)" />
    </svg>
  );
}
