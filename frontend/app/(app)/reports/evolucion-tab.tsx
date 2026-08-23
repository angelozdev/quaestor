"use client"

import type { ReactNode } from "react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  type RenderableText,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts"
import { EmptyState } from "@/components/empty-state"
import type { MonthlyReport } from "@/lib/api/types"
import { formatCents } from "@/lib/money"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/ui"

const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
  "var(--chart-7)",
  "var(--chart-8)",
  "var(--chart-9)",
  "var(--chart-10)",
]

function colorFor(index: number): string {
  return CHART_COLORS[index % CHART_COLORS.length]
}

/** Recharts' `Text` splits a label onto a new line at every plain space; a
 * non-breaking space keeps "$ 500.000" on one line above the bar. */
function barTotalLabel(cents: RenderableText): string {
  return formatCents(Number(cents ?? 0), "COP").replace(" ", "\u00a0")
}

export function EvolucionTab({
  report,
  emptyDescription,
}: {
  report: MonthlyReport
  emptyDescription: ReactNode
}) {
  const { trend } = report

  if (trend.categories.length === 0) {
    return (
      <EmptyState
        message="Sin gastos este mes"
        description={emptyDescription}
        action={{ label: "Registrar un movimiento", href: "/transactions" }}
      />
    )
  }

  const groups = Array.from(new Set(trend.months.flatMap((month) => Object.keys(month.by_group))))
  const chartData = trend.months.map((month) => ({
    month: month.month,
    total: month.total,
    ...month.by_group,
  }))

  return (
    <div className="space-y-10">
      <ResponsiveContainer width="100%" height={320} initialDimension={{ width: 960, height: 320 }}>
        <BarChart data={chartData} margin={{ top: 24 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis dataKey="month" tickLine={false} axisLine={false} />
          <YAxis hide />
          {groups.map((group, index) => (
            <Bar
              key={group}
              dataKey={group}
              stackId="evolucion"
              fill={colorFor(index)}
              isAnimationActive={false}
            >
              {index === groups.length - 1 ? (
                <LabelList dataKey="total" position="top" formatter={barTotalLabel} />
              ) : null}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Categoría</TableHead>
            {trend.months.map((month) => (
              <TableHead key={month.month} className="text-right">
                {month.month}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {trend.categories.map((row) => (
            <TableRow key={row.category}>
              <TableCell>{row.category}</TableCell>
              {trend.months.map((month) => (
                <TableCell key={month.month} className="text-right tabular-nums">
                  {formatCents(row.by_month[month.month] ?? 0, "COP")}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
