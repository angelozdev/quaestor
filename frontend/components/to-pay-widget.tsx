"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { startOfWeek, endOfWeek, startOfMonth, endOfMonth, format } from "date-fns";
import { api } from "@/lib/api";
import { qk } from "@/lib/query";
import { formatCents } from "@/lib/money";
import { MoneyAmount } from "@/components/money-amount";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";

type Scope = "week" | "month";

function windowFor(scope: Scope) {
  const now = new Date();
  const [since, until] =
    scope === "week"
      ? [startOfWeek(now, { weekStartsOn: 1 }), endOfWeek(now, { weekStartsOn: 1 })]
      : [startOfMonth(now), endOfMonth(now)];
  return { since: format(since, "yyyy-MM-dd"), until: format(until, "yyyy-MM-dd") };
}

export function ToPayWidget() {
  const qc = useQueryClient();
  const [scope, setScope] = useState<Scope>("week");
  const { since, until } = windowFor(scope);

  const query = useQuery({
    queryKey: qk.toPay(since, until),
    queryFn: () => api.toPay(since, until),
  });

  const markPaid = useMutation({
    mutationFn: (id: number) => api.confirmPayment(id),
    onSuccess: () => {
      toast.success("Pago confirmado");
      qc.invalidateQueries({ queryKey: ["planned"] });
      qc.invalidateQueries({ queryKey: ["reports"] });
      qc.invalidateQueries({ queryKey: ["accounts"] });
      qc.invalidateQueries({ queryKey: ["budgets"] });
    },
    onError: (e: unknown) =>
      toast.error(e instanceof Error ? e.message : "No se pudo confirmar el pago"),
  });

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Por pagar</CardTitle>
        <Tabs value={scope} onValueChange={(v) => setScope(v as Scope)}>
          <TabsList>
            <TabsTrigger value="week">Esta semana</TabsTrigger>
            <TabsTrigger value="month">Este mes</TabsTrigger>
          </TabsList>
        </Tabs>
      </CardHeader>
      <CardContent className="space-y-3">
        {query.isLoading && <Skeleton className="h-24 w-full" />}
        {query.isError && (
          <ErrorState message="No se pudo cargar lo pendiente" onRetry={() => query.refetch()} />
        )}
        {query.data && (
          <>
            <div className="text-2xl font-semibold">
              {formatCents(query.data.total_base, "COP")}
            </div>
            {query.data.items.length === 0 ? (
              <EmptyState message="Nada pendiente en este periodo 🎉" />
            ) : (
              <ul className="divide-y">
                {query.data.items.map((item) => (
                  <li key={item.id} className="flex items-center justify-between py-2">
                    <div>
                      <div className="font-medium">{item.payee}</div>
                      <div className="text-xs text-muted-foreground">{item.date}</div>
                    </div>
                    <div className="flex items-center gap-3">
                      <MoneyAmount cents={item.amount} currency={item.currency} />
                      <Button
                        size="sm"
                        disabled={markPaid.isPending}
                        onClick={() => markPaid.mutate(item.id)}
                      >
                        Pagar
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
