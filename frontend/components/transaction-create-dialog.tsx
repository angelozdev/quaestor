"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { EntitySelect } from "@/components/entity-select"
import { MoneyInput } from "@/components/money-input"
import { listAccounts } from "@/lib/api/accounts"
import { listCategories } from "@/lib/api/categories"
import { createTransaction, createTransfer as createTransferApi } from "@/lib/api/transactions"
import { type Account, ApiError } from "@/lib/api/types"
import { invalidate, qk } from "@/lib/query"
import {
  Button,
  Dialog,
  DialogPopup,
  DialogTitle,
  Input,
  Label,
  Select,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
} from "@/ui"

const TYPE_ITEMS = [
  { value: "expense", label: "Gasto" },
  { value: "income", label: "Ingreso" },
]

function currencyOf(accounts: Account[] | undefined, id: number | null): string {
  if (id === null) return "COP"
  return accounts?.find((a) => a.id === id)?.currency ?? "COP"
}

export function TransactionCreateDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
}) {
  const qc = useQueryClient()
  const accounts = useQuery({
    queryKey: qk.accounts(false),
    queryFn: () => listAccounts(false),
  })

  // normal tab state
  const [type, setType] = useState<string | null>("expense")
  const [accountId, setAccountId] = useState<number | null>(null)
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [amount, setAmount] = useState<number | null>(null)
  const [date, setDate] = useState("")
  const [payee, setPayee] = useState("")
  const [notes, setNotes] = useState("")
  const [fxRate, setFxRate] = useState("")

  // transfer tab state
  const [fromId, setFromId] = useState<number | null>(null)
  const [toId, setToId] = useState<number | null>(null)
  const [tAmount, setTAmount] = useState<number | null>(null)
  const [tDate, setTDate] = useState("")
  const [tNotes, setTNotes] = useState("")
  const [tFxRate, setTFxRate] = useState("")

  function resetForm() {
    setType("expense")
    setAccountId(null)
    setCategoryId(null)
    setAmount(null)
    setDate("")
    setPayee("")
    setNotes("")
    setFxRate("")
    setFromId(null)
    setToId(null)
    setTAmount(null)
    setTDate("")
    setTNotes("")
    setTFxRate("")
  }

  const normalCurrency = currencyOf(accounts.data, accountId)
  const transferCurrency = currencyOf(accounts.data, fromId)

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error")

  const done = (msg: string) => {
    toast.success(msg)
    invalidate(qc, "transactionWrite")
    onOpenChange(false)
  }

  const createNormal = useMutation({
    mutationFn: () => {
      if (accountId === null || amount === null) {
        throw new Error("account and amount are required")
      }
      return createTransaction({
        type: type as "expense" | "income",
        account_id: accountId,
        amount,
        currency: normalCurrency,
        date,
        payee: payee || undefined,
        category_id: categoryId,
        notes: notes || undefined,
        fx_rate: normalCurrency !== "COP" && fxRate ? fxRate : undefined,
      })
    },
    onSuccess: () => done("Transacción creada"),
    onError: onErr,
  })

  const createTransfer = useMutation({
    mutationFn: () => {
      if (fromId === null || toId === null || tAmount === null) {
        throw new Error("from, to, and amount are required for a transfer")
      }
      return createTransferApi({
        from_account_id: fromId,
        to_account_id: toId,
        amount: tAmount,
        currency: transferCurrency,
        date: tDate,
        notes: tNotes || undefined,
        fx_rate: transferCurrency !== "COP" && tFxRate ? tFxRate : undefined,
      })
    },
    onSuccess: () => done("Transferencia creada"),
    onError: onErr,
  })

  const normalInvalid = !type || accountId === null || amount === null || !date
  const transferInvalid = fromId === null || toId === null || tAmount === null || !tDate

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) resetForm()
        onOpenChange(o)
      }}
    >
      <DialogPopup className="max-w-lg">
        <DialogTitle>Nueva transacción</DialogTitle>
        <Tabs defaultValue="normal">
          <TabsList>
            <TabsTrigger value="normal">Normal</TabsTrigger>
            <TabsTrigger value="transfer">Transferencia</TabsTrigger>
          </TabsList>

          <TabsContent value="normal">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (!normalInvalid) createNormal.mutate()
              }}
              className="space-y-4 pt-2"
            >
              <div className="space-y-1.5">
                <Label>Tipo *</Label>
                <Select value={type} onValueChange={setType} items={TYPE_ITEMS} />
              </div>
              <div className="space-y-1.5">
                <Label>Cuenta *</Label>
                <EntitySelect
                  value={accountId}
                  onChange={setAccountId}
                  queryKey={qk.accounts(false)}
                  queryFn={() => listAccounts(false)}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Monto * ({normalCurrency})</Label>
                <MoneyInput currency={normalCurrency} value={amount} onChange={setAmount} />
              </div>
              <div className="space-y-1.5">
                <Label>Fecha *</Label>
                <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Beneficiario</Label>
                <Input value={payee} onChange={(e) => setPayee(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Categoría</Label>
                <EntitySelect
                  value={categoryId}
                  onChange={setCategoryId}
                  queryKey={qk.categories(false)}
                  queryFn={() => listCategories(false)}
                  allowNullLabel="Sin categoría"
                />
              </div>
              {normalCurrency !== "COP" && (
                <div className="space-y-1.5">
                  <Label>Tasa USD→COP (opcional)</Label>
                  <Input
                    value={fxRate}
                    onChange={(e) => setFxRate(e.target.value)}
                    placeholder="Se resuelve sola si la dejas vacía"
                  />
                </div>
              )}
              <div className="space-y-1.5">
                <Label>Notas</Label>
                <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
              </div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={normalInvalid || createNormal.isPending}>
                  {createNormal.isPending ? "…" : "Crear"}
                </Button>
              </div>
            </form>
          </TabsContent>

          <TabsContent value="transfer">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (!transferInvalid) createTransfer.mutate()
              }}
              className="space-y-4 pt-2"
            >
              <div className="space-y-1.5">
                <Label>Desde *</Label>
                <EntitySelect
                  value={fromId}
                  onChange={setFromId}
                  queryKey={qk.accounts(false)}
                  queryFn={() => listAccounts(false)}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Hacia *</Label>
                <EntitySelect
                  value={toId}
                  onChange={setToId}
                  queryKey={qk.accounts(false)}
                  queryFn={() => listAccounts(false)}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Monto * ({transferCurrency})</Label>
                <MoneyInput currency={transferCurrency} value={tAmount} onChange={setTAmount} />
              </div>
              <div className="space-y-1.5">
                <Label>Fecha *</Label>
                <Input type="date" value={tDate} onChange={(e) => setTDate(e.target.value)} />
              </div>
              {transferCurrency !== "COP" && (
                <div className="space-y-1.5">
                  <Label>Tasa USD→COP (opcional)</Label>
                  <Input value={tFxRate} onChange={(e) => setTFxRate(e.target.value)} />
                </div>
              )}
              <div className="space-y-1.5">
                <Label>Notas</Label>
                <Textarea value={tNotes} onChange={(e) => setTNotes(e.target.value)} />
              </div>
              <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                Ambas cuentas deben tener la misma moneda.
              </p>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={transferInvalid || createTransfer.isPending}>
                  {createTransfer.isPending ? "…" : "Crear"}
                </Button>
              </div>
            </form>
          </TabsContent>
        </Tabs>
      </DialogPopup>
    </Dialog>
  )
}
