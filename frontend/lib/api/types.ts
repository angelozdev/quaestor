/** Types mirror the /api JSON contract (cents are integers). */
export type TxType = "income" | "expense" | "transfer"
export type TransferDirection = "out" | "in"
export type TxStatus = "planned" | "posted" | "skipped"
export type AccountType = "debit" | "credit" | "cash" | "savings"
export type IntervalUnit = "day" | "week" | "month" | "year"
export type RecurringMode = "auto" | "manual"
export type RecurringType = "expense" | "income"
export type OccurrenceStatus = "posted" | "planned" | "skipped" | "offered"

export interface Transaction {
  id: number
  date: string
  payee: string
  notes: string | null
  type: TxType
  status: TxStatus
  amount: number
  currency: string
  cop_equivalent: number | null
  account_id: number
  category_id: number | null
  meta_id: number | null
  transfer_group_id: string | null
  transfer_direction: TransferDirection | null
  source: string
  created_at: string
  tags: string[]
}

export interface Account {
  id: number
  name: string
  type: AccountType
  currency: string
  balance: number
  archived: boolean
}

export interface Category {
  id: number
  name: string
  group_id: number | null
  is_income: boolean
  exclude_from_budget: boolean
  exclude_from_totals: boolean
  archived: boolean
}

export interface CategoryGroup {
  id: number
  name: string
  sort_order: number
  archived: boolean
}

export interface Tag {
  id: number
  name: string
}

export interface Recurring {
  id: number
  name: string
  payee: string
  type: RecurringType
  mode: RecurringMode
  amount: number
  currency: string
  category_id: number | null
  account_id: number
  interval_unit: IntervalUnit
  interval_count: number
  start_date: string
  end_date: string | null
  active: boolean
}

export interface Occurrence {
  id: number
  recurring_id: number
  due_date: string
  status: OccurrenceStatus
  transaction_id: number | null
}

export interface Settings {
  id: number
  base_currency: string
  default_source_account_id: number | null
}

export interface Fx {
  usd_cop: string
}

export interface TransferOut {
  from_leg: Transaction
  to_leg: Transaction
}

export interface ToPay {
  overdue: Transaction[]
  upcoming: Transaction[]
  total_base: number
}

export type FundRule = "fixed" | "average" | "from-recurring"

/** A fund's stored rule. What it holds is never stored — it is derived. */
export interface Fund {
  id: number
  category_id: number
  rule: FundRule
  start_month: string
  accumulates: boolean
  amount: number | null
  window_months: number | null
  target_amount: number | null
  target_month: string | null
}

export interface FundLine {
  fund_id: number
  category_id: number
  name: string
  rule: FundRule
  start_month: string
  accumulates: boolean
}

/**
 * What one fund asks, holds and reports for one month.
 *
 * `spent` is what the category cost that month; `carries` is what survives
 * into the next one, which is 0 for a fund that resets; `next_month_has` is
 * that carry plus what the rule asks then.
 */
export interface FundStatus {
  fund_id: number
  category_id: number
  name: string
  year_month: string
  rule: FundRule
  asks: number
  holds: number
  spent: number
  carries: number
  next_month_has: number
  accumulates: boolean
  accumulation_is_implied: boolean
  on_track: boolean
  averaged_over: number | null
  spreads_over: number | null
  whole_by: string | null
}

export interface FundPreview {
  category_id: number
  would_ask: number
  warning: string | null
}

/** `income − Σ funds.asks − uncovered = free`, exactly. */
export interface MonthAvailable {
  year_month: string
  income: number
  funds: FundStatus[]
  uncovered: number
  free: number
}

/** A rate is never the money available: it spreads each cycle over its months. */
export interface MonthRates {
  year_month: string
  earning: number
  cost: number
  margin: number
}

export interface FundCreate {
  category_id: number
  rule: FundRule
  start_month: string
  accumulates?: boolean
  amount?: number | null
  window_months?: number | null
  target_amount?: number | null
  target_month?: string | null
  opening_balance?: number | null
}

export interface FundUpdate {
  rule?: FundRule
  accumulates?: boolean
  amount?: number | null
  window_months?: number | null
  target_amount?: number | null
  target_month?: string | null
  balance?: number | null
}

export interface RecurringUpdate {
  name?: string
  payee?: string
  mode?: RecurringMode
  amount?: number
  category_id?: number | null
  account_id?: number
  interval_unit?: IntervalUnit
  interval_count?: number
  start_date?: string
  end_date?: string | null
}

export interface FundsSummary {
  n_on_track: number
  n_behind: number
  set_aside: number
}
export interface FundReportLine {
  category_name: string
  asks: number
  holds: number
  spent: number
  on_track: boolean
}
export interface CategorySection {
  category: string
  group: string | null
  total: number
  pct: number
}
export interface GroupSection {
  group: string
  total: number
  pct: number
}
export interface AccountBalance {
  account: string
  currency: string
  balance: number
}
export interface DriftMoM {
  prev_month: string
  income_abs: number
  income_pct: number | null
  expense_abs: number
  expense_pct: number | null
  net_abs: number
  net_pct: number | null
}
export interface MonthlyReport {
  month: string
  income: number
  expense: number
  net: number
  funds_summary: FundsSummary
  funds: FundReportLine[]
  by_category: CategorySection[]
  by_group: GroupSection[]
  balances: AccountBalance[]
  drift_mom: DriftMoM | null
  usd_share: number
  pending: string[]
  available: MonthAvailable
  markdown: string
}

