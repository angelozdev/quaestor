"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { format } from "date-fns"
import { useEffect, useState } from "react"
import { toast } from "sonner"
import { EntitySelect } from "@/components/entity-select"
import { PageHeader } from "@/components/page-header"
import { ApiError } from "@/lib/api"
import { listAccounts } from "@/lib/api/accounts"
import { getFx, setFx } from "@/lib/api/fx"
import { getSettings, updateSettings } from "@/lib/api/settings"
import { invalidate, qk } from "@/lib/query"
import { Button, Input, Label } from "@/ui"

const TODAY = format(new Date(), "yyyy-MM-dd")

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
  const fx = useQuery({
    queryKey: qk.fx(),
    queryFn: () => getFx(),
    retry: false, // a 409 MissingRate is an expected "no rate yet" state, not a transient error
  })

  const [sourceId, setSourceId] = useState<number | null>(null)
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (settings.data) setSourceId(settings.data.default_source_account_id)
  }, [settings.data])

  const [fxDate, setFxDate] = useState(TODAY)
  const [usdCop, setUsdCop] = useState("")

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error")

  const saveSettings = useMutation({
    mutationFn: () => updateSettings({ default_source_account_id: sourceId }),
    onSuccess: () => {
      toast.success("Ajustes guardados")
      invalidate(qc, "settingsWrite")
    },
    onError: onErr,
  })

  const saveFx = useMutation({
    mutationFn: () => setFx({ date: fxDate, usd_cop: usdCop }),
    onSuccess: () => {
      toast.success("Tasa registrada")
      invalidate(qc, "fxWrite")
      setUsdCop("")
    },
    onError: onErr,
  })

  const fxMissing = fx.isError && fx.error instanceof ApiError && fx.error.code === "MissingRate"

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

      <Section title="Tasa USD→COP (override manual)">
        <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
          Tasa actual:{" "}
          {fx.isLoading
            ? "…"
            : fxMissing
              ? "Sin tasa registrada"
              : fx.data
                ? `${fx.data.usd_cop} (${fx.data.date})`
                : "—"}
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (usdCop) saveFx.mutate()
          }}
          className="grid grid-cols-2 gap-3"
        >
          <div className="space-y-1.5">
            <Label>Fecha</Label>
            <Input type="date" value={fxDate} onChange={(e) => setFxDate(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>USD→COP</Label>
            <Input
              inputMode="decimal"
              value={usdCop}
              onChange={(e) => setUsdCop(e.target.value)}
              placeholder="4000.00"
            />
          </div>
          <div className="col-span-2 flex justify-end">
            <Button type="submit" disabled={!usdCop || saveFx.isPending}>
              {saveFx.isPending ? "…" : "Registrar tasa"}
            </Button>
          </div>
        </form>
      </Section>
    </div>
  )
}
