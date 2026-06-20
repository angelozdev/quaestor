export const qk = {
  toPay: (since: string, until: string) => ["planned", "to-pay", since, until] as const,
  accounts: () => ["accounts"] as const,
  safeToSpend: (month: string) => ["budgets", "safe-to-spend", month] as const,
  goalsProgress: () => ["goals", "progress"] as const,
  report: (month: string) => ["reports", month] as const,
};
