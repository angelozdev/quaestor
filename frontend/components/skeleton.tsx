import { Skeleton } from "@/ui/components/skeleton"

// Raised-contrast wrapper so skeletons read clearly in dark mode.
const TONE = { background: "var(--muted-foreground)", opacity: 0.14 } as const

export function SkeletonText({
  lines = 3,
  className = "",
}: {
  lines?: number
  className?: string
}) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => {
        const w = i === lines - 1 ? "60%" : "100%"
        return (
          // biome-ignore lint/suspicious/noArrayIndexKey: skeleton placeholders are a fixed-length list that never reorders
          <Skeleton key={i} className="h-4" style={{ ...TONE, width: w }} />
        )
      })}
    </div>
  )
}

export function SkeletonCard({ className = "" }: { className?: string }) {
  return <Skeleton className={`h-28 w-full rounded-lg ${className}`} style={TONE} />
}

export function SkeletonRows({ rows = 6, className = "" }: { rows?: number; className?: string }) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: rows }).map((_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: skeleton placeholders are a fixed-length list that never reorders
        <Skeleton key={i} className="h-9 w-full" style={TONE} />
      ))}
    </div>
  )
}

export function SkeletonBlock({ className = "" }: { className?: string }) {
  return <Skeleton className={className} style={TONE} />
}
