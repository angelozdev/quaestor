export function Phase2Banner({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="rounded-lg border px-4 py-3 text-sm"
      style={{ borderColor: "var(--border)", background: "var(--muted)", color: "var(--muted-foreground)" }}
    >
      {children}
    </div>
  );
}
