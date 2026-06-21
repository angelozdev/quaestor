"use client";

import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme();

  // Dark is the default, so treat "unresolved" (server / pre-hydration) as dark.
  // `suppressHydrationWarning` on the icon absorbs the brief server/client glyph
  // mismatch when the persisted theme is light.
  const isDark = resolvedTheme !== "light";

  return (
    <button
      type="button"
      aria-label={isDark ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className={`grid size-7 place-items-center rounded-md transition-colors hover:bg-[var(--accent)] ${className}`}
      style={{ color: "var(--muted-foreground)" }}
    >
      <span suppressHydrationWarning className="grid place-items-center">
        {isDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
      </span>
    </button>
  );
}
