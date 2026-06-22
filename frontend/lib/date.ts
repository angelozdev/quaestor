import { format, parseISO, startOfDay } from "date-fns"

/**
 * Display a calendar date in the app-wide human format: "Sun, 10 May 2026".
 * Input is the wire ISO string the backend returns ("yyyy-MM-dd").
 * Use only for display — never parse the result back.
 */
export function formatDate(value: string): string {
  return format(parseISO(value), "EEE, d MMM yyyy")
}

/**
 * True when the given ISO date is strictly before today (local time).
 * Used to flag planned payments that are past due.
 */
export function isOverdue(value: string, now: Date = new Date()): boolean {
  return startOfDay(parseISO(value)).getTime() < startOfDay(now).getTime()
}