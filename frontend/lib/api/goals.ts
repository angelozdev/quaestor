import { del, get, patch, post } from "./client"
import type {
  Goal,
  GoalContributeBody,
  GoalContribution,
  GoalCreate,
  GoalProgress,
  GoalUpdate,
} from "./types"

export const listGoals = () => get<Goal[]>("/goals")
export const createGoal = (body: GoalCreate) => post<Goal>("/goals", body)
export const updateGoal = (id: number, body: GoalUpdate) => patch<Goal>(`/goals/${id}`, body)
export const pauseGoal = (id: number) => del<void>(`/goals/${id}`)
export const restoreGoal = (id: number) => post<Goal>(`/goals/${id}/restore`, {})
export const contributeGoal = (id: number, body: GoalContributeBody) =>
  post<GoalContribution>(`/goals/${id}/contribute`, body)
export const goalsProgress = () => get<GoalProgress[]>("/goals/progress")
