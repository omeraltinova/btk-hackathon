import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * `cn` — merges Tailwind classes with conflict resolution.
 *
 * Standard shadcn helper; lets components combine variant classes with
 * caller-supplied overrides without duplicate utility classes.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
