"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { api } from "@/lib/api";
import { qk } from "@/lib/query";
import { formatCents } from "@/lib/money";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { Phase2Banner } from "@/components/phase2-banner";
import { Input } from "@/ui";

function Row({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5">
      <span className="text-sm" style={{ color: strong ? "var(--foreground)" : "var(--muted-foreground)" }}>{label}</span>
      <span className={`tabular-nums ${strong ? "text-sm font-semibold" : "text-sm"}`}>{value}</span>
    </div>
  );
}

export default function BudgetsPage() {
  const [month, setMonth] = useState(format(new Date(), "yyyy-MM"));
  const sts = useQuery({ queryKey: qk.safeToSpend(month), queryFn: () => api.safeToSpend(month) });
  const report = useQuery({ queryKey: qk.report(month), queryFn: () => api.report(month) });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Presupuestos"
        subtitle={month}
        action={<Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="w-40" />}
      />
      <Phase2Banner>Asignar a sobres y manejar presupuestos llega en la Fase 2 (requiere endpoints del backend).</Phase2Banner>

      {sts.isError && <ErrorState message="No se pudo cargar disponible para gastar" onRetry={() => sts.refetch()} />}

      {sts.data && (
        <div className="space-y-4 rounded-lg border p-5" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
          <div>
            <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>Disponible para gastar</p>
            <p className="text-4xl font-bold tabular-nums tracking-tight">{formatCents(sts.data.free, "COP")}</p>
          </div>
          <hr style={{ borderColor: "var(--border)" }} />
          <div>
            <Row label="Ingreso previsto" value={formatCents(sts.data.income_forecast, "COP")} />
            <Row label="Comprometido" value={formatCents(sts.data.committed, "COP")} />
            <Row label="Asignado a sobres" value={formatCents(sts.data.assigned_envelopes, "COP")} />
            <Row label="Libre" value={formatCents(sts.data.free, "COP")} strong />
          </div>
          {sts.data.committed_breakdown.length > 0 && (
            <>
              <hr style={{ borderColor: "var(--border)" }} />
              <div className="space-y-1">
                <p className="text-xs font-medium uppercase tracking-wider" style={{ color: "var(--muted-foreground)" }}>Comprometido</p>
                {sts.data.committed_breakdown.map((c, i) => (
                  <Row key={`${c.name}-${c.date}-${i}`} label={`${c.name} · ${c.date}`} value={formatCents(c.amount, "COP")} />
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {report.data && report.data.envelopes.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-medium" style={{ color: "var(--muted-foreground)" }}>Sobres</h2>
          <div className="overflow-hidden rounded-lg border" style={{ borderColor: "var(--border)" }}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--muted-foreground)" }}>
                  <th className="px-3 py-2.5 text-left text-xs font-medium">Categoría</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium">Asignado</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium">Gastado</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium">Disponible</th>
                </tr>
              </thead>
              <tbody>
                {report.data.envelopes.map((e) => (
                  <tr key={e.category} className="border-t" style={{ borderColor: "var(--border)" }}>
                    <td className="px-3 py-2.5">{e.category}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums" style={{ color: "var(--muted-foreground)" }}>{formatCents(e.allocated, "COP")}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums" style={{ color: "var(--muted-foreground)" }}>{formatCents(e.spent, "COP")}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums font-medium" style={{ color: e.status === "over" ? "var(--expense)" : "var(--income)" }}>
                      {formatCents(e.available, "COP")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
