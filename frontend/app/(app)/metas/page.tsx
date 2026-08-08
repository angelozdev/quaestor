"use client"

import { useQuery } from "@tanstack/react-query"
import { format } from "date-fns"
import { useState } from "react"
import { EmptyState } from "@/components/empty-state"
import { PageHeader } from "@/components/page-header"
import { QueryBoundary } from "@/components/query-boundary"
import { HelpSection, ScreenHelp } from "@/components/screen-help"
import { SkeletonRows } from "@/components/skeleton"
import { listMetas } from "@/lib/api/metas"
import type { MetaStatus } from "@/lib/api/types"
import { monthNameOf } from "@/lib/date"
import { formatCents } from "@/lib/money"
import { qk } from "@/lib/query"
import { Button } from "@/ui"
import { CreateMetaForm } from "./create-form"

const WHAT_A_META_IS =
  "una cosa con nombre y con final — un celular, un televisor — que no vive en ninguna categoría"
const WHAT_A_FONDO_IS = "va juntando lo que le sobra a una categoría, mes a mes"
const WHAT_A_PRESUPUESTO_IS = "es un tope del mes: lo que no gastes no se guarda"

function waitingOn(meta: MetaStatus): string | null {
  if (meta.complete && !meta.closed) return "cumplida"
  if (meta.waiting) return `venció en ${monthNameOf(meta.target_month)}`
  return null
}

function MetaCard({ meta }: { meta: MetaStatus }) {
  const waiting = waitingOn(meta)
  return (
    <li className="space-y-1 rounded-md border p-3" style={{ borderColor: "var(--border)" }}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <span className="font-medium">{meta.name}</span>
        {waiting !== null && (
          <span className="text-xs" style={{ color: "var(--muted-foreground)" }}>
            {waiting}
          </span>
        )}
      </div>
      <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
        Quiere {formatCents(meta.amount, meta.currency)} para {monthNameOf(meta.target_month)}{" "}
        {meta.target_month.slice(0, 4)}
      </p>
      <p className="text-sm">
        Lleva {formatCents(meta.holds, meta.currency)} · pide{" "}
        {formatCents(meta.asks, meta.currency)} este mes
      </p>
      <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
        {meta.progress}% del camino
      </p>
      {meta.complete && !meta.closed && (
        <div className="flex flex-wrap gap-2 pt-1">
          <Button variant="ghost" size="sm">
            Cerrar {meta.name}
          </Button>
          <Button variant="ghost" size="sm">
            Seguir con otro monto
          </Button>
          <Button variant="ghost" size="sm">
            Seguir con otro mes
          </Button>
        </div>
      )}
    </li>
  )
}

export default function MetasPage() {
  const month = format(new Date(), "yyyy-MM")
  const [creating, setCreating] = useState(false)
  const metas = useQuery({ queryKey: qk.metas(month), queryFn: () => listMetas(month) })

  return (
    <div className="space-y-4">
      <PageHeader
        title="Metas"
        subtitle={month}
        help={
          <ScreenHelp screen="las metas">
            <HelpSection lead="Qué es una meta">
              <p>
                Una <strong>meta</strong> es {WHAT_A_META_IS}. Se llena sola mes a mes, y el día que
                comprás la cosa vinculás el gasto y se cumple.
              </p>
            </HelpSection>
            <HelpSection lead="En qué se diferencia de un fondo y de un presupuesto">
              <p>
                Un <strong>fondo</strong> {WHAT_A_FONDO_IS}.
              </p>
              <p>
                Un <strong>presupuesto</strong> {WHAT_A_PRESUPUESTO_IS}.
              </p>
            </HelpSection>
          </ScreenHelp>
        }
        action={
          <Button onClick={() => setCreating(true)} disabled={creating}>
            Nueva meta
          </Button>
        }
      />

      {creating && <CreateMetaForm month={month} onDone={() => setCreating(false)} />}

      <QueryBoundary
        query={metas}
        skeleton={<SkeletonRows rows={3} />}
        empty={{
          when: (rows) => rows.length === 0,
          node: (
            <EmptyState
              message="Todavía no tienes metas."
              description={`Una meta es ${WHAT_A_META_IS}. Se llena sola mes a mes.`}
              action={{ label: "Crear mi primera meta", onClick: () => setCreating(true) }}
            />
          ),
        }}
      >
        {(rows) => (
          <ul className="space-y-2">
            {rows.map((meta) => (
              <MetaCard key={meta.meta_id} meta={meta} />
            ))}
          </ul>
        )}
      </QueryBoundary>
    </div>
  )
}