export interface TransactionFilters {
  date_from?: string
  date_to?: string
  account_id?: number
  category_id?: number
  tag?: string
  type?: TxType
  status?: TxStatus
  transfer_group_id?: string
}
export interface TransactionCreate {
  type: "expense" | "income"
  account_id: number
  amount: number
  currency: string
  date: string
  payee?: string
  category_id?: number | null
  new_category?: string | null
  notes?: string | null
  tags?: string[]
  meta_id?: number | null
}
export interface TransferCreate {
  from_account_id: number
  to_account_id: number
  amount: number
  amount_received?: number
  currency?: string
  date: string
  notes?: string | null
}
export interface TransactionUpdate {
  payee?: string
  notes?: string | null
  category_id?: number | null
  date?: string
  tags?: string[]
  meta_id?: number | null
}
export interface PlanPaymentCreate {
  payee: string
  amount: number
  due_date: string
  account_id: number
  currency?: string
  category_id?: number | null
  new_category?: string | null
  notes?: string | null
}
export interface ConfirmPaymentBody {
  amount?: number
  date?: string
}
export interface RecurringCreate {
  name: string
  type: RecurringType
  mode: RecurringMode
  amount: number
  account_id: number
  interval_unit: IntervalUnit
  start_date: string
  payee?: string
  currency?: string
  category_id?: number | null
  new_category?: string | null
  interval_count?: number
  end_date?: string | null
}
export interface AccountCreate {
  name: string
  type: AccountType
  currency: string
  balance?: number
}
export interface AccountUpdate {
  name?: string
  type?: AccountType
}
export interface CategoryCreate {
  name: string
  group_id?: number | null
  is_income?: boolean
  exclude_from_budget?: boolean
  exclude_from_totals?: boolean
}
export interface CategoryUpdate {
  name?: string
  group_id?: number | null
  is_income?: boolean
  exclude_from_budget?: boolean
  exclude_from_totals?: boolean
}
export interface CategoryGroupCreate {
  name: string
  sort_order?: number
}
export interface CategoryGroupUpdate {
  name?: string
  sort_order?: number
}
export interface TagCreate {
  name: string
}
export interface TagUpdate {
  name: string
}
export interface SettingsUpdate {
  default_source_account_id?: number | null
  base_currency?: string
}
export interface FxCreate {
  usd_cop: string
}

export class ApiError extends Error {
  status: number
  code: string
  fields: Record<string, string>
  constructor(status: number, code: string, message: string, fields?: Record<string, string>) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.code = code
    this.fields = fields ?? {}
  }
}

/**
 * Surface backend 422 field errors on a TanStack Form instance. Maps each
 * `ApiError.fields` key onto `form.setFieldMeta(field, { error })` so the
 * offending input shows the message inline instead of only in the toast.
 *
 * No-op when `err` is not an `ApiError` or has no field map, so callers can
 * always combine it with the existing toast handler:
 *
 *   onError: (e: unknown) => {
 *     applyApiErrorsToForm(myForm, e)
 *     toast.error(e instanceof ApiError ? e.message : "Error")
 *   }
 *
 * The form argument is typed loosely because TanStack Form's `FieldApi` /
 * `form` are deeply generic; we only touch `setFieldMeta`, which every
 * `@tanstack/react-form` instance exposes.
 */
// biome-ignore lint/suspicious/noExplicitAny: TanStack Form generics are not worth threading.
export function applyApiErrorsToForm(form: any, err: unknown): void {
  if (!(err instanceof ApiError)) return
  for (const [field, message] of Object.entries(err.fields)) {
    form.setFieldMeta(field, { error: message })
  }
}

/**
 * 401 interceptor: the app registers a handler (clear cache + redirect) in
 * app/providers.tsx. lib/ stays free of React/router imports.
 */
export let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn
}

export interface MetaStatus {
  meta_id: number
  name: string
  year_month: string
  amount: number
  currency: string
  target_month: string
  asks: number
  holds: number
  contributed: number
  progress: number
  complete: boolean
  closed: boolean
  waiting: boolean
}

export interface MetaCreate {
  name: string
  amount: number
  target_month: string
  currency?: string
  stated_opening?: number | null
}

export interface MetaPreview {
  asks: number
  months_left: number
  over_the_month: boolean
}

export interface MetaContribution {
  id: number
  meta_id: number
  year_month: string
  amount: number
}

export interface MonthSplit {
  year_month: string
  income: number
  consumo: number
  ahorro: number
  libre: number
  ahorro_share: number
}
