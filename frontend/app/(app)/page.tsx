"use client";

import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { api } from "@/lib/api";
import { qk } from "@/lib/query";
import { formatCents } from "@/lib/money";
import { MoneyAmount } from "@/components/money-amount";
import { ToPayWidget } from "@/components/to-pay-widget";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const MONTH = format(new Date(), "yyyy-MM");

export default function DashboardPage() {
  const sts = useQuery({ queryKey: qk.safeToSpend(MONTH), queryFn: () => api.safeToSpend(MONTH) });
  const report = useQuery({ queryKey: qk.report(MONTH), queryFn: () => api.report(MONTH) });
  const goals = useQuery({ queryKey: qk.goalsProgress(), queryFn: () => api.goalsProgress() });
  const accounts = useQuery({ queryKey: qk.accounts(), queryFn: () => api.accounts() });

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" subtitle={MONTH} />

      <Card>
        <CardHeader>
          <CardTitle>Disponible para gastar</CardTitle>
        </CardHeader>
        <CardContent>
          {sts.isLoading ? (
            <Skeleton className="h-10 w-48" />
          ) : sts.data ? (
            <div className="text-4xl font-bold">{formatCents(sts.data.free, "COP")}</div>
          ) : (
            <p className="text-sm text-red-600">No disponible</p>
          )}
        </CardContent>
      </Card>

      <ToPayWidget />

      <div className="grid gap-6 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Ingresos · Gastos · Neto</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            {report.isLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : report.data ? (
              <>
                <div className="flex justify-between">
                  <span>Ingresos</span>
                  <MoneyAmount cents={report.data.income} currency="COP" type="income" />
                </div>
                <div className="flex justify-between">
                  <span>Gastos</span>
                  <MoneyAmount cents={report.data.expense} currency="COP" type="expense" />
                </div>
                <div className="flex justify-between font-semibold">
                  <span>Neto</span>
                  <span className="tabular-nums">{formatCents(report.data.net, "COP")}</span>
                </div>
              </>
            ) : (
              <p className="text-sm text-red-600">No disponible</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Saldos</CardTitle>
          </CardHeader>
          <CardContent>
            {accounts.isLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : accounts.data && accounts.data.length > 0 ? (
              <ul className="space-y-1">
                {accounts.data
                  .filter((a) => !a.archived)
                  .map((a) => (
                    <li key={a.id} className="flex justify-between">
                      <span>{a.name}</span>
                      <span className="tabular-nums">{formatCents(a.balance, a.currency)}</span>
                    </li>
                  ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">Sin cuentas</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Metas</CardTitle>
          </CardHeader>
          <CardContent>
            {goals.isLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : goals.data && goals.data.length > 0 ? (
              <ul className="space-y-2">
                {goals.data.map((g) => {
                  const pct = g.target_amount
                    ? Math.min(100, Math.round((g.saved / g.target_amount) * 100))
                    : null;
                  return (
                    <li key={g.goal_id}>
                      <div className="flex justify-between text-sm">
                        <span>{g.name}</span>
                        <span className="tabular-nums">
                          {formatCents(g.saved, "COP")}
                          {g.target_amount ? ` / ${formatCents(g.target_amount, "COP")}` : ""}
                        </span>
                      </div>
                      {pct !== null && (
                        <div className="mt-1 h-2 rounded bg-muted">
                          <div className="h-2 rounded bg-green-600" style={{ width: `${pct}%` }} />
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">Sin metas activas</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Sobres en riesgo</CardTitle>
          </CardHeader>
          <CardContent>
            {report.isLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : report.data ? (
              report.data.envelopes.filter((e) => e.status === "over").length > 0 ? (
                <ul className="space-y-1">
                  {report.data.envelopes
                    .filter((e) => e.status === "over")
                    .map((e) => (
                      <li key={e.category} className="flex justify-between">
                        <span>{e.category}</span>
                        <MoneyAmount cents={Math.abs(e.available)} currency="COP" type="expense" />
                      </li>
                    ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">Todos los sobres en orden ✅</p>
              )
            ) : (
              <p className="text-sm text-red-600">No disponible</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
