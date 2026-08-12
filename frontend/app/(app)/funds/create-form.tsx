"use client"

import { useStore, useForm as useTanStackForm } from "@tanstack/react-form"
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import { useState } from "react"
import { toast } from "sonner"
import { MoneyInput } from "@/components/money-input"
import { listCategories } from "@/lib/api/categories"
import { createFund, previewFund } from "@/lib/api/funds"
import type { FundCreate, FundPreview, FundRule } from "@/lib/api/types"
import { ApiError, applyApiErrorsToForm } from "@/lib/api/types"
import { accumulatesAs, type FundShape } from "@/lib/funds"
import { invalidate, qk } from "@/lib/query"
import { Button, Input, Label, Select } from "@/ui"
import { type CreateFundValues, createFundSchema } from "./funds.schema"
import { ruleConsequence, rulesFor } from "./rules"

const DEFAULT_WINDOW = 3

function defaults(month: string): CreateFundValues {
  return {
    categoryId: null,
    rule: "fixed",
    startMonth: month,
    amount: null,
    windowMonths: DEFAULT_WINDOW,
  }
}

function bodyOf(values: CreateFundValues, shape: FundShape): FundCreate {
  const body: FundCreate = {
    category_id: values.categoryId as number,
    rule: values.rule,
    start_month: values.startMonth,
    accumulates: accumulatesAs(shape),
  }
  if (values.rule === "fixed") body.amount = values.amount
  if (values.rule === "average") body.window_months = values.windowMonths
  return body
}

/**
 * What the server would be asked to work out for a rule the owner has not
 * chosen yet, or nothing when that rule still lacks the figure it is made of.
 *
 * A fixed rule asks whatever the owner types, so there is never anything to
 * work out for it.
 */
function previewBody(
  rule: FundRule,
  values: CreateFundValues,
  shape: FundShape,
): FundCreate | null {
  if (values.categoryId === null) return null
  const base: FundCreate = {
    category_id: values.categoryId,
    rule,
    start_month: values.startMonth,
    accumulates: accumulatesAs(shape),
  }
  if (rule === "from-recurring") return base
  if (rule === "average") {
    return values.windowMonths === null ? null : { ...base, window_months: values.windowMonths }
  }
  return null
}

/**
 * Whether a rule is worth offering for the category the owner picked.
 *
 * A category whose charges all land every month can only ever ask zero from
 * the rule that fills for charges — there are no months between one turn and
 * the next to spread over — so it is not offered one (AC-14).
 *
 * A category with nothing registered yet still is: the link beside the rule is
 * how the owner registers the first charge, and taking it away would close the
 * only door out of that state.
 */
function offerTheRule(rule: FundRule, preview: FundPreview | undefined): boolean {
  if (rule !== "from-recurring" || preview === undefined) return true
  return preview.has_something_to_spread || preview.would_ask === 0
}

