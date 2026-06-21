"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  api, ApiError, type Recurring, type Account,
  type IntervalUnit, type RecurringMode, type RecurringType,
} from "@/lib/api";
import { qk, invalidate } from "@/lib/query";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { Phase2Banner } from "@/components/phase2-banner";
import { MoneyInput } from "@/components/money-input";
import { MoneyAmount } from "@/components/money-amount";
import { EntitySelect } from "@/components/entity-select";
import { Dialog, DialogPopup, DialogTitle, Select, Input, Label, Button } from "@/ui";

const TYPE_ITEMS = [
  { value: "expense", label: "Gasto" },
  { value: "income", label: "Ingreso" },
];
const MODE_ITEMS = [
  { value: "auto", label: "Automático" },
  { value: "manual", label: "Manual" },
];
const UNIT_ITEMS = [
  { value: "day", label: "Día(s)" },
  { value: "week", label: "Semana(s)" },
  { value: "month", label: "Mes(es)" },
  { value: "year", label: "Año(s)" },
];

const UNIT_SINGULAR: Record<IntervalUnit, string> = { day: "día", week: "semana", month: "mes", year: "año" };
const UNIT_PLURAL: Record<IntervalUnit, string> = { day: "días", week: "semanas", month: "meses", year: "años" };

function intervalLabel(unit: IntervalUnit, count: number): string {
  if (count === 1) return `Cada ${UNIT_SINGULAR[unit]}`;
  return `Cada ${count} ${UNIT_PLURAL[unit]}`;
}

function currencyOf(accounts: Account[] | undefined, id: number | null): string {
  if (id === null) return "COP";
  return accounts?.find((a) => a.id === id)?.currency ?? "COP";
}

