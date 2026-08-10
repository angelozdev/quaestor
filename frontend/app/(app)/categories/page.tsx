"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { CheckboxField } from "@/components/checkbox-field"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { DataTable } from "@/components/data-table"
import { EntityFormDialog, type Field, type FormValues } from "@/components/entity-form-dialog"
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
    <div className="space-y-10">
      <PageHeader
        title="Categorías"
        action={<Button onClick={() => setCreating(true)}>Nueva</Button>}
        help={<ScreenHelp screen="Categorías">{CATEGORIES_HELP}</ScreenHelp>}
      />

      <div className="space-y-3">
        <CheckboxField
          id="show-archived"
          label="Mostrar archivadas"
          checked={values.archived}
          onCheckedChange={(checked) => patch({ archived: checked })}
        />

        <DataTable
          rows={list.data}
          rowKey={(c) => c.id}
          isLoading={list.isLoading}
          isError={list.isError}
          onRetry={() => list.refetch()}
          columns={[
            {
              key: "name",
              header: "Nombre",
              render: (c) => (
                <span className="flex items-center gap-2">
                  {c.name} <StatusBadge kind="archived" value={c.archived} />
                </span>
              ),
            },
            {
              key: "group",
              header: "Grupo",
              render: (c) => (
                <span style={{ color: "var(--muted-foreground)" }}>{groupName(c.group_id)}</span>
              ),
            },
            {
              key: "marks",
              header: "Marcas",
              render: (c) => (
                <span className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                  {[
                    c.is_income && "ingreso",
                    c.exclude_from_totals && "no-totales",
                    c.counts_as_saving && "ahorro",
                  ]
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </span>
              ),
            },
          ]}
          actionsAs="inline"
          actions={[
            {
              label: "Restaurar",
              show: (c) => c.archived,
              disabled: restore.isPending,
              onClick: (c) => restore.mutate(c.id),
            },
            { label: "Editar", show: (c) => !c.archived, onClick: (c) => setEditing(c) },
            { label: "Archivar", show: (c) => !c.archived, onClick: (c) => setArchiving(c) },
          ]}
          emptyMessage="Todavía no tienes categorías."
          emptyDescription={WHAT_A_CATEGORY_IS}
          emptyAction={{ label: "Crear la primera", onClick: () => setCreating(true) }}
        />
      </div>

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
