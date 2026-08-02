"use client"

import { MoreHorizontal } from "lucide-react"
import { useMemo, useState } from "react"
import { EmptyState } from "@/components/empty-state"
import { ErrorState } from "@/components/error-state"
import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/ui"

export interface Column<T> {
  key: string
  header: string
  align?: "left" | "right"
  render: (row: T) => React.ReactNode
}

export interface RowAction<T> {
  label: string
  onClick: (row: T) => void
  variant?: "default" | "destructive"
  show?: (row: T) => boolean
}

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  actions,
  pageSize = 25,
  filterBar,
  isLoading,
  isError,
  onRetry,
  emptyMessage = "Sin resultados",
}: {
  rows: T[] | undefined
  columns: Column<T>[]
  rowKey: (row: T) => string | number
  actions?: RowAction<T>[]
  pageSize?: number
  filterBar?: React.ReactNode
  isLoading?: boolean
  isError?: boolean
  onRetry?: () => void
  emptyMessage?: string
}) {
  const [page, setPage] = useState(0)
  const all = useMemo(() => rows ?? [], [rows])
  const pageCount = Math.max(1, Math.ceil(all.length / pageSize))
  const clampedPage = Math.min(page, pageCount - 1)
  const slice = useMemo(
    () => all.slice(clampedPage * pageSize, clampedPage * pageSize + pageSize),
    [all, clampedPage, pageSize],
  )

  return (
    <div className="space-y-3">
      {filterBar}

      {isError ? (
        <ErrorState message="No se pudieron cargar los datos" onRetry={onRetry ?? (() => {})} />
      ) : isLoading ? (
        <div className="space-y-2">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-10 animate-pulse rounded"
              style={{ background: "var(--muted)" }}
            />
          ))}
        </div>
      ) : all.length === 0 ? (
        <EmptyState message={emptyMessage} />
      ) : (
        <>
          <div
            className="overflow-x-auto rounded-lg border"
            style={{ borderColor: "var(--border)" }}
          >
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--muted-foreground)" }}>
                  {columns.map((c) => (
                    <th
                      key={c.key}
                      className={`px-3 py-2.5 text-xs font-medium ${c.align === "right" ? "text-right" : "text-left"}`}
                    >
                      {c.header}
                    </th>
                  ))}
                  {actions && actions.length > 0 && <th className="w-10 px-3 py-2.5" />}
                </tr>
              </thead>
              <tbody>
                {slice.map((row) => (
                  <tr
                    key={rowKey(row)}
                    className="border-t"
                    style={{ borderColor: "var(--border)" }}
                  >
                    {columns.map((c) => (
                      <td
                        key={c.key}
                        className={`px-3 py-2.5 ${c.align === "right" ? "text-right tabular-nums" : "text-left"}`}
                      >
                        {c.render(row)}
                      </td>
                    ))}
                    {actions && actions.length > 0 && (
                      <td className="px-3 py-2.5 text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger
                            render={<Button variant="ghost" size="icon-sm" aria-label="Acciones" />}
                          >
                            <MoreHorizontal className="size-4" />
                          </DropdownMenuTrigger>
                          <DropdownMenuContent>
                            {actions
                              .filter((a) => a.show === undefined || a.show(row))
                              .map((a) => (
                                <DropdownMenuItem
                                  key={a.label}
                                  variant={a.variant}
                                  onClick={() => a.onClick(row)}
                                >
                                  {a.label}
                                </DropdownMenuItem>
                              ))}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {pageCount > 1 && (
            <div
              className="flex items-center justify-between text-xs"
              style={{ color: "var(--muted-foreground)" }}
            >
              <span>
                {all.length} resultados · página {clampedPage + 1} de {pageCount}
              </span>
              <div className="flex gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={clampedPage === 0}
                  onClick={() => setPage(clampedPage - 1)}
                >
                  Anterior
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={clampedPage >= pageCount - 1}
                  onClick={() => setPage(clampedPage + 1)}
                >
                  Siguiente
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