export function CreateFundForm({
  shape,
  month,
  heldBy,
  onDone,
  onCancel,
}: {
  shape: FundShape
  month: string
  heldBy: Map<number, FundShape>
  onDone: () => void
  onCancel: () => void
}) {
  const qc = useQueryClient()
  const [warning, setWarning] = useState<string | null>(null)
  const [refusal, setRefusal] = useState<string | null>(null)

  const categories = useQuery({
    queryKey: qk.categories(false, false),
    queryFn: () => listCategories(false, false),
  })

  const form = useTanStackForm({
    defaultValues: defaults(month),
    validators: { onChange: createFundSchema },
    onSubmit: async ({ value }) => {
      if (warning === null) ask.mutate(value)
      else create.mutate(value)
    },
  })

  const values = useStore(form.store, (state) => state.values)
  const offers = rulesFor(shape)
  const chosen = categories.data?.find((c) => c.id === values.categoryId) ?? null

  const previews = useQueries({
    queries: offers.map((offer) => {
      const body = previewBody(offer.rule, values, shape)
      return {
        queryKey: qk.fundPreview(offer.rule, body),
        queryFn: () => previewFund(body as FundCreate),
        enabled: body !== null,
        retry: false,
      }
    }),
  })

  const offeredRules = offers
    .filter((offer, index) => offerTheRule(offer.rule, previews[index]?.data))
    .map((offer) => offer.rule)

  if (offeredRules.length > 0 && !offeredRules.includes(values.rule)) {
    form.setFieldValue("rule", offeredRules[0])
  }

  const onErr = (e: unknown) => {
    applyApiErrorsToForm(form, e)
    toast.error(e instanceof ApiError ? e.message : "Error")
  }

  const ask = useMutation({
    mutationFn: (v: CreateFundValues) => previewFund(bodyOf(v, shape)),
    onSuccess: (preview, v) => {
      if (preview.warning === null) create.mutate(v)
      else setWarning(preview.warning)
    },
    onError: onErr,
  })

  const create = useMutation({
    mutationFn: (v: CreateFundValues) => createFund(bodyOf(v, shape)),
    onSuccess: () => {
      toast.success(shape === "fondo" ? "Fondo creado" : "Presupuesto creado")
      invalidate(qc, "fundWrite")
      onDone()
    },
    onError: onErr,
  })

  const clearTheAnswer = () => {
    setWarning(null)
    setRefusal(null)
  }

  const refusalFor = (v: CreateFundValues): string | null => {
    const already = v.categoryId === null ? undefined : heldBy.get(v.categoryId)
    if (already !== undefined && chosen !== null) {
      return `${chosen.name} ya tiene un ${already}. Cámbialo en vez de crear otro.`
    }
    if (v.rule === "fixed" && v.amount === null) {
      return `El ${shape} necesita su monto mensual.`
    }
    return null
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const stated = refusalFor(form.state.values)
    if (stated !== null) {
      setWarning(null)
      setRefusal(stated)
      return
    }
    setRefusal(null)
    void form.handleSubmit()
  }

  const categoryItems = (categories.data ?? []).map((c) => {
    const already = heldBy.get(c.id)
    return {
      value: String(c.id),
      label: already === undefined ? c.name : `${c.name} — ya tiene un ${already}`,
    }
  })

  const announcement = refusal ?? warning

  return (
    <form
      onSubmit={submit}
      className="space-y-4 rounded-lg border p-5"
      style={{ borderColor: "var(--border)", background: "var(--card)" }}
    >
      <p className="text-sm font-medium">Estás creando un {shape}.</p>

      <form.Field name="categoryId">
        {(field) => (
          <div className="space-y-1.5">
            <Label htmlFor="fund-category">Categoría *</Label>
            <Select
              id="fund-category"
              value={field.state.value === null ? null : String(field.state.value)}
              onValueChange={(v) => {
                field.handleChange(v === null ? null : Number(v))
                clearTheAnswer()
              }}
              items={categoryItems}
              placeholder={categories.isLoading ? "Cargando…" : "Selecciona…"}
              disabled={categories.isLoading}
            />
          </div>
        )}
      </form.Field>

      <form.Field name="rule">
        {(field) => (
          <fieldset className="space-y-3">
            <legend className="mb-2 text-sm font-medium">
              {shape === "fondo" ? "¿Cómo aparta la plata?" : "¿Cómo se pone el tope?"}
            </legend>
            {offers.map((offer, index) => {
              if (!offeredRules.includes(offer.rule)) return null
              const wouldAsk = previews[index]?.data?.would_ask ?? null
              const why = ruleConsequence(offer.rule, shape, {
                wouldAsk,
                categoryName: chosen?.name ?? null,
                windowMonths: values.windowMonths ?? DEFAULT_WINDOW,
              })
              const missingCharges = offer.rule === "from-recurring" && wouldAsk === 0
              return (
                <div key={offer.rule} className="flex gap-2.5">
                  <input
                    type="radio"
                    id={`rule-${offer.rule}`}
                    name="fund-rule"
                    className="mt-1"
                    checked={field.state.value === offer.rule}
                    aria-describedby={`why-${offer.rule}`}
                    onChange={() => {
                      field.handleChange(offer.rule)
                      clearTheAnswer()
                    }}
                  />
                  <div className="space-y-0.5">
                    <Label htmlFor={`rule-${offer.rule}`}>{offer.label}</Label>
                    <p
                      id={`why-${offer.rule}`}
                      className="text-xs"
                      style={{ color: "var(--muted-foreground)" }}
                    >
                      {why}
                    </p>
                    {missingCharges && (
                      <Link
                        href="/recurring"
                        className="inline-block text-xs underline underline-offset-2"
                      >
                        Registrar un cobro recurrente
                      </Link>
                    )}
                  </div>
                </div>
              )
            })}
          </fieldset>
        )}
      </form.Field>

      {values.rule === "fixed" && (
        <form.Field name="amount">
          {(field) => (
            <div className="space-y-1.5">
              <Label htmlFor="fund-amount">Monto mensual * (COP)</Label>
              <MoneyInput
                id="fund-amount"
                currency="COP"
                value={field.state.value}
                onChange={(cents) => {
                  field.handleChange(cents)
                  clearTheAnswer()
                }}
              />
            </div>
          )}
        </form.Field>
      )}

      {values.rule === "average" && (
        <form.Field name="windowMonths">
          {(field) => (
            <div className="space-y-1.5">
              <Label htmlFor="fund-window">Meses a promediar *</Label>
              <Input
                id="fund-window"
                type="number"
                min={1}
                value={field.state.value === null ? "" : String(field.state.value)}
                onChange={(e) =>
                  field.handleChange(e.target.value === "" ? null : Number(e.target.value))
                }
              />
            </div>
          )}
        </form.Field>
      )}

      <form.Field name="startMonth">
        {(field) => (
          <div className="space-y-1.5">
            <Label htmlFor="fund-start">Empieza en *</Label>
            <Input
              id="fund-start"
              type="month"
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value)}
            />
          </div>
        )}
      </form.Field>

      {announcement !== null && (
        <p className="text-sm" style={{ color: "var(--destructive)" }} role="alert">
          {announcement}
        </p>
      )}

      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancelar
        </Button>
        <Button type="submit" disabled={ask.isPending || create.isPending}>
          {warning === null ? "Crear" : "Crear de todos modos"}
        </Button>
      </div>
    </form>
  )
}
