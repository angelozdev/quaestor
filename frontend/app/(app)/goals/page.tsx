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
import { MoneyInput } from "@/components/money-input"
import { PageHeader } from "@/components/page-header"
import { StatusBadge } from "@/components/status-badge"
import { listAccounts } from "@/lib/api/accounts"
import {
  contributeGoal,
  createGoal,
  goalsProgress,
  listGoals,
  pauseGoal,
  restoreGoal,
  updateGoal,
} from "@/lib/api/goals"
import { ApiError, type Goal } from "@/lib/api/types"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { Button, Dialog, DialogPopup, DialogTitle, Label } from "@/ui"
import {
  type ContributeGoalValues,
  contributeGoalSchema,
  type GoalUpsertValues,
  goalUpsertSchema,
} from "./goals.schema"

const CREATE_DEFAULTS: GoalUpsertValues = {
  name: "",
  monthlyAmount: Number.NaN,
  savingsAccountId: null,
  targetAmount: Number.NaN,
  deadline: "",
}

const EDIT_DEFAULTS: GoalUpsertValues = {
  name: "",
  monthlyAmount: Number.NaN,
  savingsAccountId: null,
  targetAmount: Number.NaN,
  deadline: "",
}

const CONTRIBUTE_DEFAULTS: ContributeGoalValues = {
  amount: Number.NaN,
  date: new Date().toISOString().slice(0, 10),
}

