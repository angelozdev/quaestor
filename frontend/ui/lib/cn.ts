import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

/**
 * Merge Tailwind class names, resolving conflicts so the last one wins.
 *
 * This is the design system's own copy on purpose: `ui/` is app-agnostic and must
 * not depend on app code (see docs/adr/0002). The app re-exports this from
 * `@/lib/utils` for convenience.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
