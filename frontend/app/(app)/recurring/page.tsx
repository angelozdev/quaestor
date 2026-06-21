"use client"

import { useForm as useTanStackForm } from "@tanstack/react-form"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
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
import { ApiError, applyApiErrorsToForm, type IntervalUnit, type Recurring } from "@/lib/api/types"
import { invalidate, qk } from "@/lib/query"
import { Button, Dialog, DialogPopup, DialogTitle, Input, Label, Select } from "@/ui"
import { type RecurringCreateValues, recurringCreateSchema } from "./recurring.schema"

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

  const createForm = useTanStackForm({
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
    } as RecurringCreateValues,
    validators: { onChange: recurringCreateSchema },
    onSubmit: async ({ value }) => {
      create.mutate(value as RecurringCreateValues)
    },
  })

  const resetCreate = (values?: RecurringCreateValues) => {
    createForm.reset(values)
  }

  const editForm = useTanStackForm({
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
    } as RecurringCreateValues,
    validators: { onChange: recurringCreateSchema },
    onSubmit: async ({ value }) => {
      update.mutate(value as RecurringCreateValues)
    },
  })

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
    onError: (e: unknown) => {
      applyApiErrorsToForm(createForm, e)
      onErr(e)
    },
  })

  const update = useMutation({
    mutationFn: (values: RecurringCreateValues) => {
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
    onError: (e: unknown) => {
      applyApiErrorsToForm(editForm, e)
      onErr(e)
    },
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
                            editForm.reset({
                              name: r.name,
                              payee: r.payee ?? "",
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
            onSubmit={(e) => {
              e.preventDefault()
              e.stopPropagation()
              void createForm.handleSubmit()
            }}
            className="space-y-4"
          >
            <createForm.Field name="name">
              {(field) => <FormField field={field} label="Nombre" />}
            </createForm.Field>
            <div className="grid grid-cols-2 gap-3">
              <createForm.Field name="type">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label>Tipo *</Label>
                    <Select
                      value={field.state.value as string}
                      onValueChange={(v) => v && field.handleChange(v as never)}
                      items={TYPE_ITEMS}
                    />
                  </div>
                )}
              </createForm.Field>
              <createForm.Field name="mode">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label>Modo *</Label>
                    <Select
                      value={field.state.value as string}
                      onValueChange={(v) => v && field.handleChange(v as never)}
                      items={MODE_ITEMS}
                    />
                  </div>
                )}
              </createForm.Field>
            </div>
            <createForm.Field name="accountId">
              {(field) => (
                <div className="space-y-1.5">
                  <Label>Cuenta *</Label>
                  <EntitySelect
                    value={field.state.value as number | null}
                    onChange={(v) => field.handleChange(v as never)}
                    queryKey={qk.accounts(false)}
                    queryFn={() => listAccounts(false)}
                  />
                  {(field.state.meta.errors[0] as { message?: string } | undefined)?.message && (
                    <p className="text-xs text-destructive">
                      {String((field.state.meta.errors[0] as { message?: string })?.message)}
                    </p>
                  )}
                </div>
              )}
            </createForm.Field>
            <createForm.Field name="amount">
              {(field) => {
                const currency = createForm.getFieldValue("currency") as string
                return (
                  <div className="space-y-1.5">
                    <Label>Monto * ({currency})</Label>
                    <MoneyInput
                      currency={currency}
                      value={
                        typeof field.state.value === "number" && Number.isFinite(field.state.value)
                          ? (field.state.value as number)
                          : null
                      }
                      onChange={(cents) => field.handleChange((cents ?? Number.NaN) as never)}
                    />
                    {(field.state.meta.errors[0] as { message?: string } | undefined)?.message && (
                      <p className="text-xs text-destructive">
                        {String((field.state.meta.errors[0] as { message?: string })?.message)}
                      </p>
                    )}
                  </div>
                )
              }}
            </createForm.Field>
            <div className="grid grid-cols-2 gap-3">
              <createForm.Field name="intervalCount">
                {(field) => (
                  <FormField
                    field={field}
                    label="Cada (cantidad)"
                    type="number"
                    min={1}
                    valueAsNumber
                  />
                )}
              </createForm.Field>
              <createForm.Field name="intervalUnit">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label>Unidad *</Label>
                    <Select
                      value={field.state.value as string}
                      onValueChange={(v) => v && field.handleChange(v as never)}
                      items={UNIT_ITEMS}
                    />
                    {(field.state.meta.errors[0] as { message?: string } | undefined)?.message && (
                      <p className="text-xs text-destructive">
                        {String((field.state.meta.errors[0] as { message?: string })?.message)}
                      </p>
                    )}
                  </div>
                )}
              </createForm.Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <createForm.Field name="startDate">
                {(field) => <FormField field={field} label="Inicio" type="date" />}
              </createForm.Field>
              <createForm.Field name="endDate">
                {(field) => <FormField field={field} label="Fin (opcional)" type="date" />}
              </createForm.Field>
            </div>
            <createForm.Field name="categoryId">
              {(field) => (
                <div className="space-y-1.5">
                  <Label>Categoría</Label>
                  <EntitySelect
                    value={field.state.value as number | null}
                    onChange={(v) => field.handleChange(v as never)}
                    queryKey={qk.categories(false)}
                    queryFn={() => listCategories(false)}
                    allowNullLabel="Sin categoría"
                  />
                </div>
              )}
            </createForm.Field>
            <createForm.Field name="payee">
              {(field) => <FormField field={field} label="Beneficiario" />}
            </createForm.Field>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setCreating(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={create.isPending || createForm.state.isSubmitting}>
                {create.isPending || createForm.state.isSubmitting ? "…" : "Crear"}
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
            onSubmit={(e) => {
              e.preventDefault()
              e.stopPropagation()
              void editForm.handleSubmit()
            }}
            className="space-y-4"
          >
            <editForm.Field name="name">
              {(field) => <FormField field={field} label="Nombre" />}
            </editForm.Field>
            <div className="grid grid-cols-2 gap-3">
              <editForm.Field name="type">
                {() => (
                  <div className="space-y-1.5">
                    <Label>Tipo (no editable)</Label>
                    <Select
                      value={editForm.getFieldValue("type") as string}
                      onValueChange={() => {}}
                      items={TYPE_ITEMS}
                      disabled
                    />
                  </div>
                )}
              </editForm.Field>
              <editForm.Field name="mode">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label>Modo *</Label>
                    <Select
                      value={field.state.value as string}
                      onValueChange={(v) => v && field.handleChange(v as never)}
                      items={MODE_ITEMS}
                    />
                  </div>
                )}
              </editForm.Field>
            </div>
            <editForm.Field name="accountId">
              {(field) => (
                <div className="space-y-1.5">
                  <Label>Cuenta *</Label>
                  <EntitySelect
                    value={field.state.value as number | null}
                    onChange={(v) => field.handleChange(v as never)}
                    queryKey={qk.accounts(false)}
                    queryFn={() => listAccounts(false)}
                  />
                  {(field.state.meta.errors[0] as { message?: string } | undefined)?.message && (
                    <p className="text-xs text-destructive">
                      {String((field.state.meta.errors[0] as { message?: string })?.message)}
                    </p>
                  )}
                </div>
              )}
            </editForm.Field>
            <editForm.Field name="amount">
              {(field) => {
                const currency = editForm.getFieldValue("currency") as string
                return (
                  <div className="space-y-1.5">
                    <Label>Monto * ({currency})</Label>
                    <MoneyInput
                      currency={currency}
                      value={
                        typeof field.state.value === "number" && Number.isFinite(field.state.value)
                          ? (field.state.value as number)
                          : null
                      }
                      onChange={(cents) => field.handleChange((cents ?? Number.NaN) as never)}
                    />
                    {(field.state.meta.errors[0] as { message?: string } | undefined)?.message && (
                      <p className="text-xs text-destructive">
                        {String((field.state.meta.errors[0] as { message?: string })?.message)}
                      </p>
                    )}
                  </div>
                )
              }}
            </editForm.Field>
            <div className="grid grid-cols-2 gap-3">
              <editForm.Field name="intervalCount">
                {(field) => (
                  <FormField
                    field={field}
                    label="Cada (cantidad)"
                    type="number"
                    min={1}
                    valueAsNumber
                  />
                )}
              </editForm.Field>
              <editForm.Field name="intervalUnit">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label>Unidad *</Label>
                    <Select
                      value={field.state.value as string}
                      onValueChange={(v) => v && field.handleChange(v as never)}
                      items={UNIT_ITEMS}
                    />
                    {(field.state.meta.errors[0] as { message?: string } | undefined)?.message && (
                      <p className="text-xs text-destructive">
                        {String((field.state.meta.errors[0] as { message?: string })?.message)}
                      </p>
                    )}
                  </div>
                )}
              </editForm.Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <editForm.Field name="startDate">
                {(field) => <FormField field={field} label="Inicio" type="date" />}
              </editForm.Field>
              <editForm.Field name="endDate">
                {(field) => <FormField field={field} label="Fin (opcional)" type="date" />}
              </editForm.Field>
            </div>
            <editForm.Field name="categoryId">
              {(field) => (
                <div className="space-y-1.5">
                  <Label>Categoría</Label>
                  <EntitySelect
                    value={field.state.value as number | null}
                    onChange={(v) => field.handleChange(v as never)}
                    queryKey={qk.categories(false)}
                    queryFn={() => listCategories(false)}
                    allowNullLabel="Sin categoría"
                  />
                </div>
              )}
            </editForm.Field>
            <editForm.Field name="payee">
              {(field) => <FormField field={field} label="Beneficiario" />}
            </editForm.Field>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setEditing(null)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={update.isPending || editForm.state.isSubmitting}>
                {update.isPending || editForm.state.isSubmitting ? "…" : "Guardar"}
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
