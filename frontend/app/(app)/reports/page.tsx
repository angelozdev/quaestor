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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";

export default function ReportsPage() {
  const [month, setMonth] = useState(format(new Date(), "yyyy-MM"));
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: qk.report(month),
    queryFn: () => api.report(month),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reporte mensual"
        action={
          <Input
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="w-40"
          />
        }
      />

      {isLoading && <Skeleton className="h-64 w-full" />}
      {isError && <ErrorState message="No se pudo cargar el reporte" onRetry={() => refetch()} />}

      {data && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Neto del mes</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-4xl font-bold">{formatCents(data.net, "COP")}</div>
              <div className="mt-2 flex gap-6 text-sm">
                <span>
                  Ingresos <MoneyAmount cents={data.income} currency="COP" type="income" />
                </span>
                <span>
                  Gastos <MoneyAmount cents={data.expense} currency="COP" type="expense" />
                </span>
              </div>
              {data.drift_mom && (
                <p className="mt-2 text-xs text-muted-foreground">
                  vs {data.drift_mom.prev_month}: neto {data.drift_mom.net_abs >= 0 ? "+" : ""}
                  {formatCents(data.drift_mom.net_abs, "COP")}
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Desempeño de sobres</CardTitle>
            </CardHeader>
            <CardContent>
              {data.envelopes.length > 0 ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-muted-foreground">
                      <th className="py-1">Categoría</th>
                      <th className="text-right">Asignado</th>
                      <th className="text-right">Gastado</th>
                      <th className="text-right">Disponible</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.envelopes.map((e) => (
                      <tr key={e.category} className="border-t">
                        <td className="py-1">{e.category}</td>
                        <td className="text-right tabular-nums">{formatCents(e.allocated, "COP")}</td>
                        <td className="text-right tabular-nums">{formatCents(e.spent, "COP")}</td>
                        <td
                          className={`text-right tabular-nums ${
                            e.status === "over" ? "text-red-600" : "text-green-600"
                          }`}
                        >
                          {formatCents(e.available, "COP")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-sm text-muted-foreground">Sin sobres este mes</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Por categoría</CardTitle>
            </CardHeader>
            <CardContent>
              {data.by_category.length > 0 ? (
                <ul className="space-y-1 text-sm">
                  {data.by_category.map((c) => (
                    <li key={c.category} className="flex justify-between">
                      <span>
                        {c.category}
                        {c.group ? ` · ${c.group}` : ""}
                      </span>
                      <span className="tabular-nums">
                        {formatCents(c.total, "COP")} ({c.pct.toFixed(1)}%)
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">Sin gastos</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Por grupo</CardTitle>
            </CardHeader>
            <CardContent>
              {data.by_group.length > 0 ? (
                <ul className="space-y-1 text-sm">
                  {data.by_group.map((g) => (
                    <li key={g.group} className="flex justify-between">
                      <span>{g.group}</span>
                      <span className="tabular-nums">
                        {formatCents(g.total, "COP")} ({g.pct.toFixed(1)}%)
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">Sin gastos</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Disponible para gastar (cierre)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-semibold">
                {formatCents(data.safe_to_spend.free, "COP")}
              </div>
              <div className="mt-2 grid grid-cols-2 gap-1 text-sm text-muted-foreground">
                <span>Ingreso previsto</span>
                <span className="text-right tabular-nums">
                  {formatCents(data.safe_to_spend.income_forecast, "COP")}
                </span>
                <span>Comprometido</span>
                <span className="text-right tabular-nums">
                  {formatCents(data.safe_to_spend.committed, "COP")}
                </span>
                <span>Asignado a sobres</span>
                <span className="text-right tabular-nums">
                  {formatCents(data.safe_to_spend.assigned_envelopes, "COP")}
                </span>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
