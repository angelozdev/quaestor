// Types mirror the P1 /api JSON contract (cents are integers).
export type TxType = "income" | "expense" | "transfer";
export type TxStatus = "planned" | "posted" | "skipped";
export type AccountType = "debit" | "credit" | "cash" | "savings";
export type IntervalUnit = "day" | "week" | "month" | "year";
export type RecurringMode = "auto" | "manual";
export type RecurringType = "expense" | "income";
export type OccurrenceStatus = "posted" | "planned" | "skipped";

export interface Transaction {
  id: number;
  date: string;
  payee: string;
  notes: string | null;
  type: TxType;
  status: TxStatus;
  amount: number;
  currency: string;
  fx_rate: string;
  to_base: number;
  account_id: number;
  category_id: number | null;
  transfer_group_id: string | null;
  source: string;
  created_at: string;
}

export interface Account {
  id: number;
  name: string;
  type: AccountType;
  currency: string;
  balance: number;
  archived: boolean;
}

export interface Category {
  id: number;
  name: string;
  group_id: number | null;
  is_income: boolean;
  exclude_from_budget: boolean;
  exclude_from_totals: boolean;
  archived: boolean;
}

export interface CategoryGroup {
  id: number;
  name: string;
  sort_order: number;
  archived: boolean;
}

export interface Tag {
  id: number;
  name: string;
}

export interface Recurring {
  id: number;
  name: string;
  payee: string;
  type: RecurringType;
  mode: RecurringMode;
  amount: number;
  currency: string;
  category_id: number | null;
  account_id: number;
  interval_unit: IntervalUnit;
  interval_count: number;
  start_date: string;
  end_date: string | null;
  active: boolean;
}

export interface Occurrence {
  id: number;
  recurring_id: number;
  due_date: string;
  status: OccurrenceStatus;
  transaction_id: number | null;
}

export interface Settings {
  id: number;
  base_currency: string;
  default_source_account_id: number | null;
}

export interface Fx {
  date: string;
  usd_cop: string;
}

export interface TransferOut {
  from_leg: Transaction;
  to_leg: Transaction;
}

export interface ToPay {
  items: Transaction[];
  total_base: number;
}

export interface CommittedItem {
  kind: string;
  name: string;
  date: string;
  amount: number;
}

export interface SafeToSpend {
  year_month: string;
  income_forecast: number;
  committed: number;
  assigned_envelopes: number;
  free: number;
  committed_breakdown: CommittedItem[];
}

export interface GoalProgress {
  goal_id: number;
  name: string;
  type: string;
  monthly_amount: number;
  saved: number;
  target_amount: number | null;
  deadline: string | null;
  monthly_required: number | null;
  on_track: boolean | null;
  eta: string | null;
  remaining: number | null;
}

export type GoalStatus = "active" | "reached" | "paused";

export interface Goal {
  id: number;
  name: string;
  target_amount: number | null;
  deadline: string | null;
  monthly_amount: number;
  savings_account_id: number;
  status: GoalStatus;
}

export interface GoalContribution {
  id: number;
  goal_id: number;
  date: string;
  amount: number;
  source: string;
  transaction_id: number | null;
}

export interface BudgetLine {
  category_id: number;
  category_name: string;
  assigned: number;
  rollover_in: number;
  spent: number;
  available: number;
  pct_used: number;
  status: string;
}

export interface GoalCreate {
  name: string;
  monthly_amount: number;
  savings_account_id: number;
  target_amount?: number | null;
  deadline?: string | null;
}

export interface GoalUpdate {
  name?: string;
  monthly_amount?: number;
  target_amount?: number | null;
  deadline?: string | null;
  savings_account_id?: number;
}

export interface GoalContributeBody {
  amount: number;
  date: string;
}

export interface RecurringUpdate {
  name?: string;
  payee?: string;
  mode?: RecurringMode;
  amount?: number;
  category_id?: number | null;
  account_id?: number;
  interval_unit?: IntervalUnit;
  interval_count?: number;
  start_date?: string;
  end_date?: string | null;
}

export interface BudgetAssign {
  category_id: number;
  year_month: string;
  amount_assigned: number;
}

export interface EnvelopesSummary {
  n_green: number;
  n_red: number;
  rollover_generated: number;
}
export interface EnvelopeLine {
  category: string;
  allocated: number;
  rollover_in: number;
  spent: number;
  available: number;
  status: string;
}
export interface CategorySection {
  category: string;
  group: string | null;
  total: number;
  pct: number;
}
export interface GroupSection {
  group: string;
  total: number;
  pct: number;
}
export interface GoalLine {
  name: string;
  accumulated: number;
  target: number | null;
  eta: string | null;
  on_track: boolean | null;
}
export interface AccountBalance {
  account: string;
  currency: string;
  balance: number;
}
export interface DriftMoM {
  prev_month: string;
  income_abs: number;
  income_pct: number | null;
  expense_abs: number;
  expense_pct: number | null;
  net_abs: number;
  net_pct: number | null;
}
export interface MonthlyReport {
  month: string;
  income: number;
  expense: number;
  net: number;
  envelopes_summary: EnvelopesSummary;
  envelopes: EnvelopeLine[];
  by_category: CategorySection[];
  by_group: GroupSection[];
  goals: GoalLine[];
  balances: AccountBalance[];
  drift_mom: DriftMoM | null;
  usd_share: number;
  pending: string[];
  safe_to_spend: SafeToSpend;
  markdown: string;
}

