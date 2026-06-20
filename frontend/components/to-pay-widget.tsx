"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { startOfWeek, endOfWeek, startOfMonth, endOfMonth, format } from "date-fns";
import { api } from "@/lib/api";
import { qk } from "@/lib/query";
import { formatCents } from "@/lib/money";
import { MoneyAmount } from "@/components/money-amount";
import { ErrorState } from "@/components/error-state";
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
    <div
      className="p-5 space-y-4"
      style={{
        background: "var(--card)",
        boxShadow: "0 1px 3px rgba(0,0,0,0.05), 0 0 0 1px rgba(0,0,0,0.07)",
        borderRadius: "var(--radius)",
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <p className="text-xs font-medium uppercase tracking-wider" style={{ color: "var(--muted-foreground)" }}>
          Por pagar
        </p>
        <div className="flex items-center gap-1 rounded-md p-0.5" style={{ background: "var(--muted)" }}>
          {(["week", "month"] as Scope[]).map((s) => {
            const active = scope === s;
            return (
              <button
                key={s}
                onClick={() => setScope(s)}
                className="px-2.5 py-1 text-xs rounded transition-all"
                style={{
                  background: active ? "var(--card)" : "transparent",
                  color: active ? "var(--foreground)" : "var(--muted-foreground)",
                  fontWeight: active ? 500 : 400,
                  boxShadow: active ? "0 1px 2px rgba(0,0,0,0.08)" : "none",
                }}
              >
                {s === "week" ? "Esta semana" : "Este mes"}
              </button>
            );
          })}
        </div>
      </div>

      {query.isLoading && (
        <div className="space-y-2">
          {[1, 2].map((i) => (
            <div key={i} className="h-11 rounded animate-pulse" style={{ background: "var(--muted)" }} />
          ))}
        </div>
      )}

      {query.isError && (
        <ErrorState message="No se pudo cargar lo pendiente" onRetry={() => query.refetch()} />
      )}

      {query.data && (
        <>
          <p className="text-3xl font-bold tabular-nums tracking-tight">
            {formatCents(query.data.total_base, "COP")}
          </p>

          {query.data.items.length === 0 ? (
            <p className="text-sm py-1" style={{ color: "var(--muted-foreground)" }}>
              Nada pendiente en este periodo.
            </p>
          ) : (
            <ul className="space-y-0">
              {query.data.items.map((item) => (
                <li
                  key={item.id}
                  className="flex items-center justify-between py-2.5 border-t gap-4"
                  style={{ borderColor: "var(--border)" }}
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{item.payee}</p>
                    <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>{item.date}</p>
                  </div>
                  <div className="flex items-center gap-4 shrink-0">
                    <MoneyAmount cents={item.amount} currency={item.currency} className="text-sm font-medium" />
                    <button
                      disabled={markPaid.isPending}
                      onClick={() => markPaid.mutate(item.id)}
                      className="text-xs px-3 py-1.5 rounded-md font-medium transition-colors disabled:opacity-50"
                      style={{
                        background: "var(--muted)",
                        color: "var(--foreground)",
                        border: "1px solid var(--border)",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = "var(--foreground)";
                        e.currentTarget.style.color = "var(--background)";
                        e.currentTarget.style.borderColor = "var(--foreground)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = "var(--muted)";
                        e.currentTarget.style.color = "var(--foreground)";
                        e.currentTarget.style.borderColor = "var(--border)";
                      }}
                    >
                      Marcar pagado
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
