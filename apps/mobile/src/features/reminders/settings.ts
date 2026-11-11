import { useSyncExternalStore } from "react"

import { secureStorage } from "@/lib/secure-storage"

const KEY = "followup-reminders"
type Listener = () => void

let enabled = false
let loaded = false
const listeners = new Set<Listener>()

function emit(): void {
  listeners.forEach((l) => l())
}

/** Reads the saved choice once. Safe to call repeatedly. */
export async function loadReminderSetting(): Promise<boolean> {
  if (!loaded) {
    enabled = (await secureStorage.get(KEY)) === "on"
    loaded = true
    emit()
  }
  return enabled
}

export async function saveReminderSetting(value: boolean): Promise<void> {
  enabled = value
  loaded = true
  if (value) await secureStorage.set(KEY, "on")
  else await secureStorage.remove(KEY)
  emit()
}

function subscribe(listener: Listener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** Whether follow-up reminders are switched on. */
export function useReminderSetting(): boolean {
  return useSyncExternalStore(subscribe, () => enabled, () => false)
}