export default function GoalsPage() {
  const qc = useQueryClient()
  const goals = useQuery({ queryKey: qk.goals(), queryFn: () => listGoals() })
  const progress = useQuery({ queryKey: qk.goalsProgress(), queryFn: () => goalsProgress() })

  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Goal | null>(null)
  const [pausing, setPausing] = useState<Goal | null>(null)
  const [contributing, setContributing] = useState<Goal | null>(null)

  const createForm = useTanStackForm({
    defaultValues: CREATE_DEFAULTS,
    validators: { onChange: goalUpsertSchema },
    onSubmit: async ({ value }) => {
      create.mutate(value)
    },
  })

  const editForm = useTanStackForm({
    defaultValues: EDIT_DEFAULTS,
    validators: { onChange: goalUpsertSchema },
    onSubmit: async ({ value }) => {
      update.mutate(value)
    },
  })

  const contributeForm = useTanStackForm({
    defaultValues: CONTRIBUTE_DEFAULTS,
    validators: { onChange: contributeGoalSchema },
    onSubmit: async ({ value }) => {
      contribute.mutate(value)
    },
  })

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error")
  const done = (msg: string) => {
    toast.success(msg)
    invalidate(qc, "goalWrite")
  }

  const create = useMutation({
    mutationFn: (values: GoalUpsertValues) => {
      return createGoal({
        name: values.name,
        monthly_amount: values.monthlyAmount,
        savings_account_id: values.savingsAccountId as number,
        target_amount:
          values.targetAmount !== undefined && Number.isFinite(values.targetAmount)
            ? values.targetAmount
            : null,
        deadline: values.deadline && values.deadline.length > 0 ? values.deadline : null,
      })
    },
    onSuccess: () => {
      done("Meta creada")
      setCreating(false)
      createForm.reset(CREATE_DEFAULTS)
    },
    onError: onErr,
  })
  const update = useMutation({
    mutationFn: (values: GoalUpsertValues) => {
      if (!editing) throw new Error("editing goal is required")
      return updateGoal(editing.id, {
        name: values.name,
        monthly_amount: values.monthlyAmount,
        target_amount:
          values.targetAmount !== undefined && Number.isFinite(values.targetAmount)
            ? values.targetAmount
            : null,
        deadline: values.deadline && values.deadline.length > 0 ? values.deadline : null,
        savings_account_id: values.savingsAccountId ?? undefined,
      })
    },
    onSuccess: () => {
      done("Meta actualizada")
      setEditing(null)
      editForm.reset(EDIT_DEFAULTS)
    },
    onError: onErr,
  })
  const pause = useMutation({
    mutationFn: () => {
      if (!pausing) throw new Error("pausing goal is required")
      return pauseGoal(pausing.id)
    },
    onSuccess: () => {
      done("Meta pausada")
      setPausing(null)
    },
    onError: onErr,
  })
  const restore = useMutation({
    mutationFn: (g: Goal) => restoreGoal(g.id),
    onSuccess: () => done("Meta restaurada"),
    onError: onErr,
  })
  const contribute = useMutation({
    mutationFn: (values: ContributeGoalValues) => {
      if (!contributing) throw new Error("contributing goal is required")
      return contributeGoal(contributing.id, { amount: values.amount, date: values.date })
    },
    onSuccess: () => {
      done("Aporte registrado")
      setContributing(null)
      contributeForm.reset(CONTRIBUTE_DEFAULTS)
    },
    onError: onErr,
  })

  const savedFor = (id: number) => progress.data?.find((p) => p.goal_id === id)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Metas"
        action={
          <Button
            onClick={() => {
              createForm.reset(CREATE_DEFAULTS)
              setCreating(true)
            }}
          >
            Nueva
          </Button>
        }
      />

      {goals.isError && (
        <ErrorState message="No se pudieron cargar las metas" onRetry={() => goals.refetch()} />
      )}
      {goals.data && goals.data.length === 0 && <EmptyState message="Sin metas" />}

      {goals.data && goals.data.length > 0 && (
        <div className="space-y-3">
          {goals.data.map((g) => {
            const p = savedFor(g.id)
            const pct =
              g.target_amount && p
                ? Math.min(100, Math.round((p.saved / g.target_amount) * 100))
                : null
            return (
              <div
                key={g.id}
                className="space-y-3 rounded-lg border p-5"
                style={{ borderColor: "var(--border)", background: "var(--card)" }}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2 font-medium">
                    {g.name} <StatusBadge kind="goal" value={g.status} />
                  </span>
                  <div className="flex gap-1">
                    {g.status === "paused" || g.status === "reached" ? (
                      g.status === "paused" ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={restore.isPending}
                          onClick={() => restore.mutate(g)}
                        >
                          Restaurar
                        </Button>
                      ) : null
                    ) : (
                      <>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setContributing(g)
                            contributeForm.reset(CONTRIBUTE_DEFAULTS)
                          }}
                        >
                          Aportar
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setEditing(g)
                            editForm.reset({
                              name: g.name,
                              monthlyAmount: g.monthly_amount,
                              savingsAccountId: g.savings_account_id,
                              targetAmount: g.target_amount ?? Number.NaN,
                              deadline: g.deadline ?? "",
                            })
                          }}
                        >
                          Editar
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setPausing(g)}>
                          Pausar
                        </Button>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span style={{ color: "var(--muted-foreground)" }}>
                    {formatCents(p?.saved ?? 0, "COP")}
                    {g.target_amount !== null && ` / ${formatCents(g.target_amount, "COP")}`}
                  </span>
                  {pct !== null && <span className="tabular-nums">{pct}%</span>}
                </div>
                {pct !== null && (
                  <div
                    className="h-1.5 overflow-hidden rounded-full"
                    style={{ background: "var(--muted)" }}
                  >
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${pct}%`, background: "var(--foreground)" }}
                    />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Create dialog */}
      <Dialog
        open={creating}
        onOpenChange={(o) => {
          if (!o) {
            setCreating(false)
            createForm.reset(CREATE_DEFAULTS)
          }
        }}
      >
        <DialogPopup className="max-w-md">
          <DialogTitle>Nueva meta</DialogTitle>
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
            <createForm.Field name="monthlyAmount">
              {(field) => {
                const error = field.state.meta.errors[0] as { message?: string } | undefined
                return (
                  <div className="space-y-1.5">
                    <Label>Aporte mensual * (COP)</Label>
                    <MoneyInput
                      currency="COP"
                      value={
                        typeof field.state.value === "number" && Number.isFinite(field.state.value)
                          ? (field.state.value as number)
                          : null
                      }
                      onChange={(cents) => field.handleChange((cents ?? Number.NaN) as never)}
                    />
                    {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                  </div>
                )
              }}
            </createForm.Field>
            <createForm.Field name="savingsAccountId">
              {(field) => {
                const error = field.state.meta.errors[0] as { message?: string } | undefined
                return (
                  <div className="space-y-1.5">
                    <Label>Cuenta de ahorro *</Label>
                    <EntitySelect
                      value={field.state.value as number | null}
                      onChange={(v) => field.handleChange(v as never)}
                      queryKey={qk.accounts(false)}
                      queryFn={() => listAccounts(false)}
                    />
                    {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                  </div>
                )
              }}
            </createForm.Field>
            <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
              Meta definida: completa objetivo y fecha. Abierta: deja ambos vacíos.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <createForm.Field name="targetAmount">
                {(field) => {
                  const error = field.state.meta.errors[0] as { message?: string } | undefined
                  return (
                    <div className="space-y-1.5">
                      <Label>Objetivo (COP)</Label>
                      <MoneyInput
                        currency="COP"
                        value={
                          typeof field.state.value === "number" &&
                          Number.isFinite(field.state.value)
                            ? (field.state.value as number)
                            : null
                        }
                        onChange={(cents) => field.handleChange((cents ?? Number.NaN) as never)}
                      />
                      {error?.message && (
                        <p className="text-xs text-destructive">{error.message}</p>
                      )}
                    </div>
                  )
                }}
              </createForm.Field>
              <createForm.Field name="deadline">
                {(field) => <FormField field={field} label="Fecha límite" type="date" />}
              </createForm.Field>
            </div>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setCreating(false)
                  createForm.reset(CREATE_DEFAULTS)
                }}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={create.isPending || createForm.state.isSubmitting}>
                {create.isPending || createForm.state.isSubmitting ? "…" : "Guardar"}
              </Button>
            </div>
          </form>
        </DialogPopup>
      </Dialog>

      {/* Edit dialog */}
      <Dialog
        open={editing !== null}
        onOpenChange={(o) => {
          if (!o) {
            setEditing(null)
            editForm.reset(EDIT_DEFAULTS)
          }
        }}
      >
        <DialogPopup className="max-w-md">
          <DialogTitle>Editar meta</DialogTitle>
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
            <editForm.Field name="monthlyAmount">
              {(field) => {
                const error = field.state.meta.errors[0] as { message?: string } | undefined
                return (
                  <div className="space-y-1.5">
                    <Label>Aporte mensual * (COP)</Label>
                    <MoneyInput
                      currency="COP"
                      value={
                        typeof field.state.value === "number" && Number.isFinite(field.state.value)
                          ? (field.state.value as number)
                          : null
                      }
                      onChange={(cents) => field.handleChange((cents ?? Number.NaN) as never)}
                    />
                    {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                  </div>
                )
              }}
            </editForm.Field>
            <editForm.Field name="savingsAccountId">
              {(field) => {
                const error = field.state.meta.errors[0] as { message?: string } | undefined
                return (
                  <div className="space-y-1.5">
                    <Label>Cuenta de ahorro *</Label>
                    <EntitySelect
                      value={field.state.value as number | null}
                      onChange={(v) => field.handleChange(v as never)}
                      queryKey={qk.accounts(false)}
                      queryFn={() => listAccounts(false)}
                    />
                    {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                  </div>
                )
              }}
            </editForm.Field>
            <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
              Meta definida: completa objetivo y fecha. Abierta: deja ambos vacíos.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <editForm.Field name="targetAmount">
                {(field) => {
                  const error = field.state.meta.errors[0] as { message?: string } | undefined
                  return (
                    <div className="space-y-1.5">
                      <Label>Objetivo (COP)</Label>
                      <MoneyInput
                        currency="COP"
                        value={
                          typeof field.state.value === "number" &&
                          Number.isFinite(field.state.value)
                            ? (field.state.value as number)
                            : null
                        }
                        onChange={(cents) => field.handleChange((cents ?? Number.NaN) as never)}
                      />
                      {error?.message && (
                        <p className="text-xs text-destructive">{error.message}</p>
                      )}
                    </div>
                  )
                }}
              </editForm.Field>
              <editForm.Field name="deadline">
                {(field) => <FormField field={field} label="Fecha límite" type="date" />}
              </editForm.Field>
            </div>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setEditing(null)
                  editForm.reset(EDIT_DEFAULTS)
                }}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={update.isPending || editForm.state.isSubmitting}>
                {update.isPending || editForm.state.isSubmitting ? "…" : "Guardar"}
              </Button>
            </div>
          </form>
        </DialogPopup>
      </Dialog>

      {/* Contribute dialog */}
      <Dialog
        open={contributing !== null}
        onOpenChange={(o) => {
          if (!o) {
            setContributing(null)
            contributeForm.reset(CONTRIBUTE_DEFAULTS)
          }
        }}
      >
        <DialogPopup className="max-w-sm">
          <DialogTitle>Aportar a {contributing?.name}</DialogTitle>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              e.stopPropagation()
              void contributeForm.handleSubmit()
            }}
            className="space-y-4"
          >
            <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
              Transfiere desde tu cuenta origen predeterminada (configúrala en Ajustes).
            </p>
            <contributeForm.Field name="amount">
              {(field) => {
                const error = field.state.meta.errors[0] as { message?: string } | undefined
                return (
                  <div className="space-y-1.5">
                    <Label>Monto * (COP)</Label>
                    <MoneyInput
                      currency="COP"
                      value={
                        typeof field.state.value === "number" && Number.isFinite(field.state.value)
                          ? (field.state.value as number)
                          : null
                      }
                      onChange={(cents) => field.handleChange((cents ?? Number.NaN) as never)}
                    />
                    {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                  </div>
                )
              }}
            </contributeForm.Field>
            <contributeForm.Field name="date">
              {(field) => <FormField field={field} label="Fecha" type="date" />}
            </contributeForm.Field>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setContributing(null)
                  contributeForm.reset(CONTRIBUTE_DEFAULTS)
                }}
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={contribute.isPending || contributeForm.state.isSubmitting}
              >
                {contribute.isPending || contributeForm.state.isSubmitting ? "…" : "Aportar"}
              </Button>
            </div>
          </form>
        </DialogPopup>
      </Dialog>

      <ConfirmDialog
        open={pausing !== null}
        onOpenChange={(o) => !o && setPausing(null)}
        title="Pausar meta"
        description={`Se pausará "${pausing?.name}". Tus aportes se mantienen. Puedes restaurarla luego.`}
        confirmLabel="Pausar"
        pending={pause.isPending}
        onConfirm={() => pausing && pause.mutate()}
      />
    </div>
  )
}
