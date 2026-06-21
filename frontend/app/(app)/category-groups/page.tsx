"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, type CategoryGroup } from "@/lib/api";
import { qk, invalidate } from "@/lib/query";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { EntityFormDialog, type Field, type FormValues } from "@/components/entity-form-dialog";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Button } from "@/ui";

const FIELDS: Field[] = [
  { kind: "text", name: "name", label: "Nombre", required: true },
  { kind: "number", name: "sort_order", label: "Orden", min: 0 },
];

export default function CategoryGroupsPage() {
  const qc = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [editing, setEditing] = useState<CategoryGroup | null>(null);
  const [creating, setCreating] = useState(false);
  const [archiving, setArchiving] = useState<CategoryGroup | null>(null);

  const list = useQuery({
    queryKey: qk.categoryGroups(showArchived),
    queryFn: () => api.listCategoryGroups(showArchived),
  });

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error");
  const onOk = (msg: string) => {
    toast.success(msg);
    invalidate(qc, "categoryGroupWrite");
  };

  const create = useMutation({
    mutationFn: (v: FormValues) =>
      api.createCategoryGroup({ name: String(v.name), sort_order: (v.sort_order as number) ?? 0 }),
    onSuccess: () => { onOk("Grupo creado"); setCreating(false); },
    onError: onErr,
  });
  const update = useMutation({
    mutationFn: (v: FormValues) =>
      api.updateCategoryGroup(editing!.id, { name: String(v.name), sort_order: (v.sort_order as number) ?? 0 }),
    onSuccess: () => { onOk("Grupo actualizado"); setEditing(null); },
    onError: onErr,
  });
  const archive = useMutation({
    mutationFn: (id: number) => api.archiveCategoryGroup(id),
    onSuccess: () => { onOk("Grupo archivado"); setArchiving(null); },
    onError: onErr,
  });
  const restore = useMutation({
    mutationFn: (id: number) => api.restoreCategoryGroup(id),
    onSuccess: () => { onOk("Grupo restaurado"); },
    onError: onErr,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Grupos de categorías"
        action={<Button onClick={() => setCreating(true)}>Nuevo</Button>}
      />

      <label className="flex items-center gap-2 text-sm" style={{ color: "var(--muted-foreground)" }}>
        <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
        Mostrar archivados
      </label>

      {list.isLoading && (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-10 animate-pulse rounded" style={{ background: "var(--muted)" }} />
          ))}
        </div>
      )}
      {list.isError && <ErrorState message="No se pudieron cargar los grupos" onRetry={() => list.refetch()} />}
      {list.data && list.data.length === 0 && <EmptyState message="Sin grupos" />}

      {list.data && list.data.length > 0 && (
        <div className="overflow-hidden rounded-lg border" style={{ borderColor: "var(--border)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ color: "var(--muted-foreground)" }}>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Nombre</th>
                <th className="px-3 py-2.5 text-right text-xs font-medium">Orden</th>
                <th className="w-40 px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {list.data.map((g) => (
                <tr key={g.id} className="border-t" style={{ borderColor: "var(--border)" }}>
                  <td className="px-3 py-2.5">
                    <span className="flex items-center gap-2">
                      {g.name} <StatusBadge kind="archived" value={g.archived} />
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{g.sort_order}</td>
                  <td className="px-3 py-2.5 text-right">
                    {g.archived ? (
                      <Button variant="ghost" size="sm" disabled={restore.isPending} onClick={() => restore.mutate(g.id)}>Restaurar</Button>
                    ) : (
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => setEditing(g)}>Editar</Button>
                        <Button variant="ghost" size="sm" onClick={() => setArchiving(g)}>Archivar</Button>
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
  );
}
