// Types mirror the P1 /api JSON contract (cents are integers).
export type TxType = "income" | "expense" | "transfer";
export type TxStatus = "planned" | "posted" | "skipped";

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
  type: string;
  currency: string;
  balance: number;
  archived: boolean;
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
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
  // reads
  accounts: () => request<Account[]>("/accounts"),
  toPay: (since: string, until: string) =>
    request<ToPay>(`/planned/to-pay?since=${since}&until=${until}`),
  safeToSpend: (month: string) => request<SafeToSpend>(`/budgets/safe-to-spend?month=${month}`),
  goalsProgress: () => request<GoalProgress[]>("/goals/progress"),
  report: (month: string) => request<MonthlyReport>(`/reports?month=${month}`),
  // mutations
  confirmPayment: (id: number, body: { amount?: number; date?: string } = {}) =>
    request<Transaction>(`/planned/${id}/confirm`, { method: "POST", body: JSON.stringify(body) }),
};
