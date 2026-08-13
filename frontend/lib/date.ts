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
/**
 * True when a repeating obligation is past its end date.
 *
 * The end date is itself a due date, so an obligation ending today has not
 * ended yet; one with no end date never ends. Mirrors what the backend
 * derives rather than reading a stored flag (ADR-0037) — `active` still
 * means only that the user switched it off.
 */
export function hasEnded(endDate: string | null, now: Date = new Date()): boolean {
  return endDate !== null && isOverdue(endDate, now)
}

/** The wire month a wire date falls in ("2026-12-24" → "2026-12"), or null when it is not a date yet. */
export function yearMonthOf(date: string): string | null {
  return /^\d{4}-\d{2}-\d{2}$/.test(date) ? date.slice(0, 7) : null
}

/** The month after a wire month ("2026-12" → "2027-01"). */
export function nextYearMonth(yearMonth: string): string {
  const [year, month] = yearMonth.split("-").map(Number)
  const rolls = month === 12
  return `${rolls ? year + 1 : year}-${String(rolls ? 1 : month + 1).padStart(2, "0")}`
}

const MONTH_IN_SPANISH = new Intl.DateTimeFormat("es-CO", { month: "long", timeZone: "UTC" })

function spanishMonth(yearMonth: string): { name: string; year: number } {
  const [year, month] = yearMonth.split("-").map(Number)
  return { name: MONTH_IN_SPANISH.format(new Date(Date.UTC(year, month - 1, 1))), year }
}

/** A wire month as the sentence names it: "2026-09" → "Septiembre". */
export function monthNameOf(yearMonth: string): string {
  const { name } = spanishMonth(yearMonth)
  return name.charAt(0).toUpperCase() + name.slice(1)
}

/**
 * A wire month with its year, mid-sentence: "2027-08" → "agosto de 2027".
 *
 * A charge a year out needs the year said, which `monthNameOf` leaves off
 * because the months it names are always the one in view or the one after it.
 */
export function monthAndYearOf(yearMonth: string): string {
  const { name, year } = spanishMonth(yearMonth)
  return `${name} de ${year}`
}
