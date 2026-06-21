import { get, put, qs } from "./client";
import type { BudgetLine, BudgetAssign, SafeToSpend } from "./types";

export const listBudgets  = (month: string) => get<BudgetLine[]>(`/budgets${qs({ month })}`);
export const assignBudget = (body: BudgetAssign) => put<BudgetLine>("/budgets", body);
export const safeToSpend  = (month: string) => get<SafeToSpend>(`/budgets/safe-to-spend${qs({ month })}`);
