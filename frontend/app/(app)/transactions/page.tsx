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
import { StatusBadge } from "@/components/status-badge"
import { TransactionCreateDialog } from "@/components/transaction-create-dialog"
import { TransactionEditDialog } from "@/components/transaction-edit-dialog"
import { listAccounts } from "@/lib/api/accounts"
import { listCategories } from "@/lib/api/categories"
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
import { Button, Input, Select } from "@/ui"

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

function deleteDescription(tx: Transaction | null): string {
  if (tx?.type !== "transfer")
    return `Se eliminará "${tx?.payee || "(sin beneficiario)"}". Es permanente.`
  if (hasCounterpartLeg(tx))
    return "Se eliminarán ambos lados de la transferencia y se restaurarán los saldos de las dos cuentas. Es permanente."
  return "Esta transferencia todavía no tiene contraparte: se eliminará solo este movimiento y ningún saldo cambiará. Es permanente."
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
    { key: "date", header: "Fecha", render: (t) => formatDate(t.date) },
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
          <span className="font-medium">{t.payee || "—"}</span>
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
      render: (t) => <MoneyAmount cents={t.amount} currency={t.currency} type={t.type} />,
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
      label: "Eliminar",
      variant: "destructive",
      onClick: (t) => setDeleting(t),
    },
  ]

  const filterBar = (
    <div className="flex flex-wrap items-end gap-2">
      <div className="space-y-1">
        <label
          htmlFor="tx-from"
          className="block text-xs"
          style={{ color: "var(--muted-foreground)" }}
        >
          Desde
        </label>
        <Input
          id="tx-from"
          type="date"
          value={values.date_from ?? ""}
          onChange={(e) => patch({ date_from: e.target.value })}
          className="w-36"
        />
      </div>
      <div className="space-y-1">
        <label
          htmlFor="tx-to"
          className="block text-xs"
          style={{ color: "var(--muted-foreground)" }}
        >
          Hasta
        </label>
        <Input
          id="tx-to"
          type="date"
          value={values.date_to ?? ""}
          onChange={(e) => patch({ date_to: e.target.value })}
          className="w-36"
        />
      </div>
      <div className="w-40 space-y-1">
        <label
          htmlFor="tx-account"
          className="block text-xs"
          style={{ color: "var(--muted-foreground)" }}
        >
          Cuenta
        </label>
        <EntitySelect
          id="tx-account"
          value={values.account_id}
          onChange={(v) => patch({ account_id: v })}
          queryKey={qk.accounts(true)}
          queryFn={() => listAccounts(true)}
          allowNullLabel="Todas"
        />
      </div>
      <div className="w-40 space-y-1">
        <label
          htmlFor="tx-category"
          className="block text-xs"
          style={{ color: "var(--muted-foreground)" }}
        >
          Categoría
        </label>
        <EntitySelect
          id="tx-category"
          value={values.category_id}
          onChange={(v) => patch({ category_id: v })}
          queryKey={qk.categories(true)}
          queryFn={() => listCategories(true)}
          allowNullLabel="Todas"
        />
      </div>
      <div className="w-36 space-y-1">
        <label
          htmlFor="tx-tag"
          className="block text-xs"
          style={{ color: "var(--muted-foreground)" }}
        >
          Etiqueta
        </label>
        <EntitySelect
          id="tx-tag"
          value={values.tag}
          onChange={(v) => patch({ tag: v })}
          queryKey={qk.tags()}
          queryFn={() => listTags()}
          allowNullLabel="Todas"
          disabled={tags.isLoading}
        />
      </div>
      <div className="w-32 space-y-1">
        <label
          htmlFor="tx-type"
          className="block text-xs"
          style={{ color: "var(--muted-foreground)" }}
        >
          Tipo
        </label>
        <Select
          id="tx-type"
          value={values.type ?? ALL}
          onValueChange={(v) => patch({ type: v === ALL ? null : (v as TxType) })}
          items={TYPE_ITEMS}
          placeholder="Todos"
        />
      </div>
      <div className="w-32 space-y-1">
        <label
          htmlFor="tx-status"
          className="block text-xs"
          style={{ color: "var(--muted-foreground)" }}
        >
          Estado
        </label>
        <Select
          id="tx-status"
          value={values.status ?? ALL}
          onValueChange={(v) => patch({ status: v === ALL ? null : (v as TxStatus) })}
          items={STATUS_ITEMS}
          placeholder="Todos"
        />
      </div>
      <Button variant="ghost" size="sm" onClick={clear}>
        Limpiar
      </Button>
    </div>
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Transacciones"
        action={<Button onClick={() => setCreating(true)}>Nueva</Button>}
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
