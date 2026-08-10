"use client"

import { Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"
import { Button } from "@/ui"

/**
 * Theme switch.
 *
 * Dark is the app default, so an unresolved theme (server render, before
 * hydration) counts as dark. `suppressHydrationWarning` on the icon absorbs the
 * brief server/client glyph mismatch when the persisted theme is light.
 */
export function ThemeToggle({ className = "" }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme()
  const isDark = resolvedTheme !== "light"

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon-sm"
      aria-label={isDark ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className={`text-muted-foreground ${className}`}
    >
      <span suppressHydrationWarning className="grid place-items-center">
        {isDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
      </span>
    </Button>
  )
}
