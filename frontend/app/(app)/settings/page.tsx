"use client"

import { useForm as useTanStackForm } from "@tanstack/react-form"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { toast } from "sonner"
import { EntitySelect } from "@/components/entity-select"
import { PageHeader } from "@/components/page-header"
import { ApiError, applyApiErrorsToForm } from "@/lib/api"
import { listAccounts } from "@/lib/api/accounts"
import { getFx, setFx } from "@/lib/api/fx"
import { getSettings, updateSettings } from "@/lib/api/settings"
import { invalidate, qk } from "@/lib/query"
import { Button, Input, Label } from "@/ui"
import { type SetTrmValues, setTrmSchema } from "./settings.schema"

const TRM_DEFAULTS: SetTrmValues = {
  usdCop: Number.NaN,
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h2 className="text-sm font-medium" style={{ color: "var(--muted-foreground)" }}>
        {title}
      </h2>
      <div
        className="space-y-4 rounded-lg border p-5"
        style={{ borderColor: "var(--border)", background: "var(--card)" }}
      >
        {children}
      </div>
    </div>
  )
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
    <div className="space-y-6">
      <PageHeader title="Ajustes" />

      <Section title="Cuenta origen por defecto">
        <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
          Cuenta usada como origen de las contribuciones a metas y transferencias planeadas.
        </p>
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
      </Section>

      <Section title="TRM (USD→COP)">
        <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
          Una sola tasa vigente para toda la app: el job diario la refresca y aquí puedes corregirla
          manualmente. TRM actual:{" "}
          {trm.isLoading
            ? "…"
            : trmMissing
              ? "Sin TRM registrada"
              : trm.data
                ? trm.data.usd_cop
                : "—"}
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            e.stopPropagation()
            void trmForm.handleSubmit()
          }}
          className="space-y-3"
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
                  <Label htmlFor={field.name}>TRM actual *</Label>
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
