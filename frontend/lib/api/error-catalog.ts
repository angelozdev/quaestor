import type { ApiError } from "./types"

export const ERROR_CATALOG: Record<string, (data: Record<string, unknown>) => string> = {
  category_duplicate_active: (d) =>
    `Ya existe una categoría de ${d.direction === "income" ? "ingreso" : "gasto"} llamada «${d.name}»`,
  category_duplicate_archived: (d) =>
    `Ya existe una categoría de ${d.direction === "income" ? "ingreso" : "gasto"} archivada llamada «${d.name}». Restaurarla en vez de crear otra.`,
  amount_not_positive: () => "El monto debe ser mayor que cero",
}

export function translateApiError(err: ApiError): string {
  return ERROR_CATALOG[err.code]?.(err.data) ?? err.message
}
