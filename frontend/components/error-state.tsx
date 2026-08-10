import { Button } from "@/ui"

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="space-y-3 py-6 text-center">
      <p className="text-sm" style={{ color: "var(--expense)" }}>
        {message}
      </p>
      <Button type="button" size="sm" variant="outline" onClick={onRetry}>
        Reintentar
      </Button>
    </div>
  )
}
