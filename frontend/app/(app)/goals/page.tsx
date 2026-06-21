"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { EmptyState } from "@/components/empty-state"
import { EntitySelect } from "@/components/entity-select"
import { ErrorState } from "@/components/error-state"
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
import { Button, Dialog, DialogPopup, DialogTitle, Input, Label } from "@/ui"

export default function GoalsPage() {
  const qc = useQueryClient()
  const goals = useQuery({ queryKey: qk.goals(), queryFn: () => listGoals() })
  const progress = useQuery({ queryKey: qk.goalsProgress(), queryFn: () => goalsProgress() })

  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Goal | null>(null)
  const [pausing, setPausing] = useState<Goal | null>(null)
  const [contributing, setContributing] = useState<Goal | null>(null)

  const [name, setName] = useState("")
  const [monthly, setMonthly] = useState<number | null>(null)
  const [savingsId, setSavingsId] = useState<number | null>(null)
  const [target, setTarget] = useState<number | null>(null)
  const [deadline, setDeadline] = useState("")
  const [amount, setAmount] = useState<number | null>(null)
  const [date, setDate] = useState("")

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error")
  const done = (msg: string) => {
    toast.success(msg)
    invalidate(qc, "goalWrite")
  }
  const resetForm = () => {
    setName("")
    setMonthly(null)
    setSavingsId(null)
    setTarget(null)
    setDeadline("")
  }

  const create = useMutation({
    mutationFn: () => {
      if (monthly === null || savingsId === null) {
        throw new Error("monthly and savingsId are required")
      }
      return createGoal({
        name,
        monthly_amount: monthly,
        savings_account_id: savingsId,
        target_amount: target,
        deadline: deadline || null,
      })
    },
    onSuccess: () => {
      done("Meta creada")
      setCreating(false)
      resetForm()
    },
    onError: onErr,
  })
  const update = useMutation({
    mutationFn: () => {
      if (!editing) throw new Error("editing goal is required")
      return updateGoal(editing.id, {
        name,
        monthly_amount: monthly ?? undefined,
        target_amount: target,
        deadline: deadline || null,
        savings_account_id: savingsId ?? undefined,
      })
    },
    onSuccess: () => {
      done("Meta actualizada")
      setEditing(null)
      resetForm()
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
    mutationFn: () => {
      if (!contributing || amount === null) {
        throw new Error("contributing goal and amount are required")
      }
      return contributeGoal(contributing.id, { amount, date })
    },
    onSuccess: () => {
      done("Aporte registrado")
      setContributing(null)
      setAmount(null)
      setDate("")
    },
    onError: onErr,
  })

  const createInvalid = !name || monthly === null || savingsId === null || !!target !== !!deadline
  const editInvalid = !name || !!target !== !!deadline

  const savedFor = (id: number) => progress.data?.find((p) => p.goal_id === id)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Metas"
        action={
          <Button
            onClick={() => {
              resetForm()
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
                            setAmount(null)
                            setDate("")
                          }}
                        >
                          Aportar
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setEditing(g)
                            setName(g.name)
                            setMonthly(g.monthly_amount)
                            setSavingsId(g.savings_account_id)
                            setTarget(g.target_amount)
                            setDeadline(g.deadline ?? "")
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

      {/* Create / edit dialog (shared fields) */}
      <Dialog
        open={creating || editing !== null}
        onOpenChange={(o) => {
          if (!o) {
            setCreating(false)
            setEditing(null)
          }
        }}
      >
        <DialogPopup className="max-w-md">
          <DialogTitle>{editing ? "Editar meta" : "Nueva meta"}</DialogTitle>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (editing ? !editInvalid : !createInvalid) (editing ? update : create).mutate()
            }}
            className="space-y-4"
          >
            <div className="space-y-1.5">
              <Label>Nombre *</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Aporte mensual * (COP)</Label>
              <MoneyInput currency="COP" value={monthly} onChange={setMonthly} />
            </div>
            <div className="space-y-1.5">
              <Label>Cuenta de ahorro *</Label>
              <EntitySelect
                value={savingsId}
                onChange={setSavingsId}
                queryKey={qk.accounts(false)}
                queryFn={() => listAccounts(false)}
              />
            </div>
            <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
              Meta definida: completa objetivo y fecha. Abierta: deja ambos vacíos.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Objetivo (COP)</Label>
                <MoneyInput currency="COP" value={target} onChange={setTarget} />
              </div>
              <div className="space-y-1.5">
                <Label>Fecha límite</Label>
                <Input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setCreating(false)
                  setEditing(null)
                }}
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={
                  (editing ? editInvalid : createInvalid) || create.isPending || update.isPending
                }
              >
                {create.isPending || update.isPending ? "…" : "Guardar"}
              </Button>
            </div>
          </form>
        </DialogPopup>
      </Dialog>

      {/* Contribute dialog */}
      <Dialog open={contributing !== null} onOpenChange={(o) => !o && setContributing(null)}>
        <DialogPopup className="max-w-sm">
          <DialogTitle>Aportar a {contributing?.name}</DialogTitle>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (amount !== null && date) contribute.mutate()
            }}
            className="space-y-4"
          >
            <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
              Transfiere desde tu cuenta origen predeterminada (configúrala en Ajustes).
            </p>
            <div className="space-y-1.5">
              <Label>Monto * (COP)</Label>
              <MoneyInput currency="COP" value={amount} onChange={setAmount} />
            </div>
            <div className="space-y-1.5">
              <Label>Fecha *</Label>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setContributing(null)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={amount === null || !date || contribute.isPending}>
                {contribute.isPending ? "…" : "Aportar"}
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
