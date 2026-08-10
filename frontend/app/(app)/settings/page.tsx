"use client"

import { useForm as useTanStackForm } from "@tanstack/react-form"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { toast } from "sonner"
import { EntitySelect } from "@/components/entity-select"
import { Section, Term } from "@/components/ledger"
import { PageHeader } from "@/components/page-header"
import { ApiError, applyApiErrorsToForm } from "@/lib/api"
import { listAccounts } from "@/lib/api/accounts"
import { getFx, setFx } from "@/lib/api/fx"
import { getSettings, updateSettings } from "@/lib/api/settings"
import { formatRate } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { Button, Input, Label } from "@/ui"
import { type SetTrmValues, setTrmSchema } from "./settings.schema"

const TRM_DEFAULTS: SetTrmValues = {
  usdCop: Number.NaN,
}

export default function SettingsPage() {
  const qc = useQueryClient()
  const settings = useQuery({ queryKey: qk.settings(), queryFn: () => getSettings() })
  const trm = useQuery({
    queryKey: qk.fx(),
    queryFn: () => getFx(),
    retry: false,
  })

  const [sourceId, setSourceId] = useState<number | null>(null)
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (settings.data) setSourceId(settings.data.default_source_account_id)
  }, [settings.data])

  const trmForm = useTanStackForm({
    defaultValues: TRM_DEFAULTS,
    validators: { onChange: setTrmSchema },
    onSubmit: async ({ value }) => {
      saveTrm.mutate(value)
    },
  })

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error")

  const saveSettings = useMutation({
    mutationFn: () => updateSettings({ default_source_account_id: sourceId }),
    onSuccess: () => {
      toast.success("Ajustes guardados")
      invalidate(qc, "settingsWrite")
    },
    onError: onErr,
  })

  const saveTrm = useMutation({
    mutationFn: (values: SetTrmValues) => setFx({ usd_cop: String(values.usdCop) }),
    onSuccess: () => {
      toast.success("TRM actualizada")
      invalidate(qc, "fxWrite")
      trmForm.reset(TRM_DEFAULTS)
    },
    onError: (e: unknown) => {
      applyApiErrorsToForm(trmForm, e)
      onErr(e)
    },
  })

  const trmMissing =
    trm.isError && trm.error instanceof ApiError && trm.error.code === "MissingRate"

  return (
    <div className="space-y-10">
      <PageHeader title="Ajustes" />

      <Section label="Cuenta origen por defecto">
        <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
          Cuenta usada como origen de las transferencias planeadas.
        </p>
        <div className="max-w-md space-y-3">
          <div className="space-y-1.5">
            <Label>Cuenta origen</Label>
            <EntitySelect
              value={sourceId}
              onChange={setSourceId}
              queryKey={qk.accounts(false)}
              queryFn={() => listAccounts(false)}
              allowNullLabel="Ninguna"
            />
          </div>
          <div className="flex justify-end">
            <Button onClick={() => saveSettings.mutate()} disabled={saveSettings.isPending}>
              {saveSettings.isPending ? "…" : "Guardar"}
            </Button>
          </div>
        </div>
      </Section>

      <Section label="TRM (USD→COP)">
        <p className="max-w-prose text-sm" style={{ color: "var(--muted-foreground)" }}>
          Una sola tasa vigente para toda la app, y la actualizas tú: por ahora no se refresca sola.
          Sin una tasa puesta, las pantallas que muestran pesos no pueden leerse.
        </p>
        <div className="max-w-md">
          <Term label="TRM vigente">
            <span className="text-sm font-medium tabular-nums">
              {trm.isLoading
                ? "…"
                : trmMissing
                  ? "Sin TRM registrada"
                  : trm.data
                    ? `$ ${formatRate(Number(trm.data.usd_cop))}`
                    : "—"}
            </span>
          </Term>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            e.stopPropagation()
            void trmForm.handleSubmit()
          }}
          className="max-w-md space-y-3"
        >
          <trmForm.Field name="usdCop">
            {(field) => {
              const error = field.state.meta.errors[0] as { message?: string } | undefined
              const raw =
                typeof field.state.value === "number" && Number.isFinite(field.state.value)
                  ? String(field.state.value)
                  : ""
              return (
                <div className="space-y-1.5">
                  <Label htmlFor={field.name}>Nueva TRM</Label>
                  <Input
                    id={field.name}
                    inputMode="decimal"
                    value={raw}
                    placeholder="4000.00"
                    onChange={(e) => {
                      const v = e.target.value
                      field.handleChange(v === "" ? Number.NaN : Number(v))
                    }}
                    onBlur={field.handleBlur}
                    aria-invalid={error?.message ? true : undefined}
                  />
                  {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                </div>
              )
            }}
          </trmForm.Field>
          <div className="flex justify-end">
            <Button type="submit" disabled={saveTrm.isPending || trmForm.state.isSubmitting}>
              {saveTrm.isPending || trmForm.state.isSubmitting ? "…" : "Guardar TRM"}
            </Button>
          </div>
        </form>
      </Section>
    </div>
  )
}
