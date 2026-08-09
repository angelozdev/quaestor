import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

/**
 * Merge Tailwind class names, resolving conflicts so the last one wins.
 *
 * This is the design system's own copy on purpose: `ui/` is app-agnostic and must
 * not depend on app code (see docs/adr/0002). App code imports it from `@/ui`,
 * and `components.json` points shadcn's `utils` alias straight here.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
