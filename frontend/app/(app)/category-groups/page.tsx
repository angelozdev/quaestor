"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { DataTable } from "@/components/data-table"
import { EntityFormDialog, type Field, type FormValues } from "@/components/entity-form-dialog"
import { PageHeader } from "@/components/page-header"
import { ScreenHelp } from "@/components/screen-help"
import { StatusBadge } from "@/components/status-badge"
import {
  archiveCategoryGroup,
  createCategoryGroup,
  listCategoryGroups,
  restoreCategoryGroup,
  updateCategoryGroup,
} from "@/lib/api/category-groups"
import { ApiError, type CategoryGroup } from "@/lib/api/types"
import { ARCHIVED_FILTER_SCHEMA } from "@/lib/filter-schemas"
import { invalidate, qk } from "@/lib/query"
import { useUrlFilters } from "@/lib/use-url-filters"
import { Button, Checkbox } from "@/ui"

const FIELDS: Field[] = [
  { kind: "text", name: "name", label: "Nombre", required: true },
  { kind: "number", name: "sort_order", label: "Orden", min: 0 },
]

const WHAT_A_GROUP_IS = (
  <p>
    Un grupo junta categorías que van juntas — «Casa» puede reunir arriendo, servicios y mercado.
  </p>
)

const GROUPS_HELP = (
  <>
    {WHAT_A_GROUP_IS}
    <p>
      Sirve para leer el mes de más lejos: los reportes suman por grupo además de por categoría, así
      que ves cuánto se fue en «Casa» sin sumar tres líneas a mano.
    </p>
  </>
)

export default function CategoryGroupsPage() {
  const qc = useQueryClient()
  const { values, patch } = useUrlFilters(ARCHIVED_FILTER_SCHEMA)
  const [editing, setEditing] = useState<CategoryGroup | null>(null)
  const [creating, setCreating] = useState(false)
  const [archiving, setArchiving] = useState<CategoryGroup | null>(null)

  const list = useQuery({
    queryKey: qk.categoryGroups(values.archived),
    queryFn: () => listCategoryGroups(values.archived),
  })

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error")
  const onOk = (msg: string) => {
    toast.success(msg)
    invalidate(qc, "categoryGroupWrite")
  }

  const create = useMutation({
    mutationFn: (v: FormValues) =>
      createCategoryGroup({ name: String(v.name), sort_order: (v.sort_order as number) ?? 0 }),
    onSuccess: () => {
      onOk("Grupo creado")
      setCreating(false)
    },
    onError: onErr,
  })
  const update = useMutation({
    mutationFn: (v: FormValues) => {
      if (!editing) throw new Error("editing category group is required")
      return updateCategoryGroup(editing.id, {
        name: String(v.name),
        sort_order: (v.sort_order as number) ?? 0,
      })
    },
    onSuccess: () => {
      onOk("Grupo actualizado")
      setEditing(null)
    },
    onError: onErr,
  })
  const archive = useMutation({
    mutationFn: (id: number) => archiveCategoryGroup(id),
    onSuccess: () => {
      onOk("Grupo archivado")
      setArchiving(null)
    },
    onError: onErr,
  })
  const restore = useMutation({
    mutationFn: (id: number) => restoreCategoryGroup(id),
    onSuccess: () => {
      onOk("Grupo restaurado")
    },
    onError: onErr,
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Grupos de categorías"
        action={<Button onClick={() => setCreating(true)}>Nuevo</Button>}
        help={<ScreenHelp screen="Grupos">{GROUPS_HELP}</ScreenHelp>}
      />

      <label
        className="flex items-center gap-2 text-sm"
        style={{ color: "var(--muted-foreground)" }}
      >
        <Checkbox
          checked={values.archived}
          onCheckedChange={(checked) => patch({ archived: checked })}
        />
        Mostrar archivados
      </label>

      <DataTable
        rows={list.data}
        rowKey={(g) => g.id}
        isLoading={list.isLoading}
        isError={list.isError}
        onRetry={() => list.refetch()}
        columns={[
          {
            key: "name",
            header: "Nombre",
            render: (g) => (
              <span className="flex items-center gap-2">
                {g.name} <StatusBadge kind="archived" value={g.archived} />
              </span>
            ),
          },
          { key: "order", header: "Orden", align: "right", render: (g) => g.sort_order },
        ]}
        actionsAs="inline"
        actions={[
          {
            label: "Restaurar",
            show: (g) => g.archived,
            disabled: restore.isPending,
            onClick: (g) => restore.mutate(g.id),
          },
          { label: "Editar", show: (g) => !g.archived, onClick: (g) => setEditing(g) },
          { label: "Archivar", show: (g) => !g.archived, onClick: (g) => setArchiving(g) },
        ]}
        emptyMessage="Todavía no tienes grupos."
        emptyDescription={WHAT_A_GROUP_IS}
        emptyAction={{ label: "Crear el primero", onClick: () => setCreating(true) }}
      />

      <EntityFormDialog
        open={creating}
        onOpenChange={setCreating}
        title="Nuevo grupo"
        fields={FIELDS}
        initialValues={{ name: "", sort_order: 0 }}
        pending={create.isPending}
        onSubmit={(v) => create.mutate(v)}
      />
      <EntityFormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title="Editar grupo"
        fields={FIELDS}
        initialValues={{ name: editing?.name ?? "", sort_order: editing?.sort_order ?? 0 }}
        pending={update.isPending}
        onSubmit={(v) => update.mutate(v)}
      />
      <ConfirmDialog
        open={archiving !== null}
        onOpenChange={(o) => !o && setArchiving(null)}
        title="Archivar grupo"
        description={`Se archivará "${archiving?.name}". Puedes restaurarlo luego con "Mostrar archivados".`}
        confirmLabel="Archivar"
        pending={archive.isPending}
        onConfirm={() => archiving && archive.mutate(archiving.id)}
      />
    </div>
  )
}
