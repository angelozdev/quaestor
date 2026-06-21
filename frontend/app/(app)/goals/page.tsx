"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { qk } from "@/lib/query";
import { formatCents } from "@/lib/money";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { Phase2Banner } from "@/components/phase2-banner";

export default function GoalsPage() {
  const goals = useQuery({ queryKey: qk.goalsProgress(), queryFn: () => api.goalsProgress() });

  return (
    <div className="space-y-6">
      <PageHeader title="Metas" />
      <Phase2Banner>Crear y contribuir a metas llega en la Fase 2 (requiere endpoints del backend).</Phase2Banner>

      {goals.isError && <ErrorState message="No se pudieron cargar las metas" onRetry={() => goals.refetch()} />}
      {goals.data && goals.data.length === 0 && <EmptyState message="Sin metas activas" />}

      {goals.data && goals.data.length > 0 && (
        <div className="space-y-3">
          {goals.data.map((g) => {
            const pct = g.target_amount ? Math.min(100, Math.round((g.saved / g.target_amount) * 100)) : null;
            return (
              <div key={g.goal_id} className="space-y-3 rounded-lg border p-5" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium">{g.name}</span>
                  {g.on_track !== null && <StatusBadge kind="onTrack" value={g.on_track} />}
                </div>

                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span style={{ color: "var(--muted-foreground)" }}>
                    {formatCents(g.saved, "COP")}{g.target_amount !== null && ` / ${formatCents(g.target_amount, "COP")}`}
                  </span>
                  {pct !== null && <span className="tabular-nums">{pct}%</span>}
                </div>

                {pct !== null && (
                  <div className="h-1.5 overflow-hidden rounded-full" style={{ background: "var(--muted)" }}>
                    <div className="h-full rounded-full" style={{ width: `${pct}%`, background: "var(--foreground)" }} />
                  </div>
                )}

                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs" style={{ color: "var(--muted-foreground)" }}>
                  {g.monthly_required !== null && <span>Requerido/mes: {formatCents(g.monthly_required, "COP")}</span>}
                  {g.remaining !== null && <span>Restante: {formatCents(g.remaining, "COP")}</span>}
                  {g.eta && <span>ETA: {g.eta}</span>}
                  {g.deadline && <span>Fecha límite: {g.deadline}</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
