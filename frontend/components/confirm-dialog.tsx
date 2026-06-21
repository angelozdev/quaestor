"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  Button,
  Input,
} from "@/ui";

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirmar",
  onConfirm,
  destructive = false,
  pending = false,
  requireTextMatch,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: React.ReactNode;
  confirmLabel?: string;
  onConfirm: () => void;
  destructive?: boolean;
  pending?: boolean;
  requireTextMatch?: string;
}) {
  const [typed, setTyped] = useState("");

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!open) setTyped("");
  }, [open]);

  const blocked = requireTextMatch !== undefined && typed.trim() !== requireTextMatch;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup className="max-w-sm">
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>{description}</DialogDescription>

        {requireTextMatch !== undefined && (
          <Input
            autoFocus
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder={requireTextMatch}
            aria-label="Confirmación por texto"
          />
        )}

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>
            Cancelar
          </Button>
          <Button
            variant={destructive ? "destructive" : "default"}
            onClick={onConfirm}
            disabled={pending || blocked}
          >
            {pending ? "…" : confirmLabel}
          </Button>
        </div>
      </DialogPopup>
    </Dialog>
  );
}
