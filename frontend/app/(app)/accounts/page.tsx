"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { DataTable } from "@/components/data-table"
import { EntityFormDialog, type Field, type FormValues } from "@/components/entity-form-dialog"
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
import { Button, Checkbox } from "@/ui"

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
        <Checkbox
          checked={values.archived}
          onCheckedChange={(checked) => patch({ archived: checked })}
        />
        Mostrar archivadas
      </label>

      <DataTable
        rows={list.data}
        rowKey={(a) => a.id}
        isLoading={list.isLoading}
        isError={list.isError}
        onRetry={() => list.refetch()}
        columns={[
          {
            key: "name",
            header: "Nombre",
            render: (a) => (
              <span className="flex items-center gap-2">
                {a.name} <StatusBadge kind="archived" value={a.archived} />
              </span>
            ),
          },
          {
            key: "type",
            header: "Tipo",
            render: (a) => (
              <span style={{ color: "var(--muted-foreground)" }}>
                {TYPE_LABEL[a.type] ?? a.type}
              </span>
            ),
          },
          {
            key: "balance",
            header: "Saldo",
            align: "right",
            render: (a) => formatCents(a.balance, a.currency),
          },
        ]}
        actionsAs="inline"
        actions={[
          {
            label: "Restaurar",
            show: (a) => a.archived,
            disabled: restore.isPending,
            onClick: (a) => restore.mutate(a.id),
          },
          { label: "Editar", show: (a) => !a.archived, onClick: (a) => setEditing(a) },
          { label: "Archivar", show: (a) => !a.archived, onClick: (a) => setArchiving(a) },
        ]}
        emptyMessage="Todavía no tienes cuentas."
        emptyDescription={WHAT_AN_ACCOUNT_IS}
        emptyAction={{ label: "Crear la primera", onClick: () => setCreating(true) }}
      />

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
