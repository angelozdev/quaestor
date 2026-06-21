"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, type Account, type AccountType } from "@/lib/api";
import { qk, invalidate } from "@/lib/query";
import { formatCents } from "@/lib/money";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { EntityFormDialog, type Field, type FormValues } from "@/components/entity-form-dialog";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Button } from "@/ui";

const TYPE_OPTIONS = [
  { value: "debit", label: "Débito" },
  { value: "credit", label: "Crédito" },
  { value: "cash", label: "Efectivo" },
  { value: "savings", label: "Ahorros" },
];
const TYPE_LABEL: Record<string, string> = Object.fromEntries(TYPE_OPTIONS.map((o) => [o.value, o.label]));
const CURRENCY_OPTIONS = [
  { value: "COP", label: "COP" },
  { value: "USD", label: "USD" },
];

const CREATE_FIELDS: Field[] = [
  { kind: "text", name: "name", label: "Nombre", required: true },
  { kind: "select", name: "type", label: "Tipo", options: TYPE_OPTIONS, required: true },
  { kind: "select", name: "currency", label: "Moneda", options: CURRENCY_OPTIONS, required: true },
  { kind: "money", name: "balance", label: "Saldo inicial", currencyFrom: "currency" },
];
const EDIT_FIELDS: Field[] = [
  { kind: "text", name: "name", label: "Nombre", required: true },
  { kind: "select", name: "type", label: "Tipo", options: TYPE_OPTIONS, required: true },
];

export default function AccountsPage() {
  const qc = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const [archiving, setArchiving] = useState<Account | null>(null);

  const list = useQuery({
    queryKey: qk.accounts(showArchived),
    queryFn: () => api.listAccounts(showArchived),
  });

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error");
  const done = (msg: string) => { toast.success(msg); invalidate(qc, "accountWrite"); };

  const create = useMutation({
    mutationFn: (v: FormValues) =>
      api.createAccount({
        name: String(v.name),
        type: v.type as AccountType,
        currency: String(v.currency),
        balance: (v.balance as number) ?? 0,
      }),
    onSuccess: () => { done("Cuenta creada"); setCreating(false); },
    onError: onErr,
  });
  const update = useMutation({
    mutationFn: (v: FormValues) =>
      api.updateAccount(editing!.id, { name: String(v.name), type: v.type as AccountType }),
    onSuccess: () => { done("Cuenta actualizada"); setEditing(null); },
    onError: onErr,
  });
  const archive = useMutation({
    mutationFn: (id: number) => api.archiveAccount(id),
    onSuccess: () => { done("Cuenta archivada"); setArchiving(null); },
    onError: onErr,
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Cuentas" action={<Button onClick={() => setCreating(true)}>Nueva</Button>} />

      <label className="flex items-center gap-2 text-sm" style={{ color: "var(--muted-foreground)" }}>
        <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
        Mostrar archivadas
      </label>

      {list.isError && <ErrorState message="No se pudieron cargar las cuentas" onRetry={() => list.refetch()} />}
      {list.data && list.data.length === 0 && <EmptyState message="Sin cuentas" />}

      {list.data && list.data.length > 0 && (
        <div className="overflow-hidden rounded-lg border" style={{ borderColor: "var(--border)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ color: "var(--muted-foreground)" }}>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Nombre</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Tipo</th>
                <th className="px-3 py-2.5 text-right text-xs font-medium">Saldo</th>
                <th className="w-40 px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {list.data.map((a) => (
                <tr key={a.id} className="border-t" style={{ borderColor: "var(--border)" }}>
                  <td className="px-3 py-2.5">
                    <span className="flex items-center gap-2">
                      {a.name} <StatusBadge kind="archived" value={a.archived} />
                    </span>
                  </td>
                  <td className="px-3 py-2.5" style={{ color: "var(--muted-foreground)" }}>
                    {TYPE_LABEL[a.type] ?? a.type}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatCents(a.balance, a.currency)}</td>
                  <td className="px-3 py-2.5 text-right">
                    {!a.archived && (
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => setEditing(a)}>Editar</Button>
                        <Button variant="ghost" size="sm" onClick={() => setArchiving(a)}>Archivar</Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <EntityFormDialog
        open={creating}
        onOpenChange={setCreating}
        title="Nueva cuenta"
        fields={CREATE_FIELDS}
        initialValues={{ name: "", type: "debit", currency: "COP", balance: null }}
        pending={create.isPending}
        onSubmit={(v) => create.mutate(v)}
      />
      <EntityFormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title="Editar cuenta"
        fields={EDIT_FIELDS}
        initialValues={{ name: editing?.name ?? "", type: editing?.type ?? "debit" }}
        pending={update.isPending}
        onSubmit={(v) => update.mutate(v)}
      />
      <ConfirmDialog
        open={archiving !== null}
        onOpenChange={(o) => !o && setArchiving(null)}
        title="Archivar cuenta"
        description={`Se archivará "${archiving?.name}". No podrás reactivarla desde la app (Fase 2).`}
        confirmLabel="Archivar"
        pending={archive.isPending}
        onConfirm={() => archiving && archive.mutate(archiving.id)}
      />
    </div>
  );
}
