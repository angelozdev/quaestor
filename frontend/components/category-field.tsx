"use client"

import { useState } from "react"
import { EntitySelect } from "@/components/entity-select"
import { listCategories } from "@/lib/api/categories"
import { qk } from "@/lib/query"
import { Button, Input, Label } from "@/ui"

export type CategoryChoice = {
  categoryId: number | null
  newCategory: string
}

export const NO_CATEGORY: CategoryChoice = { categoryId: null, newCategory: "" }

export function CategoryField({
  value,
  onChange,
  isIncome,
  error,
  id = "category",
  allowCreate = true,
}: {
  value: CategoryChoice
  onChange: (choice: CategoryChoice) => void
  isIncome: boolean
  error?: string
  id?: string
  /** Whether this form can create a category in the same request. Only the
   * paths that carry `new_category` may offer it — see the recurring edit
   * dialog, whose update endpoint does not. */
  allowCreate?: boolean
}) {
  const [creating, setCreating] = useState(false)
  const direction = isIncome ? "ingreso" : "gasto"

  function toggleCreating() {
    setCreating(!creating)
    onChange(NO_CATEGORY)
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <Label htmlFor={id}>Categoría *</Label>
        {allowCreate ? (
          <Button type="button" variant="ghost" size="sm" onClick={toggleCreating}>
            {creating ? "Elegir una existente" : "Crear categoría"}
          </Button>
        ) : null}
      </div>
      {allowCreate && creating ? (
        <Input
          id={id}
          autoFocus
          placeholder={`Nombre de la categoría de ${direction}`}
          value={value.newCategory}
          onChange={(e) => onChange({ categoryId: null, newCategory: e.target.value })}
        />
      ) : (
        <EntitySelect
          id={id}
          value={value.categoryId}
          onChange={(categoryId) => onChange({ categoryId, newCategory: "" })}
          queryKey={qk.categories(false, isIncome)}
          queryFn={() => listCategories(false, isIncome)}
          placeholder={`Categoría de ${direction}…`}
        />
      )}
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  )
}
