import { Badge } from "@/ui"

type Variant = "default" | "secondary" | "destructive" | "outline" | "ghost"

const TX: Record<string, { label: string; variant: Variant }> = {
  planned: { label: "Planeado", variant: "outline" },
  posted: { label: "Registrado", variant: "secondary" },
  skipped: { label: "Omitido", variant: "ghost" },
}
const MODE: Record<string, { label: string; variant: Variant }> = {
  auto: { label: "Automático", variant: "secondary" },
  manual: { label: "Manual", variant: "outline" },
}
const GOAL: Record<string, { label: string; variant: Variant }> = {
  active: { label: "Activa", variant: "secondary" },
  reached: { label: "Cumplida", variant: "secondary" },
  paused: { label: "Pausada", variant: "ghost" },
}

export function StatusBadge({
  kind,
  value,
}: {
  kind: "tx" | "mode" | "archived" | "onTrack" | "goal"
  value: string | boolean
}) {
  let label = String(value)
  let variant: Variant = "outline"

  if (kind === "tx") {
    const m = TX[String(value)]
    if (m) ({ label, variant } = m)
  } else if (kind === "mode") {
    const m = MODE[String(value)]
    if (m) ({ label, variant } = m)
  } else if (kind === "goal") {
    const m = GOAL[String(value)]
    if (m) ({ label, variant } = m)
  } else if (kind === "archived") {
    if (value !== true) return null
    label = "Archivado"
    variant = "ghost"
  } else if (kind === "onTrack") {
    if (value === true) ({ label, variant } = { label: "En camino", variant: "secondary" })
    else ({ label, variant } = { label: "Atrasado", variant: "destructive" })
  }

  return <Badge variant={variant}>{label}</Badge>
}
