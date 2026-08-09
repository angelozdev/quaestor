"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { EmptyState } from "@/components/empty-state"
import { EntityFormDialog, type Field, type FormValues } from "@/components/entity-form-dialog"
import { ErrorState } from "@/components/error-state"
import { PageHeader } from "@/components/page-header"
import { ScreenHelp } from "@/components/screen-help"
import { StatusBadge } from "@/components/status-badge"
import {
  archiveCategory,
  createCategory,
  listCategories,
  restoreCategory,
  updateCategory,
} from "@/lib/api/categories"
import { listCategoryGroups } from "@/lib/api/category-groups"
import type { Category } from "@/lib/api/types"
import { ApiError } from "@/lib/api/types"
import { ARCHIVED_FILTER_SCHEMA } from "@/lib/filter-schemas"
import { invalidate, qk } from "@/lib/query"
import { useUrlFilters } from "@/lib/use-url-filters"
import { Button } from "@/ui"

const FIELDS: Field[] = [
  { kind: "text", name: "name", label: "Nombre", required: true },
  {
    kind: "entity",
    name: "group_id",
    label: "Grupo",
    queryKey: qk.categoryGroups(false),
    queryFn: () => listCategoryGroups(false),
    allowNullLabel: "Sin grupo",
  },
  { kind: "checkbox", name: "is_income", label: "Es ingreso" },
  { kind: "checkbox", name: "exclude_from_totals", label: "Excluir de los totales" },
  { kind: "checkbox", name: "counts_as_saving", label: "Gastar aquí es ahorrar" },
]

const WHAT_A_CATEGORY_IS = (
  <p>
    Una categoría dice para qué fue un movimiento — mercado, arriendo, salario. Cada gasto y cada
    ingreso lleva una.
  </p>
)

const CATEGORIES_HELP = (
  <>
    {WHAT_A_CATEGORY_IS}
    <p>
      Es la unidad con la que trabaja el resto de la app: los reportes reparten el mes por
      categoría, y un fondo o un presupuesto vigila exactamente una.
    </p>
  </>
)

export default function CategoriesPage() {
  const qc = useQueryClient()
  const { values, patch } = useUrlFilters(ARCHIVED_FILTER_SCHEMA)
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Category | null>(null)
  const [archiving, setArchiving] = useState<Category | null>(null)

  const list = useQuery({
    queryKey: qk.categories(values.archived),
    queryFn: () => listCategories(values.archived),
  })
  const groups = useQuery({
    queryKey: qk.categoryGroups(true),
    queryFn: () => listCategoryGroups(true),
  })
  const groupName = (id: number | null) =>
    id === null ? "—" : (groups.data?.find((g) => g.id === id)?.name ?? "—")

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error")
  const done = (msg: string) => {
    toast.success(msg)
    invalidate(qc, "categoryWrite")
  }

  const toBody = (v: FormValues) => ({
    name: String(v.name),
    group_id: (v.group_id as number | null) ?? null,
    is_income: Boolean(v.is_income),
    exclude_from_totals: Boolean(v.exclude_from_totals),
    counts_as_saving: Boolean(v.counts_as_saving),
  })

  const create = useMutation({
    mutationFn: (v: FormValues) => createCategory(toBody(v)),
    onSuccess: () => {
      done("Categoría creada")
      setCreating(false)
    },
    onError: onErr,
  })
  const update = useMutation({
    mutationFn: (v: FormValues) => {
      if (!editing) throw new Error("editing category is required")
      return updateCategory(editing.id, toBody(v))
    },
    onSuccess: () => {
      done("Categoría actualizada")
      setEditing(null)
    },
    onError: onErr,
  })
  const archive = useMutation({
    mutationFn: (id: number) => archiveCategory(id),
    onSuccess: () => {
      done("Categoría archivada")
      setArchiving(null)
    },
    onError: onErr,
  })
  const restore = useMutation({
    mutationFn: (id: number) => restoreCategory(id),
    onSuccess: () => {
      done("Categoría restaurada")
    },
    onError: onErr,
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Categorías"
        action={<Button onClick={() => setCreating(true)}>Nueva</Button>}
        help={<ScreenHelp screen="Categorías">{CATEGORIES_HELP}</ScreenHelp>}
      />

      <label
        className="flex items-center gap-2 text-sm"
        style={{ color: "var(--muted-foreground)" }}
      >
        <input
          type="checkbox"
          checked={values.archived}
          onChange={(e) => patch({ archived: e.target.checked })}
        />
        Mostrar archivadas
      </label>

      {list.isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 5 }, (_, i) => `skel-${i}`).map((k) => (
            <div
              key={k}
              className="h-10 animate-pulse rounded"
              style={{ background: "var(--muted)" }}
            />
          ))}
        </div>
      )}
      {list.isError && (
        <ErrorState message="No se pudieron cargar las categorías" onRetry={() => list.refetch()} />
      )}
      {list.data && list.data.length === 0 && (
        <EmptyState
          message="Todavía no tienes categorías."
          description={WHAT_A_CATEGORY_IS}
          action={{ label: "Crear la primera", onClick: () => setCreating(true) }}
        />
      )}

      {list.data && list.data.length > 0 && (
        <div className="overflow-hidden rounded-lg border" style={{ borderColor: "var(--border)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ color: "var(--muted-foreground)" }}>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Nombre</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Grupo</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Flags</th>
                <th className="w-40 px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {list.data.map((c) => (
                <tr key={c.id} className="border-t" style={{ borderColor: "var(--border)" }}>
                  <td className="px-3 py-2.5">
                    <span className="flex items-center gap-2">
                      {c.name} <StatusBadge kind="archived" value={c.archived} />
                    </span>
                  </td>
                  <td className="px-3 py-2.5" style={{ color: "var(--muted-foreground)" }}>
                    {groupName(c.group_id)}
                  </td>
                  <td className="px-3 py-2.5 text-xs" style={{ color: "var(--muted-foreground)" }}>
                    {[
                      c.is_income && "ingreso",
                      c.exclude_from_totals && "no-totales",
                      c.counts_as_saving && "ahorro",
                    ]
                      .filter(Boolean)
                      .join(" · ") || "—"}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    {c.archived ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={restore.isPending}
                        onClick={() => restore.mutate(c.id)}
                      >
                        Restaurar
                      </Button>
                    ) : (
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => setEditing(c)}>
                          Editar
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setArchiving(c)}>
                          Archivar
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <EntityFormDialog
        open={creating}
        onOpenChange={setCreating}
        title="Nueva categoría"
        fields={FIELDS}
        initialValues={{
          name: "",
          group_id: null,
          is_income: false,
          exclude_from_totals: false,
          counts_as_saving: false,
        }}
        pending={create.isPending}
        onSubmit={(v) => create.mutate(v)}
      />
      <EntityFormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title="Editar categoría"
        fields={FIELDS}
        initialValues={{
          name: editing?.name ?? "",
          group_id: editing?.group_id ?? null,
          is_income: editing?.is_income ?? false,
          exclude_from_totals: editing?.exclude_from_totals ?? false,
          counts_as_saving: editing?.counts_as_saving ?? false,
        }}
        pending={update.isPending}
        onSubmit={(v) => update.mutate(v)}
      />
      <ConfirmDialog
        open={archiving !== null}
        onOpenChange={(o) => !o && setArchiving(null)}
        title="Archivar categoría"
        description={`Se archivará "${archiving?.name}". Puedes restaurarla luego con "Mostrar archivadas".`}
        confirmLabel="Archivar"
        pending={archive.isPending}
        onConfirm={() => archiving && archive.mutate(archiving.id)}
      />
    </div>
  )
}
