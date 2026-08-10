"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeftRight } from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { type Column, DataTable, type RowAction } from "@/components/data-table"
import { EntitySelect } from "@/components/entity-select"
import { MoneyAmount } from "@/components/money-amount"
import { PageHeader } from "@/components/page-header"
import { ScreenHelp } from "@/components/screen-help"
import { StatusBadge } from "@/components/status-badge"
import { TransactionCreateDialog } from "@/components/transaction-create-dialog"
import { TransactionEditDialog } from "@/components/transaction-edit-dialog"
import { listAccounts } from "@/lib/api/accounts"
import { listCategories } from "@/lib/api/categories"
import { restorePlanned } from "@/lib/api/planned"
import { listTags } from "@/lib/api/tags"
import { deleteTransaction, listTransactions } from "@/lib/api/transactions"
import type { Transaction, TransactionFilters, TxStatus, TxType } from "@/lib/api/types"
import { ApiError } from "@/lib/api/types"
import { formatDate } from "@/lib/date"
import { TX_FILTER_SCHEMA } from "@/lib/filter-schemas"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { counterpartsByTxId, hasCounterpartLeg } from "@/lib/transfers"
import { useUrlFilters } from "@/lib/use-url-filters"
import { Badge, Button, Input, Select } from "@/ui"

const ALL = "__all__"

const TYPE_ITEMS = [
  { value: ALL, label: "Todos" },
  { value: "expense", label: "Gasto" },
  { value: "income", label: "Ingreso" },
  { value: "transfer", label: "Transferencia" },
]
const STATUS_ITEMS = [
  { value: ALL, label: "Todos" },
  { value: "planned", label: "Planeado" },
  { value: "posted", label: "Registrado" },
  { value: "skipped", label: "Omitido" },
]

const WHAT_A_MOVEMENT_IS = (
  <p>
    Un movimiento es plata que entra o que sale — un gasto, un ingreso, o un traslado entre tus
    cuentas.
  </p>
)

const TRANSACTIONS_HELP = (
  <>
    {WHAT_A_MOVEMENT_IS}
    <p>
      Aquí queda registrado cada uno. La categoría que le pongas es lo que alimenta los reportes y
      lo que un fondo o un presupuesto vigila.
    </p>
    <p>
      Los filtros de arriba se guardan en la dirección del navegador, así que la lista que estás
      viendo se puede volver a abrir tal cual.
    </p>
  </>
)

function deleteDescription(tx: Transaction | null): string {
  if (tx?.type !== "transfer")
    return `Se eliminará "${tx?.payee || "(sin beneficiario)"}". Es permanente.`
  if (hasCounterpartLeg(tx))
    return "Se eliminarán ambos lados de la transferencia y se restaurarán los saldos de las dos cuentas. Es permanente."
  return "Esta transferencia todavía no tiene contraparte: se eliminará solo este movimiento y ningún saldo cambiará. Es permanente."
}

function Filter({
  id,
  label,
  width,
  children,
}: {
  id: string
  label: string
  width: string
  children: React.ReactNode
}) {
  return (
    <div className={`${width} space-y-1`}>
      <label htmlFor={id} className="block text-xs" style={{ color: "var(--muted-foreground)" }}>
        {label}
      </label>
      {children}
    </div>
  )
}

