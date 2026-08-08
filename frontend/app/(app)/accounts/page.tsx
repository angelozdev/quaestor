"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { EmptyState } from "@/components/empty-state"
import { EntityFormDialog, type Field, type FormValues } from "@/components/entity-form-dialog"
import { ErrorState } from "@/components/error-state"
import { PageHeader } from "@/components/page-header"
import { ScreenHelp } from "@/components/screen-help"
import { StatusBadge } from "@/components/status-badge"
import {
  archiveAccount,
  createAccount,
  listAccounts,
  restoreAccount,
  updateAccount,
} from "@/lib/api/accounts"
import type { Account, AccountType } from "@/lib/api/types"
import { ApiError } from "@/lib/api/types"
import { ARCHIVED_FILTER_SCHEMA } from "@/lib/filter-schemas"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { useUrlFilters } from "@/lib/use-url-filters"
import { Button } from "@/ui"

const TYPE_OPTIONS = [
  { value: "debit", label: "Débito" },
  { value: "credit", label: "Crédito" },
  { value: "cash", label: "Efectivo" },
  { value: "savings", label: "Ahorros" },
]
const TYPE_LABEL: Record<string, string> = Object.fromEntries(
  TYPE_OPTIONS.map((o) => [o.value, o.label]),
)
const CURRENCY_OPTIONS = [
  { value: "COP", label: "COP" },
  { value: "USD", label: "USD" },
]

const CREATE_FIELDS: Field[] = [
  { kind: "text", name: "name", label: "Nombre", required: true },
  { kind: "select", name: "type", label: "Tipo", options: TYPE_OPTIONS, required: true },
  { kind: "select", name: "currency", label: "Moneda", options: CURRENCY_OPTIONS, required: true },
  { kind: "money", name: "balance", label: "Saldo inicial", currencyFrom: "currency" },
]
const EDIT_FIELDS: Field[] = [
  { kind: "text", name: "name", label: "Nombre", required: true },
  { kind: "select", name: "type", label: "Tipo", options: TYPE_OPTIONS, required: true },
]

const WHAT_AN_ACCOUNT_IS = (
  <p>
    Una cuenta es donde está la plata — el banco, la tarjeta de crédito, el efectivo, los ahorros.
  </p>
)

const ACCOUNTS_HELP = (
  <>
    {WHAT_AN_ACCOUNT_IS}
    <p>
      Cada movimiento sale de una cuenta o entra a una, y el saldo se mueve solo: aquí no se edita a
      mano. El saldo inicial se pone al crearla.
    </p>
  </>
)

export default function AccountsPage() {
  const qc = useQueryClient()
  const { values, patch } = useUrlFilters(ARCHIVED_FILTER_SCHEMA)
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Account | null>(null)
  const [archiving, setArchiving] = useState<Account | null>(null)

  const list = useQuery({
    queryKey: qk.accounts(values.archived),
    queryFn: () => listAccounts(values.archived),
  })

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error")
  const done = (msg: string) => {
    toast.success(msg)
    invalidate(qc, "accountWrite")
  }

  const create = useMutation({
    mutationFn: (v: FormValues) =>
      createAccount({
        name: String(v.name),
        type: v.type as AccountType,
        currency: String(v.currency),
        balance: (v.balance as number) ?? 0,
      }),
    onSuccess: () => {
      done("Cuenta creada")
      setCreating(false)
    },
    onError: onErr,
  })
  const update = useMutation({
    mutationFn: (v: FormValues) => {
      if (!editing) throw new Error("editing account is required")
      return updateAccount(editing.id, { name: String(v.name), type: v.type as AccountType })
    },
    onSuccess: () => {
      done("Cuenta actualizada")
      setEditing(null)
    },
    onError: onErr,
  })
  const archive = useMutation({
    mutationFn: (id: number) => archiveAccount(id),
    onSuccess: () => {
      done("Cuenta archivada")
      setArchiving(null)
    },
    onError: onErr,
  })
  const restore = useMutation({
    mutationFn: (id: number) => restoreAccount(id),
    onSuccess: () => {
      done("Cuenta restaurada")
    },
    onError: onErr,
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Cuentas"
        action={<Button onClick={() => setCreating(true)}>Nueva</Button>}
        help={<ScreenHelp screen="Cuentas">{ACCOUNTS_HELP}</ScreenHelp>}
      />

      <label
        className="flex items-center gap-2 text-sm"
        style={{ color: "var(--muted-foreground)" }}
      >
        <input
          type="checkbox"
          checked={values.archived}
          onChange={(e) => patch({ archived: e.target.checked })}
        />
        Mostrar archivadas
      </label>

      {list.isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 5 }, (_, i) => `skel-${i}`).map((k) => (
            <div
              key={k}
              className="h-10 animate-pulse rounded"
              style={{ background: "var(--muted)" }}
            />
          ))}
        </div>
      )}
      {list.isError && (
        <ErrorState message="No se pudieron cargar las cuentas" onRetry={() => list.refetch()} />
      )}
      {list.data && list.data.length === 0 && (
        <EmptyState
          message="Todavía no tienes cuentas."
          description={WHAT_AN_ACCOUNT_IS}
          action={{ label: "Crear la primera", onClick: () => setCreating(true) }}
        />
      )}

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
                  <td className="px-3 py-2.5 text-right tabular-nums">
                    {formatCents(a.balance, a.currency)}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    {a.archived ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={restore.isPending}
                        onClick={() => restore.mutate(a.id)}
                      >
                        Restaurar
                      </Button>
                    ) : (
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => setEditing(a)}>
                          Editar
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setArchiving(a)}>
                          Archivar
                        </Button>
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
        description={`Se archivará "${archiving?.name}". Puedes restaurarla luego con "Mostrar archivadas".`}
        confirmLabel="Archivar"
        pending={archive.isPending}
        onConfirm={() => archiving && archive.mutate(archiving.id)}
      />
    </div>
  )
}
