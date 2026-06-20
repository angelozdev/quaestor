"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { api } from "@/lib/api";
import { qk } from "@/lib/query";
import { formatCents } from "@/lib/money";
import { MoneyAmount } from "@/components/money-amount";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";

const CARD_STYLE = {
  background: "var(--card)",
  boxShadow: "0 1px 3px rgba(0,0,0,0.05), 0 0 0 1px rgba(0,0,0,0.07)",
  borderRadius: "var(--radius)",
} as const;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h2 className="text-sm font-medium" style={{ color: "var(--muted-foreground)" }}>{title}</h2>
      <div className="p-5" style={CARD_STYLE}>{children}</div>
    </div>
  );
}

function Row({
  label,
  children,
  faint = false,
}: {
  label: string;
  children: React.ReactNode;
  faint?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5">
      <span className="text-sm" style={{ color: faint ? "var(--muted-foreground)" : "var(--foreground)" }}>
        {label}
      </span>
      {children}
    </div>
  );
}

export default function ReportsPage() {
  const [month, setMonth] = useState(format(new Date(), "yyyy-MM"));
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: qk.report(month),
    queryFn: () => api.report(month),
  });

  return (
    <div className="space-y-8">
      <PageHeader
        title="Reportes"
        subtitle={month}
        action={
          <input
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="rounded-md px-3 py-1.5 text-sm outline-none transition-colors w-40"
            style={{
              background: "var(--input)",
              border: "1px solid var(--border)",
              color: "var(--foreground)",
              colorScheme: "light",
            }}
            onFocus={(e) => (e.target.style.borderColor = "var(--foreground)")}
            onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
          />
        }
      />

      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-28 rounded-lg animate-pulse"
              style={{ background: "var(--muted)" }}
            />
          ))}
        </div>
      )}

      {isError && <ErrorState message="No se pudo cargar el reporte" onRetry={() => refetch()} />}

      {data && (
        <div className="space-y-6 animate-fade-up">

          {/* Neto */}
          <Section title="Resultado del mes">
            <div className="space-y-4">
              <div className="space-y-0.5">
                <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>Neto</p>
                <p
                  className="text-4xl font-bold tabular-nums tracking-tight"
                  style={{ color: data.net >= 0 ? "var(--income)" : "var(--expense)" }}
                >
                  {formatCents(data.net, "COP")}
                </p>
              </div>
              <hr style={{ borderColor: "var(--border)" }} />
              <div className="space-y-1">
                <Row label="Ingresos">
                  <MoneyAmount cents={data.income} currency="COP" type="income" className="text-sm font-medium" />
                </Row>
                <Row label="Gastos" faint>
                  <MoneyAmount cents={data.expense} currency="COP" type="expense" className="text-sm font-medium" />
                </Row>
              </div>
              {data.drift_mom && (
                <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                  vs {data.drift_mom.prev_month} →{" "}
                  <span style={{ color: data.drift_mom.net_abs >= 0 ? "var(--income)" : "var(--expense)" }}>
                    {data.drift_mom.net_abs >= 0 ? "+" : ""}
                    {formatCents(data.drift_mom.net_abs, "COP")}
                  </span>
                </p>
              )}
            </div>
          </Section>

          {/* Sobres */}
          {data.envelopes.length > 0 && (
            <Section title="Sobres">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: "var(--muted-foreground)" }}>
                    <th className="text-left pb-3 font-medium text-xs">Categoría</th>
                    <th className="text-right pb-3 font-medium text-xs">Asignado</th>
                    <th className="text-right pb-3 font-medium text-xs">Gastado</th>
                    <th className="text-right pb-3 font-medium text-xs">Disponible</th>
                  </tr>
                </thead>
                <tbody>
                  {data.envelopes.map((e) => (
                    <tr
                      key={e.category}
                      className="border-t"
                      style={{ borderColor: "var(--border)" }}
                    >
                      <td className="py-2.5 text-sm">{e.category}</td>
                      <td className="py-2.5 text-right tabular-nums text-sm" style={{ color: "var(--muted-foreground)" }}>
                        {formatCents(e.allocated, "COP")}
                      </td>
                      <td className="py-2.5 text-right tabular-nums text-sm" style={{ color: "var(--muted-foreground)" }}>
                        {formatCents(e.spent, "COP")}
                      </td>
                      <td
                        className="py-2.5 text-right tabular-nums text-sm font-medium"
                        style={{ color: e.status === "over" ? "var(--expense)" : "var(--income)" }}
                      >
                        {formatCents(e.available, "COP")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>
          )}

          {/* Por categoría */}
          {data.by_category.length > 0 && (
            <Section title="Por categoría">
              <div className="space-y-1">
                {data.by_category.map((c) => (
                  <Row key={c.category} label={c.category} faint>
                    <div className="flex items-baseline gap-3 shrink-0">
                      <span className="text-sm font-medium tabular-nums">
                        {formatCents(c.total, "COP")}
                      </span>
                      <span className="text-xs w-9 text-right" style={{ color: "var(--muted-foreground)" }}>
                        {c.pct.toFixed(1)}%
                      </span>
                    </div>
                  </Row>
                ))}
              </div>
            </Section>
          )}

          {/* Por grupo */}
          {data.by_group.length > 0 && (
            <Section title="Por grupo">
              <div className="space-y-1">
                {data.by_group.map((g) => (
                  <Row key={g.group} label={g.group} faint>
                    <div className="flex items-baseline gap-3 shrink-0">
                      <span className="text-sm font-medium tabular-nums">
                        {formatCents(g.total, "COP")}
                      </span>
                      <span className="text-xs w-9 text-right" style={{ color: "var(--muted-foreground)" }}>
                        {g.pct.toFixed(1)}%
                      </span>
                    </div>
                  </Row>
                ))}
              </div>
            </Section>
          )}

          {/* Cierre */}
          <Section title="Disponible para gastar · cierre">
            <div className="space-y-4">
              <p className="text-3xl font-bold tabular-nums tracking-tight">
                {formatCents(data.safe_to_spend.free, "COP")}
              </p>
              <hr style={{ borderColor: "var(--border)" }} />
              <div className="space-y-1">
                <Row label="Ingreso previsto" faint>
                  <span className="text-sm tabular-nums" style={{ color: "var(--muted-foreground)" }}>
                    {formatCents(data.safe_to_spend.income_forecast, "COP")}
                  </span>
                </Row>
                <Row label="Comprometido" faint>
                  <span className="text-sm tabular-nums" style={{ color: "var(--muted-foreground)" }}>
                    {formatCents(data.safe_to_spend.committed, "COP")}
                  </span>
                </Row>
                <Row label="Asignado a sobres" faint>
                  <span className="text-sm tabular-nums" style={{ color: "var(--muted-foreground)" }}>
                    {formatCents(data.safe_to_spend.assigned_envelopes, "COP")}
                  </span>
                </Row>
              </div>
            </div>
          </Section>

        </div>
      )}
    </div>
  );
}
