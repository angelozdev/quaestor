"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
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
import { invalidate, qk } from "@/lib/query"
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
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [accountId, setAccountId] = useState<number | null>(null)
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [tag, setTag] = useState<number | null>(null)
  const [type, setType] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)

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
    if (dateFrom) f.date_from = dateFrom
    if (dateTo) f.date_to = dateTo
    if (accountId !== null) f.account_id = accountId
    if (categoryId !== null) f.category_id = categoryId
    if (tag !== null) {
      const tagged = tags.data?.find((t) => t.id === tag)?.name
      if (tagged) f.tag = tagged
    }
    if (type && type !== ALL) f.type = type as TxType
    if (status && status !== ALL) f.status = status as TxStatus
    return f
  }, [dateFrom, dateTo, accountId, categoryId, tag, type, status, tags.data])

  const list = useQuery({
    queryKey: qk.transactions(filters),
    queryFn: () => listTransactions(filters),
  })

  const columns: Column<Transaction>[] = [
    { key: "date", header: "Fecha", render: (t) => t.date },
    {
      key: "payee",
      header: "Beneficiario",
      render: (t) => <span className="font-medium">{t.payee || "—"}</span>,
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
  ]

  const actions: RowAction<Transaction>[] = [
    { label: "Editar", onClick: (t) => setEditing(t) },
    {
      label: "Eliminar",
      variant: "destructive",
      onClick: (t) => {
        if (t.type === "transfer") {
          toast.error("Las transferencias no se pueden eliminar (Fase 1).")
          return
        }
        setDeleting(t)
      },
    },
  ]

  const clear = () => {
    setDateFrom("")
    setDateTo("")
    setAccountId(null)
    setCategoryId(null)
    setTag(null)
    setType(null)
    setStatus(null)
  }

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
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
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
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
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
          value={accountId}
          onChange={setAccountId}
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
          value={categoryId}
          onChange={setCategoryId}
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
          value={tag}
          onChange={setTag}
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
          value={type ?? ALL}
          onValueChange={(v) => setType(v === ALL ? null : v)}
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
          value={status ?? ALL}
          onValueChange={(v) => setStatus(v === ALL ? null : v)}
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
        title="Eliminar transacción"
        description={`Se eliminará "${deleting?.payee || "(sin beneficiario)"}". Es permanente.`}
        confirmLabel="Eliminar"
        destructive
        pending={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting.id)}
      />
    </div>
  )
}
