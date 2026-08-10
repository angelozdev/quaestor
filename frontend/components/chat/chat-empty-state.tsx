"use client"

import { Button } from "@/ui"

type Props = {
  onPick: (text: string) => void
}

const SUGGESTIONS = [
  "¿Cuánto puedo gastar este mes?",
  "Lista mis cuentas y sus saldos",
  "Dame el resumen del mes",
] as const

export function ChatEmptyState({ onPick }: Props) {
  return (
    <div className="flex flex-col items-start gap-3 px-1 py-6">
      <p className="text-lg font-semibold tracking-tight" style={{ color: "var(--foreground)" }}>
        Pregúntale a tu asistente
      </p>
      <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
        Puede leer tus cuentas, transacciones y fondos.
      </p>
      <div className="mt-1 flex flex-wrap gap-2">
        {SUGGESTIONS.map((text) => (
          <Button
            key={text}
            type="button"
            size="sm"
            variant="outline"
            aria-label={`Enviar sugerencia: ${text}`}
            onClick={() => onPick(text)}
            className="rounded-full border-primary bg-transparent"
          >
            {text}
          </Button>
        ))}
      </div>
    </div>
  )
}