// ---- Request payloads (only fields the API accepts) ----
export interface TransactionFilters {
  date_from?: string;
  date_to?: string;
  account_id?: number;
  category_id?: number;
  tag?: string;
  type?: TxType;
  status?: TxStatus;
}
export interface TransactionCreate {
  type: "expense" | "income";
  account_id: number;
  amount: number;
  currency: string;
  date: string;
  payee?: string;
  category_id?: number | null;
  notes?: string | null;
  fx_rate?: string;
}
export interface TransferCreate {
  from_account_id: number;
  to_account_id: number;
  amount: number;
  currency: string;
  date: string;
  notes?: string | null;
  fx_rate?: string;
}
export interface TransactionUpdate {
  payee?: string;
  notes?: string | null;
  category_id?: number | null;
  date?: string;
}
export interface PlanPaymentCreate {
  payee: string;
  amount: number;
  due_date: string;
  account_id: number;
  currency?: string;
  category_id?: number | null;
  notes?: string | null;
}
export interface ConfirmPaymentBody {
  amount?: number;
  date?: string;
}
export interface RecurringCreate {
  name: string;
  type: RecurringType;
  mode: RecurringMode;
  amount: number;
  account_id: number;
  interval_unit: IntervalUnit;
  start_date: string;
  payee?: string;
  currency?: string;
  category_id?: number | null;
  interval_count?: number;
  end_date?: string | null;
}
export interface AccountCreate {
  name: string;
  type: AccountType;
  currency: string;
  balance?: number;
}
export interface AccountUpdate {
  name?: string;
  type?: AccountType;
}
export interface CategoryCreate {
  name: string;
  group_id?: number | null;
  is_income?: boolean;
  exclude_from_budget?: boolean;
  exclude_from_totals?: boolean;
}
export interface CategoryUpdate {
  name?: string;
  group_id?: number | null;
  is_income?: boolean;
  exclude_from_budget?: boolean;
  exclude_from_totals?: boolean;
}
export interface CategoryGroupCreate {
  name: string;
  sort_order?: number;
}
export interface CategoryGroupUpdate {
  name?: string;
  sort_order?: number;
}
export interface TagCreate {
  name: string;
}
export interface TagUpdate {
  name: string;
}
export interface SettingsUpdate {
  default_source_account_id?: number | null;
  base_currency?: string;
}
export interface FxCreate {
  date: string;
  usd_cop: string;
}

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

// 401 interceptor: the app registers a handler (clear cache + redirect) in
// app/providers.tsx. lib/ stays free of React/router imports.
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (res.status === 401 && !path.startsWith("/auth")) {
    onUnauthorized?.();
    return undefined as unknown as T;
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const code = (data && data.error) || "Error";
    const message = (data && data.detail) || `Request failed (${res.status})`;
    throw new ApiError(res.status, code, message);
  }
  return data as T;
}

