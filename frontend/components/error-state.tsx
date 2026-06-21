export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="space-y-3 py-6 text-center">
      <p className="text-sm" style={{ color: "var(--expense)" }}>
        {message}
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="text-xs px-3 py-1.5 rounded-md border transition-colors"
        style={{ borderColor: "var(--border)", color: "var(--muted-foreground)" }}
        onMouseEnter={(e) => (e.currentTarget.style.color = "var(--foreground)")}
        onMouseLeave={(e) => (e.currentTarget.style.color = "var(--muted-foreground)")}
      >
        Reintentar
      </button>
    </div>
  )
}
