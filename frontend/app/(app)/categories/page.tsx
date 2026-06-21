"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, type Category } from "@/lib/api";
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
  {
    kind: "entity",
    name: "group_id",
    label: "Grupo",
    queryKey: qk.categoryGroups(false),
    queryFn: () => api.listCategoryGroups(false),
    allowNullLabel: "Sin grupo",
  },
  { kind: "checkbox", name: "is_income", label: "Es ingreso" },
  { kind: "checkbox", name: "exclude_from_budget", label: "Excluir del presupuesto" },
  { kind: "checkbox", name: "exclude_from_totals", label: "Excluir de los totales" },
];

export default function CategoriesPage() {
  const qc = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [archiving, setArchiving] = useState<Category | null>(null);

  const list = useQuery({
    queryKey: qk.categories(showArchived),
    queryFn: () => api.listCategories(showArchived),
  });
  const groups = useQuery({
    queryKey: qk.categoryGroups(true),
    queryFn: () => api.listCategoryGroups(true),
  });
  const groupName = (id: number | null) =>
    id === null ? "—" : groups.data?.find((g) => g.id === id)?.name ?? "—";

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error");
  const done = (msg: string) => { toast.success(msg); invalidate(qc, "categoryWrite"); };

  const toBody = (v: FormValues) => ({
    name: String(v.name),
    group_id: (v.group_id as number | null) ?? null,
    is_income: Boolean(v.is_income),
    exclude_from_budget: Boolean(v.exclude_from_budget),
    exclude_from_totals: Boolean(v.exclude_from_totals),
  });

  const create = useMutation({
    mutationFn: (v: FormValues) => api.createCategory(toBody(v)),
    onSuccess: () => { done("Categoría creada"); setCreating(false); },
    onError: onErr,
  });
  const update = useMutation({
    mutationFn: (v: FormValues) => api.updateCategory(editing!.id, toBody(v)),
    onSuccess: () => { done("Categoría actualizada"); setEditing(null); },
    onError: onErr,
  });
  const archive = useMutation({
    mutationFn: (id: number) => api.archiveCategory(id),
    onSuccess: () => { done("Categoría archivada"); setArchiving(null); },
    onError: onErr,
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Categorías" action={<Button onClick={() => setCreating(true)}>Nueva</Button>} />

      <label className="flex items-center gap-2 text-sm" style={{ color: "var(--muted-foreground)" }}>
        <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
        Mostrar archivadas
      </label>

      {list.isLoading && (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-10 animate-pulse rounded" style={{ background: "var(--muted)" }} />
          ))}
        </div>
      )}
      {list.isError && <ErrorState message="No se pudieron cargar las categorías" onRetry={() => list.refetch()} />}
      {list.data && list.data.length === 0 && <EmptyState message="Sin categorías" />}

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
                  <td className="px-3 py-2.5" style={{ color: "var(--muted-foreground)" }}>{groupName(c.group_id)}</td>
                  <td className="px-3 py-2.5 text-xs" style={{ color: "var(--muted-foreground)" }}>
                    {[
                      c.is_income && "ingreso",
                      c.exclude_from_budget && "no-presup.",
                      c.exclude_from_totals && "no-totales",
                    ].filter(Boolean).join(" · ") || "—"}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    {!c.archived && (
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => setEditing(c)}>Editar</Button>
                        <Button variant="ghost" size="sm" onClick={() => setArchiving(c)}>Archivar</Button>
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
        initialValues={{ name: "", group_id: null, is_income: false, exclude_from_budget: false, exclude_from_totals: false }}
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
          exclude_from_budget: editing?.exclude_from_budget ?? false,
          exclude_from_totals: editing?.exclude_from_totals ?? false,
        }}
        pending={update.isPending}
        onSubmit={(v) => update.mutate(v)}
      />
      <ConfirmDialog
        open={archiving !== null}
        onOpenChange={(o) => !o && setArchiving(null)}
        title="Archivar categoría"
        description={`Se archivará "${archiving?.name}". No podrás reactivarla desde la app (Fase 2).`}
        confirmLabel="Archivar"
        pending={archive.isPending}
        onConfirm={() => archiving && archive.mutate(archiving.id)}
      />
    </div>
  );
}