export default function TransactionsPage() {
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Transaction | null>(null)
  const [deleting, setDeleting] = useState<Transaction | null>(null)

  const qc = useQueryClient()

  const del = useMutation({
    mutationFn: (id: number) => deleteTransaction(id),
    onSuccess: () => {
      toast.success("Transacción eliminada")
      invalidate(qc, "transactionWrite")
      setDeleting(null)
    },
    onError: (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error"),
  })

  const restore = useMutation({
    mutationFn: (id: number) => restorePlanned(id),
    onSuccess: () => {
      toast.success("Pago restaurado")
      invalidate(qc, "transactionWrite")
    },
    onError: (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error"),
  })

  const { values, patch, clear } = useUrlFilters(TX_FILTER_SCHEMA)

  const accounts = useQuery({
    queryKey: qk.accounts(true),
    queryFn: () => listAccounts(true),
  })
  const categories = useQuery({
    queryKey: qk.categories(true),
    queryFn: () => listCategories(true),
  })
  const tags = useQuery({
    queryKey: qk.tags(),
    queryFn: () => listTags(),
  })

  const accountName = (id: number | null) =>
    id === null ? "—" : (accounts.data?.find((a) => a.id === id)?.name ?? `#${id}`)
  const categoryName = (id: number | null) =>
    id === null ? "—" : (categories.data?.find((c) => c.id === id)?.name ?? `#${id}`)

  const filters: TransactionFilters = useMemo(() => {
    const f: TransactionFilters = {}
    if (values.date_from) f.date_from = values.date_from
    if (values.date_to) f.date_to = values.date_to
    if (values.account_id !== null) f.account_id = values.account_id
    if (values.category_id !== null) f.category_id = values.category_id
    if (values.tag !== null) {
      const tagged = tags.data?.find((t) => t.id === values.tag)?.name
      if (tagged) f.tag = tagged
    }
    if (values.type) f.type = values.type
    if (values.status) f.status = values.status
    return f
  }, [values, tags.data])

  const list = useQuery({
    queryKey: qk.transactions(filters),
    queryFn: () => listTransactions(filters),
  })

  const counterparts = useMemo(() => counterpartsByTxId(list.data), [list.data])

  const transferLabel = (t: Transaction) => {
    const counterpart = counterparts.get(t.id)
    const name = counterpart ? accountName(counterpart.account_id) : null
    if (t.transfer_direction === "out")
      return name ? `Transferencia a ${name}` : "Transferencia enviada"
    if (t.transfer_direction === "in")
      return name ? `Transferencia desde ${name}` : "Transferencia recibida"
    return "Transferencia"
  }

  const columns: Column<Transaction>[] = [
    {
      key: "date",
      header: "Fecha",
      render: (t) => <span className="whitespace-nowrap">{formatDate(t.date)}</span>,
    },
    {
      key: "payee",
      header: "Beneficiario",
      render: (t) =>
        t.type === "transfer" ? (
          <span
            className="inline-flex items-center gap-1.5"
            style={{ color: "var(--muted-foreground)" }}
          >
            <ArrowLeftRight size={14} aria-hidden />
            {transferLabel(t)}
          </span>
        ) : (
          <span className="inline-flex items-center gap-2">
            <span className="font-medium">{t.payee || "—"}</span>
            {t.source === "recurring" && <Badge variant="outline">Recurrente</Badge>}
          </span>
        ),
    },
    {
      key: "category",
      header: "Categoría",
      render: (t) => (
        <span style={{ color: "var(--muted-foreground)" }}>{categoryName(t.category_id)}</span>
      ),
    },
    {
      key: "account",
      header: "Cuenta",
      render: (t) => (
        <span style={{ color: "var(--muted-foreground)" }}>{accountName(t.account_id)}</span>
      ),
    },
    {
      key: "status",
      header: "Estado",
      render: (t) => <StatusBadge kind="tx" value={t.status} />,
    },
    {
      key: "amount",
      header: "Monto",
      align: "right",
      render: (t) => (
        <MoneyAmount
          cents={t.amount}
          currency={t.currency}
          type={t.type}
          className="whitespace-nowrap"
        />
      ),
    },
    {
      key: "cop_equivalent",
      header: "Equivalente (COP)",
      align: "right",
      render: (t) => (
        <span style={{ color: "var(--muted-foreground)" }}>
          {t.cop_equivalent === null ? "—" : formatCents(t.cop_equivalent, "COP")}
        </span>
      ),
    },
  ]

  const actions: RowAction<Transaction>[] = [
    { label: "Editar", onClick: (t) => setEditing(t) },
    {
      label: "Restaurar",
      show: (t) => t.status === "skipped",
      onClick: (t) => restore.mutate(t.id),
    },
    {
      label: "Eliminar",
      variant: "destructive",
      onClick: (t) => setDeleting(t),
    },
  ]

  const filterBar = (
    <div className="flex flex-wrap items-end gap-3">
      <Filter id="tx-from" label="Desde" width="w-36">
        <Input
          id="tx-from"
          type="date"
          value={values.date_from ?? ""}
          onChange={(e) => patch({ date_from: e.target.value })}
        />
      </Filter>
      <Filter id="tx-to" label="Hasta" width="w-36">
        <Input
          id="tx-to"
          type="date"
          value={values.date_to ?? ""}
          onChange={(e) => patch({ date_to: e.target.value })}
        />
      </Filter>
      <Filter id="tx-account" label="Cuenta" width="w-40">
        <EntitySelect
          id="tx-account"
          value={values.account_id}
          onChange={(v) => patch({ account_id: v })}
          queryKey={qk.accounts(true)}
          queryFn={() => listAccounts(true)}
          allowNullLabel="Todas"
        />
      </Filter>
      <Filter id="tx-category" label="Categoría" width="w-40">
        <EntitySelect
          id="tx-category"
          value={values.category_id}
          onChange={(v) => patch({ category_id: v })}
          queryKey={qk.categories(true)}
          queryFn={() => listCategories(true)}
          allowNullLabel="Todas"
        />
      </Filter>
      <Filter id="tx-tag" label="Etiqueta" width="w-36">
        <EntitySelect
          id="tx-tag"
          value={values.tag}
          onChange={(v) => patch({ tag: v })}
          queryKey={qk.tags()}
          queryFn={() => listTags()}
          allowNullLabel="Todas"
          disabled={tags.isLoading}
        />
      </Filter>
      <Filter id="tx-type" label="Tipo" width="w-32">
        <Select
          id="tx-type"
          value={values.type ?? ALL}
          onValueChange={(v) => patch({ type: v === ALL ? null : (v as TxType) })}
          items={TYPE_ITEMS}
          placeholder="Todos"
        />
      </Filter>
      <Filter id="tx-status" label="Estado" width="w-32">
        <Select
          id="tx-status"
          value={values.status ?? ALL}
          onValueChange={(v) => patch({ status: v === ALL ? null : (v as TxStatus) })}
          items={STATUS_ITEMS}
          placeholder="Todos"
        />
      </Filter>
      <Button variant="ghost" size="sm" onClick={clear}>
        Limpiar
      </Button>
    </div>
  )

  return (
    <div className="space-y-10">
      <PageHeader
        title="Transacciones"
        action={<Button onClick={() => setCreating(true)}>Nueva</Button>}
        help={<ScreenHelp screen="Transacciones">{TRANSACTIONS_HELP}</ScreenHelp>}
      />
      <DataTable
        rows={list.data}
        columns={columns}
        rowKey={(t) => t.id}
        actions={actions}
        filterBar={filterBar}
        isLoading={list.isLoading}
        isError={list.isError}
        onRetry={() => list.refetch()}
        emptyMessage="No hay transacciones para estos filtros"
        emptyDescription={WHAT_A_MOVEMENT_IS}
        emptyAction={{ label: "Registrar el primero", onClick: () => setCreating(true) }}
      />
      <TransactionCreateDialog open={creating} onOpenChange={setCreating} />
      <TransactionEditDialog
        tx={editing}
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
      />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={deleting?.type === "transfer" ? "Eliminar transferencia" : "Eliminar transacción"}
        description={deleteDescription(deleting)}
        confirmLabel="Eliminar"
        destructive
        pending={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting.id)}
      />
    </div>
  )
}