export default function RecurringPage() {
  const qc = useQueryClient();
  const accounts = useQuery({ queryKey: qk.accounts(false), queryFn: () => api.listAccounts(false) });
  const list = useQuery({ queryKey: qk.recurring(), queryFn: () => api.listRecurring() });

  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState<string | null>("expense");
  const [mode, setMode] = useState<string | null>("manual");
  const [accountId, setAccountId] = useState<number | null>(null);
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [amount, setAmount] = useState<number | null>(null);
  const [unit, setUnit] = useState<string | null>("month");
  const [count, setCount] = useState<number | null>(1);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [payee, setPayee] = useState("");

  const [skipping, setSkipping] = useState<Recurring | null>(null);
  const [skipDate, setSkipDate] = useState("");

  const currency = currencyOf(accounts.data, accountId);
  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error");
  const done = (msg: string) => { toast.success(msg); invalidate(qc, "recurringWrite"); };

  const create = useMutation({
    mutationFn: () =>
      api.createRecurring({
        name,
        type: type as RecurringType,
        mode: mode as RecurringMode,
        amount: amount!,
        account_id: accountId!,
        interval_unit: unit as IntervalUnit,
        interval_count: count ?? 1,
        start_date: startDate,
        end_date: endDate || null,
        currency,
        category_id: categoryId,
        payee: payee || undefined,
      }),
    onSuccess: () => {
      done("Recurrente creado");
      setCreating(false);
      setName(""); setAmount(null); setStartDate(""); setEndDate(""); setPayee("");
      setAccountId(null); setCategoryId(null); setCount(1);
    },
    onError: onErr,
  });

  const skip = useMutation({
    mutationFn: () => api.skipRecurring(skipping!.id, skipDate),
    onSuccess: () => { done("Ocurrencia omitida"); setSkipping(null); setSkipDate(""); },
    onError: onErr,
  });

  const invalid = !name || amount === null || accountId === null || !unit || !startDate || !type || !mode;

  return (
    <div className="space-y-6">
      <PageHeader title="Recurrentes" action={<Button onClick={() => setCreating(true)}>Nuevo</Button>} />

      <Phase2Banner>Editar y eliminar recurrentes llega en la Fase 2 (requiere endpoints del backend).</Phase2Banner>

      {list.isError && <ErrorState message="No se pudieron cargar los recurrentes" onRetry={() => list.refetch()} />}
      {list.data && list.data.length === 0 && <EmptyState message="Sin recurrentes" />}

      {list.data && list.data.length > 0 && (
        <div className="overflow-hidden rounded-lg border" style={{ borderColor: "var(--border)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ color: "var(--muted-foreground)" }}>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Nombre</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Frecuencia</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Modo</th>
                <th className="px-3 py-2.5 text-right text-xs font-medium">Monto</th>
                <th className="w-24 px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {list.data.map((r) => (
                <tr key={r.id} className="border-t" style={{ borderColor: "var(--border)" }}>
                  <td className="px-3 py-2.5 font-medium">{r.name}</td>
                  <td className="px-3 py-2.5" style={{ color: "var(--muted-foreground)" }}>
                    {intervalLabel(r.interval_unit, r.interval_count)}
                  </td>
                  <td className="px-3 py-2.5"><StatusBadge kind="mode" value={r.mode} /></td>
                  <td className="px-3 py-2.5 text-right">
                    <MoneyAmount cents={r.amount} currency={r.currency} type={r.type} />
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    <Button variant="ghost" size="sm" onClick={() => setSkipping(r)}>Omitir</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogPopup className="max-w-lg">
          <DialogTitle>Nuevo recurrente</DialogTitle>
          <form onSubmit={(e) => { e.preventDefault(); if (!invalid) create.mutate(); }} className="space-y-4">
            <div className="space-y-1.5"><Label>Nombre *</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5"><Label>Tipo *</Label><Select value={type} onValueChange={setType} items={TYPE_ITEMS} /></div>
              <div className="space-y-1.5"><Label>Modo *</Label><Select value={mode} onValueChange={setMode} items={MODE_ITEMS} /></div>
            </div>
            <div className="space-y-1.5">
              <Label>Cuenta *</Label>
              <EntitySelect value={accountId} onChange={setAccountId} queryKey={qk.accounts(false)} queryFn={() => api.listAccounts(false)} />
            </div>
            <div className="space-y-1.5"><Label>Monto * ({currency})</Label><MoneyInput currency={currency} value={amount} onChange={setAmount} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5"><Label>Cada (cantidad) *</Label>
                <Input type="number" min={1} value={count === null ? "" : String(count)} onChange={(e) => setCount(e.target.value === "" ? null : Number(e.target.value))} />
              </div>
              <div className="space-y-1.5"><Label>Unidad *</Label><Select value={unit} onValueChange={setUnit} items={UNIT_ITEMS} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5"><Label>Inicio *</Label><Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></div>
              <div className="space-y-1.5"><Label>Fin (opcional)</Label><Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></div>
            </div>
            <div className="space-y-1.5">
              <Label>Categoría</Label>
              <EntitySelect value={categoryId} onChange={setCategoryId} queryKey={qk.categories(false)} queryFn={() => api.listCategories(false)} allowNullLabel="Sin categoría" />
            </div>
            <div className="space-y-1.5"><Label>Beneficiario</Label><Input value={payee} onChange={(e) => setPayee(e.target.value)} /></div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setCreating(false)}>Cancelar</Button>
              <Button type="submit" disabled={invalid || create.isPending}>{create.isPending ? "…" : "Crear"}</Button>
            </div>
          </form>
        </DialogPopup>
      </Dialog>

      {/* Skip dialog */}
      <Dialog open={skipping !== null} onOpenChange={(o) => !o && setSkipping(null)}>
        <DialogPopup className="max-w-sm">
          <DialogTitle>Omitir ocurrencia</DialogTitle>
          {skipping && (
            <form onSubmit={(e) => { e.preventDefault(); if (skipDate) skip.mutate(); }} className="space-y-4">
              <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                Indica la fecha de la ocurrencia de &quot;{skipping.name}&quot; que quieres omitir.
              </p>
              <div className="space-y-1.5"><Label>Fecha de la ocurrencia *</Label><Input type="date" value={skipDate} onChange={(e) => setSkipDate(e.target.value)} /></div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setSkipping(null)}>Cancelar</Button>
                <Button type="submit" disabled={!skipDate || skip.isPending}>{skip.isPending ? "…" : "Omitir"}</Button>
              </div>
            </form>
          )}
        </DialogPopup>
      </Dialog>
    </div>
  );
}
