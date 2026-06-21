"use client";

import { useEffect, useState } from "react";
import { Input } from "@/ui";

/**
 * Parse user text into integer cents for a currency. Presentation-only — never
 * applied to amounts already resolved by the API.
 * COP: digits only, value is whole pesos -> ×100. USD: one decimal point allowed,
 * major units -> ×100 rounded. Returns null for empty/invalid input.
 */
export function parseMoneyToCents(text: string, currency: string): number | null {
  const trimmed = text.trim();
  if (trimmed === "") return null;
  if (currency === "USD") {
    const cleaned = trimmed.replace(/[^0-9.]/g, "");
    if (cleaned === "" || cleaned === ".") return null;
    const major = Number.parseFloat(cleaned);
    if (!Number.isFinite(major)) return null;
    return Math.round(major * 100);
  }
  const digits = trimmed.replace(/[^0-9]/g, "");
  if (digits === "") return null;
  const pesos = Number.parseInt(digits, 10);
  if (!Number.isFinite(pesos)) return null;
  return pesos * 100;
}

function centsToText(cents: number | null, currency: string): string {
  if (cents === null) return "";
  if (currency === "USD") return (cents / 100).toString();
  return Math.round(cents / 100).toString();
}

export function MoneyInput({
  currency,
  value,
  onChange,
  id,
  placeholder,
  disabled,
}: {
  currency: string;
  value: number | null;
  onChange: (cents: number | null) => void;
  id?: string;
  placeholder?: string;
  disabled?: boolean;
}) {
  const [text, setText] = useState(() => centsToText(value, currency));

  // Re-sync when the external currency changes (e.g. currency switch).
  // Only depends on currency to avoid cursor jump on value change from parent.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setText(centsToText(value, currency));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currency]);

  const prefix = currency === "USD" ? "US$" : "$";

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-muted-foreground tabular-nums">{prefix}</span>
      <Input
        id={id}
        inputMode={currency === "USD" ? "decimal" : "numeric"}
        value={text}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(e) => {
          const next = e.target.value;
          setText(next);
          onChange(parseMoneyToCents(next, currency));
        }}
        className="tabular-nums"
      />
    </div>
  );
}
