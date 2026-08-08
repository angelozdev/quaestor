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
import { createTag, deleteTag, listTags, updateTag } from "@/lib/api/tags"
import { ApiError, type Tag } from "@/lib/api/types"
import { invalidate, qk } from "@/lib/query"
import { Button } from "@/ui"

const FIELDS: Field[] = [{ kind: "text", name: "name", label: "Nombre", required: true }]

const WHAT_A_TAG_IS = (
  <p>
    Una etiqueta marca movimientos que van juntos aunque estén en categorías distintas — un viaje,
    una reforma, un regalo.
  </p>
)

const TAGS_HELP = (
  <>
    {WHAT_A_TAG_IS}
    <p>
      Un movimiento tiene una sola categoría, pero puede llevar varias etiquetas. En{" "}
      <strong>Transacciones</strong> puedes filtrar por una y ver todo lo que costó eso.
    </p>
  </>
)

export default function TagsPage() {
  const qc = useQueryClient()
  const [editing, setEditing] = useState<Tag | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<Tag | null>(null)

  const list = useQuery({ queryKey: qk.tags(), queryFn: () => listTags() })

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error")
  const done = (msg: string) => {
    toast.success(msg)
    invalidate(qc, "tagWrite")
  }

  const create = useMutation({
    mutationFn: (v: FormValues) => createTag({ name: String(v.name) }),
    onSuccess: () => {
      done("Etiqueta creada")
      setCreating(false)
    },
    onError: onErr,
  })
  const update = useMutation({
    mutationFn: (v: FormValues) => {
      if (!editing) throw new Error("editing tag is required")
      return updateTag(editing.id, { name: String(v.name) })
    },
    onSuccess: () => {
      done("Etiqueta actualizada")
      setEditing(null)
    },
    onError: onErr,
  })
  const remove = useMutation({
    mutationFn: (id: number) => deleteTag(id),
    onSuccess: () => {
      done("Etiqueta eliminada")
      setDeleting(null)
    },
    onError: onErr,
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Etiquetas"
        action={<Button onClick={() => setCreating(true)}>Nueva</Button>}
        help={<ScreenHelp screen="Etiquetas">{TAGS_HELP}</ScreenHelp>}
      />

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
        <ErrorState message="No se pudieron cargar las etiquetas" onRetry={() => list.refetch()} />
      )}
      {list.data && list.data.length === 0 && (
        <EmptyState
          message="Todavía no tienes etiquetas."
          description={WHAT_A_TAG_IS}
          action={{ label: "Crear la primera", onClick: () => setCreating(true) }}
        />
      )}

      {list.data && list.data.length > 0 && (
        <div className="overflow-hidden rounded-lg border" style={{ borderColor: "var(--border)" }}>
          <table className="w-full text-sm">
            <tbody>
              {list.data.map((t) => (
                <tr
                  key={t.id}
                  className="border-t first:border-t-0"
                  style={{ borderColor: "var(--border)" }}
                >
                  <td className="px-3 py-2.5">{t.name}</td>
                  <td className="px-3 py-2.5 text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="sm" onClick={() => setEditing(t)}>
                        Editar
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setDeleting(t)}>
                        Eliminar
                      </Button>
                    </div>
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
        title="Nueva etiqueta"
        fields={FIELDS}
        initialValues={{ name: "" }}
        pending={create.isPending}
        onSubmit={(v) => create.mutate(v)}
      />
      <EntityFormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title="Editar etiqueta"
        fields={FIELDS}
        initialValues={{ name: editing?.name ?? "" }}
        pending={update.isPending}
        onSubmit={(v) => update.mutate(v)}
      />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="Eliminar etiqueta"
        description={
          <>
            Esto elimina la etiqueta <strong>{deleting?.name}</strong> y la quita de todas sus
            transacciones. Es permanente. Escribe el nombre para confirmar.
          </>
        }
        confirmLabel="Eliminar"
        destructive
        requireTextMatch={deleting?.name}
        pending={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting.id)}
      />
    </div>
  )
}
