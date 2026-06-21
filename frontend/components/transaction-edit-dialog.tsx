"use client";

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, type Transaction } from "@/lib/api";
import { qk, invalidate } from "@/lib/query";
import { formatCents } from "@/lib/money";
import { EntitySelect } from "@/components/entity-select";
import { Dialog, DialogPopup, DialogTitle, Input, Label, Textarea, Button } from "@/ui";

export function TransactionEditDialog({
  tx,
  open,
  onOpenChange,
}: {
  tx: Transaction | null;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const qc = useQueryClient();
  const [payee, setPayee] = useState("");
  const [date, setDate] = useState("");
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (tx) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPayee(tx.payee ?? "");
      setDate(tx.date);
      setCategoryId(tx.category_id);
      setNotes(tx.notes ?? "");
    }
  }, [tx]);

  const update = useMutation({
    mutationFn: () =>
      api.updateTransaction(tx!.id, {
        payee,
        date,
        category_id: categoryId,
        notes: notes || null,
      }),
    onSuccess: () => {
      toast.success("Transacción actualizada");
      invalidate(qc, "transactionWrite");
      onOpenChange(false);
    },
    onError: (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error"),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup>
        <DialogTitle>Editar transacción</DialogTitle>
        {tx && (
          <form onSubmit={(e) => { e.preventDefault(); update.mutate(); }} className="space-y-4">
            <div className="rounded-lg border p-3 text-sm" style={{ borderColor: "var(--border)", color: "var(--muted-foreground)" }}>
              <p>{tx.type} · {formatCents(tx.amount, tx.currency)} · cuenta #{tx.account_id}</p>
              <p className="mt-1 text-xs">Para cambiar monto/cuenta, elimina y vuelve a crear.</p>
            </div>
            <div className="space-y-1.5">
              <Label>Beneficiario</Label>
              <Input value={payee} onChange={(e) => setPayee(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Fecha</Label>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Categoría</Label>
              <EntitySelect
                value={categoryId}
                onChange={setCategoryId}
                queryKey={qk.categories(false)}
                queryFn={() => api.listCategories(false)}
                allowNullLabel="Sin categoría"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Notas</Label>
              <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
              <Button type="submit" disabled={update.isPending}>{update.isPending ? "…" : "Guardar"}</Button>
            </div>
          </form>
        )}
      </DialogPopup>
    </Dialog>
  );
}
