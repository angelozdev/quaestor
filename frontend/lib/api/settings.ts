import { get, patch } from "./client";
import type { Settings, SettingsUpdate } from "./types";

export const getSettings    = ()                          => get<Settings>("/settings");
export const updateSettings = (body: SettingsUpdate)       => patch<Settings>("/settings", body);