export const api = {
  // auth
  login: (password: string) =>
    request<{ ok: boolean }>("/auth/login", { method: "POST", body: JSON.stringify({ password }) }),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  me: () => request<{ authenticated: boolean }>("/auth/me"),

  // transactions
  listTransactions: (filters: TransactionFilters = {}) =>
    request<Transaction[]>(`/transactions${qs(filters as Record<string, string | number | boolean | undefined>)}`),
  getTransaction: (id: number) => request<Transaction>(`/transactions/${id}`),
  createTransaction: (body: TransactionCreate) =>
    request<Transaction>("/transactions", { method: "POST", body: JSON.stringify(body) }),
  createTransfer: (body: TransferCreate) =>
    request<TransferOut>("/transactions/transfer", { method: "POST", body: JSON.stringify(body) }),
  updateTransaction: (id: number, body: TransactionUpdate) =>
    request<Transaction>(`/transactions/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteTransaction: (id: number) =>
    request<void>(`/transactions/${id}`, { method: "DELETE" }),

  // planned / to-pay
  toPay: (since: string, until: string) =>
    request<ToPay>(`/planned/to-pay${qs({ since, until })}`),
  planPayment: (body: PlanPaymentCreate) =>
    request<Transaction>("/planned", { method: "POST", body: JSON.stringify(body) }),
  confirmPayment: (id: number, body: ConfirmPaymentBody = {}) =>
    request<Transaction>(`/planned/${id}/confirm`, { method: "POST", body: JSON.stringify(body) }),
  skipPlanned: (id: number) =>
    request<Transaction>(`/planned/${id}/skip`, { method: "POST", body: JSON.stringify({}) }),

  // recurring
  listRecurring: (active?: boolean) => request<Recurring[]>(`/recurring${qs({ active })}`),
  createRecurring: (body: RecurringCreate) =>
    request<Recurring>("/recurring", { method: "POST", body: JSON.stringify(body) }),
  skipRecurring: (id: number, due_date: string) =>
    request<Occurrence>(`/recurring/${id}/skip`, { method: "POST", body: JSON.stringify({ due_date }) }),
  updateRecurring: (id: number, body: RecurringUpdate) =>
    request<Recurring>(`/recurring/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteRecurring: (id: number) => request<void>(`/recurring/${id}`, { method: "DELETE" }),
  restoreRecurring: (id: number) =>
    request<Recurring>(`/recurring/${id}/restore`, { method: "POST", body: JSON.stringify({}) }),

  // accounts
  listAccounts: (archived = false) => request<Account[]>(`/accounts${qs({ archived })}`),
  getAccount: (id: number) => request<Account>(`/accounts/${id}`),
  createAccount: (body: AccountCreate) =>
    request<Account>("/accounts", { method: "POST", body: JSON.stringify(body) }),
  updateAccount: (id: number, body: AccountUpdate) =>
    request<Account>(`/accounts/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  archiveAccount: (id: number) => request<void>(`/accounts/${id}`, { method: "DELETE" }),

  // categories
  listCategories: (archived = false) => request<Category[]>(`/categories${qs({ archived })}`),
  createCategory: (body: CategoryCreate) =>
    request<Category>("/categories", { method: "POST", body: JSON.stringify(body) }),
  updateCategory: (id: number, body: CategoryUpdate) =>
    request<Category>(`/categories/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  archiveCategory: (id: number) => request<void>(`/categories/${id}`, { method: "DELETE" }),

  // category groups
  listCategoryGroups: (archived = false) =>
    request<CategoryGroup[]>(`/category-groups${qs({ archived })}`),
  createCategoryGroup: (body: CategoryGroupCreate) =>
    request<CategoryGroup>("/category-groups", { method: "POST", body: JSON.stringify(body) }),
  updateCategoryGroup: (id: number, body: CategoryGroupUpdate) =>
    request<CategoryGroup>(`/category-groups/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  archiveCategoryGroup: (id: number) =>
    request<void>(`/category-groups/${id}`, { method: "DELETE" }),

  // tags
  listTags: () => request<Tag[]>("/tags"),
  createTag: (body: TagCreate) =>
    request<Tag>("/tags", { method: "POST", body: JSON.stringify(body) }),
  updateTag: (id: number, body: TagUpdate) =>
    request<Tag>(`/tags/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteTag: (id: number) => request<void>(`/tags/${id}`, { method: "DELETE" }),

  // settings
  getSettings: () => request<Settings>("/settings"),
  updateSettings: (body: SettingsUpdate) =>
    request<Settings>("/settings", { method: "PATCH", body: JSON.stringify(body) }),

  // fx
  getFx: (date?: string) => request<Fx>(`/fx${qs({ date })}`),
  setFx: (body: FxCreate) =>
    request<Fx>("/fx", { method: "POST", body: JSON.stringify(body) }),

  // goals (Phase 2)
  listGoals: () => request<Goal[]>("/goals"),
  createGoal: (body: GoalCreate) =>
    request<Goal>("/goals", { method: "POST", body: JSON.stringify(body) }),
  updateGoal: (id: number, body: GoalUpdate) =>
    request<Goal>(`/goals/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  pauseGoal: (id: number) => request<void>(`/goals/${id}`, { method: "DELETE" }),
  restoreGoal: (id: number) =>
    request<Goal>(`/goals/${id}/restore`, { method: "POST", body: JSON.stringify({}) }),
  contributeGoal: (id: number, body: GoalContributeBody) =>
    request<GoalContribution>(`/goals/${id}/contribute`, { method: "POST", body: JSON.stringify(body) }),

  // budgets (Phase 2)
  listBudgets: (month: string) => request<BudgetLine[]>(`/budgets${qs({ month })}`),
  assignBudget: (body: BudgetAssign) =>
    request<BudgetLine>("/budgets", { method: "PUT", body: JSON.stringify(body) }),

  // masters restore (Phase 2)
  restoreAccount: (id: number) =>
    request<Account>(`/accounts/${id}/restore`, { method: "POST", body: JSON.stringify({}) }),
  restoreCategory: (id: number) =>
    request<Category>(`/categories/${id}/restore`, { method: "POST", body: JSON.stringify({}) }),
  restoreCategoryGroup: (id: number) =>
    request<CategoryGroup>(`/category-groups/${id}/restore`, { method: "POST", body: JSON.stringify({}) }),

  // planning reads
  safeToSpend: (month: string) => request<SafeToSpend>(`/budgets/safe-to-spend${qs({ month })}`),
  goalsProgress: () => request<GoalProgress[]>("/goals/progress"),
  report: (month: string) => request<MonthlyReport>(`/reports${qs({ month })}`),
};
