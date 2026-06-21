"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { Controller, useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { EmptyState } from "@/components/empty-state"
import { EntitySelect } from "@/components/entity-select"
import { ErrorState } from "@/components/error-state"
import { FormField } from "@/components/form-field"
import { MoneyAmount } from "@/components/money-amount"
import { MoneyInput } from "@/components/money-input"
import { PageHeader } from "@/components/page-header"
import { StatusBadge } from "@/components/status-badge"
import { listAccounts } from "@/lib/api/accounts"
import { listCategories } from "@/lib/api/categories"
import {
  createRecurring,
  deleteRecurring,
  listRecurring,
  restoreRecurring,
  skipRecurring,
  updateRecurring,
} from "@/lib/api/recurring"
import { ApiError, type IntervalUnit, type Recurring } from "@/lib/api/types"
import { invalidate, qk } from "@/lib/query"
import { intervalCount, isoDate, positiveCents, requiredString } from "@/lib/schemas/primitives"
import { Button, Dialog, DialogPopup, DialogTitle, Input, Label, Select } from "@/ui"

const TYPE_ITEMS = [
  { value: "expense", label: "Gasto" },
  { value: "income", label: "Ingreso" },
]
const MODE_ITEMS = [
  { value: "auto", label: "Automático" },
  { value: "manual", label: "Manual" },
]
const UNIT_ITEMS = [
  { value: "day", label: "Día(s)" },
  { value: "week", label: "Semana(s)" },
  { value: "month", label: "Mes(es)" },
  { value: "year", label: "Año(s)" },
]

const UNIT_SINGULAR: Record<IntervalUnit, string> = {
  day: "día",
  week: "semana",
  month: "mes",
  year: "año",
}
const UNIT_PLURAL: Record<IntervalUnit, string> = {
  day: "días",
  week: "semanas",
  month: "meses",
  year: "años",
}

function intervalLabel(unit: IntervalUnit, count: number): string {
  if (count === 1) return `Cada ${UNIT_SINGULAR[unit]}`
  return `Cada ${count} ${UNIT_PLURAL[unit]}`
}

const recurringCreateSchema = z
  .object({
    name: requiredString,
    payee: z.string().max(500, "Máximo 500 caracteres").optional(),
    amount: positiveCents,
    currency: z.enum(["COP", "USD"]),
    categoryId: z.number().nullable(),
    accountId: z.number().nullable(),
    type: z.enum(["expense", "income"]),
    mode: z.enum(["auto", "manual"]),
    intervalCount,
    intervalUnit: z.enum(["day", "week", "month", "year"]),
    startDate: isoDate,
    endDate: isoDate.optional().or(z.literal("")),
  })
  .refine((d) => !d.endDate || d.endDate >= d.startDate, {
    message: "Fin debe ser ≥ inicio",
    path: ["endDate"],
  })
  .refine((d) => d.accountId !== null, {
    message: "Requerido",
    path: ["accountId"],
  })

type RecurringCreateValues = z.infer<typeof recurringCreateSchema>

const recurringEditSchema = recurringCreateSchema
type RecurringEditValues = z.infer<typeof recurringEditSchema>

export default function RecurringPage() {
  const qc = useQueryClient()

  const [showInactive, setShowInactive] = useState(false)
  const list = useQuery({
    queryKey: qk.recurring(showInactive ? undefined : true),
    queryFn: () => listRecurring(showInactive ? undefined : true),
  })

  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Recurring | null>(null)
  const [deleting, setDeleting] = useState<Recurring | null>(null)

  const createForm = useForm<RecurringCreateValues>({
    resolver: zodResolver(recurringCreateSchema),
    defaultValues: {
      name: "",
      payee: "",
      amount: Number.NaN,
      currency: "COP",
      categoryId: null,
      accountId: null,
      type: "expense",
      mode: "manual",
      intervalCount: 1,
      intervalUnit: "month",
      startDate: new Date().toISOString().slice(0, 10),
      endDate: "",
    },
  })
  const { reset: resetCreate } = createForm

  const editForm = useForm<RecurringEditValues>({
    resolver: zodResolver(recurringEditSchema),
    defaultValues: {
      name: "",
      payee: "",
      amount: Number.NaN,
      currency: "COP",
      categoryId: null,
      accountId: null,
      type: "expense",
      mode: "manual",
      intervalCount: 1,
      intervalUnit: "month",
      startDate: "",
      endDate: "",
    },
  })
  const { reset: resetEdit } = editForm

  const [skipping, setSkipping] = useState<Recurring | null>(null)
  const [skipDate, setSkipDate] = useState("")

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error")
  const done = (msg: string) => {
    toast.success(msg)
    invalidate(qc, "recurringWrite")
  }

  const create = useMutation({
    mutationFn: (values: RecurringCreateValues) => {
      return createRecurring({
        name: values.name,
        type: values.type,
        mode: values.mode,
        amount: values.amount,
        account_id: values.accountId as number,
        interval_unit: values.intervalUnit,
        interval_count: values.intervalCount,
        start_date: values.startDate,
        end_date: values.endDate ? values.endDate : null,
        currency: values.currency,
        category_id: values.categoryId,
        payee: values.payee && values.payee.length > 0 ? values.payee : undefined,
      })
    },
    onSuccess: () => {
      done("Recurrente creado")
      setCreating(false)
      resetCreate({
        name: "",
        payee: "",
        amount: Number.NaN,
        currency: "COP",
        categoryId: null,
        accountId: null,
        type: "expense",
        mode: "manual",
        intervalCount: 1,
        intervalUnit: "month",
        startDate: new Date().toISOString().slice(0, 10),
        endDate: "",
      })
    },
    onError: onErr,
  })

  const update = useMutation({
    mutationFn: (values: RecurringEditValues) => {
      if (!editing) throw new Error("editing recurring is required")
      return updateRecurring(editing.id, {
        name: values.name,
        amount: values.amount,
        payee: values.payee && values.payee.length > 0 ? values.payee : undefined,
        category_id: values.categoryId,
        account_id: values.accountId ?? undefined,
        mode: values.mode,
        interval_unit: values.intervalUnit,
        interval_count: values.intervalCount,
        start_date: values.startDate,
        end_date: values.endDate ? values.endDate : null,
      })
    },
    onSuccess: () => {
      done("Recurrente actualizado")
      setEditing(null)
    },
    onError: onErr,
  })

  const remove = useMutation({
    mutationFn: () => {
      if (!deleting) throw new Error("deleting recurring is required")
      return deleteRecurring(deleting.id)
    },
    onSuccess: () => {
      done("Recurrente desactivado")
      setDeleting(null)
    },
    onError: onErr,
  })

  const restore = useMutation({
    mutationFn: (r: Recurring) => restoreRecurring(r.id),
    onSuccess: () => done("Recurrente restaurado"),
    onError: onErr,
  })

  const skip = useMutation({
    mutationFn: () => {
      if (!skipping) throw new Error("skipping recurring is required")
      return skipRecurring(skipping.id, skipDate)
    },
    onSuccess: () => {
      done("Ocurrencia omitida")
      setSkipping(null)
      setSkipDate("")
    },
    onError: onErr,
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Recurrentes"
        action={<Button onClick={() => setCreating(true)}>Nuevo</Button>}
      />

      <label
        className="flex items-center gap-2 text-sm"
        style={{ color: "var(--muted-foreground)" }}
      >
        <input
          type="checkbox"
          checked={showInactive}
          onChange={(e) => setShowInactive(e.target.checked)}
        />
        Mostrar inactivos
      </label>

      {list.isError && (
        <ErrorState
          message="No se pudieron cargar los recurrentes"
          onRetry={() => list.refetch()}
        />
      )}
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
                  <td className="px-3 py-2.5 font-medium">
                    {r.name}
                    {!r.active && <StatusBadge kind="archived" value={true} />}
                  </td>
                  <td className="px-3 py-2.5" style={{ color: "var(--muted-foreground)" }}>
                    {intervalLabel(r.interval_unit, r.interval_count)}
                  </td>
                  <td className="px-3 py-2.5">
                    <StatusBadge kind="mode" value={r.mode} />
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    <MoneyAmount cents={r.amount} currency={r.currency} type={r.type} />
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    {r.active ? (
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setEditing(r)
                            resetEdit({
                              name: r.name,
                              payee: r.payee,
                              amount: r.amount,
                              currency: r.currency as "COP" | "USD",
                              categoryId: r.category_id,
                              accountId: r.account_id,
                              type: r.type,
                              mode: r.mode,
                              intervalCount: r.interval_count,
                              intervalUnit: r.interval_unit,
                              startDate: r.start_date,
                              endDate: r.end_date ?? "",
                            })
                          }}
                        >
                          Editar
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setSkipping(r)}>
                          Omitir
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setDeleting(r)}>
                          Eliminar
                        </Button>
                      </div>
                    ) : (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => restore.mutate(r)}
                        disabled={restore.isPending}
                      >
                        Restaurar
                      </Button>
                    )}
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
          <form
            onSubmit={createForm.handleSubmit((values) => create.mutate(values))}
            className="space-y-4"
          >
            <FormField control={createForm.control} name="name" label="Nombre" />
            <div className="grid grid-cols-2 gap-3">
              <Controller
                control={createForm.control}
                name="type"
                render={({ field }) => (
                  <div className="space-y-1.5">
                    <Label>Tipo *</Label>
                    <Select
                      value={field.value}
                      onValueChange={(v) => field.onChange(v)}
                      items={TYPE_ITEMS}
                    />
                  </div>
                )}
              />
              <Controller
                control={createForm.control}
                name="mode"
                render={({ field }) => (
                  <div className="space-y-1.5">
                    <Label>Modo *</Label>
                    <Select
                      value={field.value}
                      onValueChange={(v) => field.onChange(v)}
                      items={MODE_ITEMS}
                    />
                  </div>
                )}
              />
            </div>
            <Controller
              control={createForm.control}
              name="accountId"
              render={({ field, fieldState: { error } }) => (
                <div className="space-y-1.5">
                  <Label>Cuenta *</Label>
                  <EntitySelect
                    value={field.value}
                    onChange={field.onChange}
                    queryKey={qk.accounts(false)}
                    queryFn={() => listAccounts(false)}
                  />
                  {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                </div>
              )}
            />
            <Controller
              control={createForm.control}
              name="amount"
              render={({ field, fieldState: { error } }) => (
                <div className="space-y-1.5">
                  <Label>Monto * ({createForm.watch("currency")})</Label>
                  <MoneyInput
                    currency={createForm.watch("currency")}
                    value={
                      typeof field.value === "number" && Number.isFinite(field.value)
                        ? field.value
                        : null
                    }
                    onChange={(cents) => field.onChange(cents ?? Number.NaN)}
                  />
                  {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                </div>
              )}
            />
            <div className="grid grid-cols-2 gap-3">
              <FormField
                control={createForm.control}
                name="intervalCount"
                label="Cada (cantidad)"
                type="number"
                min={1}
                valueAsNumber
              />
              <Controller
                control={createForm.control}
                name="intervalUnit"
                render={({ field, fieldState: { error } }) => (
                  <div className="space-y-1.5">
                    <Label>Unidad *</Label>
                    <Select
                      value={field.value}
                      onValueChange={(v) => field.onChange(v)}
                      items={UNIT_ITEMS}
                    />
                    {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                  </div>
                )}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <FormField control={createForm.control} name="startDate" label="Inicio" type="date" />
              <FormField
                control={createForm.control}
                name="endDate"
                label="Fin (opcional)"
                type="date"
              />
            </div>
            <Controller
              control={createForm.control}
              name="categoryId"
              render={({ field, fieldState: { error } }) => (
                <div className="space-y-1.5">
                  <Label>Categoría</Label>
                  <EntitySelect
                    value={field.value}
                    onChange={field.onChange}
                    queryKey={qk.categories(false)}
                    queryFn={() => listCategories(false)}
                    allowNullLabel="Sin categoría"
                  />
                  {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                </div>
              )}
            />
            <FormField control={createForm.control} name="payee" label="Beneficiario" />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setCreating(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "…" : "Crear"}
              </Button>
            </div>
          </form>
        </DialogPopup>
      </Dialog>

      {/* Edit dialog */}
      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogPopup className="max-w-lg">
          <DialogTitle>Editar recurrente</DialogTitle>
          <form
            onSubmit={editForm.handleSubmit((values) => update.mutate(values))}
            className="space-y-4"
          >
            <FormField control={editForm.control} name="name" label="Nombre" />
            <div className="grid grid-cols-2 gap-3">
              <Controller
                control={editForm.control}
                name="type"
                render={() => (
                  <div className="space-y-1.5">
                    <Label>Tipo (no editable)</Label>
                    <Select
                      value={editForm.watch("type")}
                      onValueChange={() => {}}
                      items={TYPE_ITEMS}
                      disabled
                    />
                  </div>
                )}
              />
              <Controller
                control={editForm.control}
                name="mode"
                render={({ field }) => (
                  <div className="space-y-1.5">
                    <Label>Modo *</Label>
                    <Select
                      value={field.value}
                      onValueChange={(v) => field.onChange(v)}
                      items={MODE_ITEMS}
                    />
                  </div>
                )}
              />
            </div>
            <Controller
              control={editForm.control}
              name="accountId"
              render={({ field, fieldState: { error } }) => (
                <div className="space-y-1.5">
                  <Label>Cuenta *</Label>
                  <EntitySelect
                    value={field.value}
                    onChange={field.onChange}
                    queryKey={qk.accounts(false)}
                    queryFn={() => listAccounts(false)}
                  />
                  {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                </div>
              )}
            />
            <Controller
              control={editForm.control}
              name="amount"
              render={({ field, fieldState: { error } }) => (
                <div className="space-y-1.5">
                  <Label>Monto * ({editForm.watch("currency")})</Label>
                  <MoneyInput
                    currency={editForm.watch("currency")}
                    value={
                      typeof field.value === "number" && Number.isFinite(field.value)
                        ? field.value
                        : null
                    }
                    onChange={(cents) => field.onChange(cents ?? Number.NaN)}
                  />
                  {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                </div>
              )}
            />
            <div className="grid grid-cols-2 gap-3">
              <FormField
                control={editForm.control}
                name="intervalCount"
                label="Cada (cantidad)"
                type="number"
                min={1}
                valueAsNumber
              />
              <Controller
                control={editForm.control}
                name="intervalUnit"
                render={({ field, fieldState: { error } }) => (
                  <div className="space-y-1.5">
                    <Label>Unidad *</Label>
                    <Select
                      value={field.value}
                      onValueChange={(v) => field.onChange(v)}
                      items={UNIT_ITEMS}
                    />
                    {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                  </div>
                )}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <FormField control={editForm.control} name="startDate" label="Inicio" type="date" />
              <FormField
                control={editForm.control}
                name="endDate"
                label="Fin (opcional)"
                type="date"
              />
            </div>
            <Controller
              control={editForm.control}
              name="categoryId"
              render={({ field, fieldState: { error } }) => (
                <div className="space-y-1.5">
                  <Label>Categoría</Label>
                  <EntitySelect
                    value={field.value}
                    onChange={field.onChange}
                    queryKey={qk.categories(false)}
                    queryFn={() => listCategories(false)}
                    allowNullLabel="Sin categoría"
                  />
                  {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                </div>
              )}
            />
            <FormField control={editForm.control} name="payee" label="Beneficiario" />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setEditing(null)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={update.isPending}>
                {update.isPending ? "…" : "Guardar"}
              </Button>
            </div>
          </form>
        </DialogPopup>
      </Dialog>

      {/* Skip dialog */}
      <Dialog open={skipping !== null} onOpenChange={(o) => !o && setSkipping(null)}>
        <DialogPopup className="max-w-sm">
          <DialogTitle>Omitir ocurrencia</DialogTitle>
          {skipping && (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (skipDate) skip.mutate()
              }}
              className="space-y-4"
            >
              <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                Indica la fecha de la ocurrencia de &quot;{skipping.name}&quot; que quieres omitir.
              </p>
              <div className="space-y-1.5">
                <Label>Fecha de la ocurrencia *</Label>
                <Input type="date" value={skipDate} onChange={(e) => setSkipDate(e.target.value)} />
              </div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setSkipping(null)}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={!skipDate || skip.isPending}>
                  {skip.isPending ? "…" : "Omitir"}
                </Button>
              </div>
            </form>
          )}
        </DialogPopup>
      </Dialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="Eliminar recurrente"
        description={`Se desactivará "${deleting?.name}". Las ocurrencias ya registradas se mantienen. Puedes restaurarlo luego.`}
        confirmLabel="Eliminar"
        destructive
        pending={remove.isPending}
        onConfirm={() => deleting && remove.mutate()}
      />
    </div>
  )
}
