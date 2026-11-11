import { useQuery } from "@tanstack/react-query"
import { useRouter } from "expo-router"
import { useEffect } from "react"
import { AppState } from "react-native"

import { request } from "@/api/client"
import { useToday } from "@/api/dashboard"
import { useOpportunities } from "@/api/opportunities"
import type { Followup } from "@/api/types"
import { loadReminderSetting, useReminderSetting } from "./settings"
import {
  hasReminderPermission,
  onReminderTapped,
  remindersSupported,
  scheduleReminders,
} from "./notifications"
import { planReminders } from "./plan"

/**
 * Renders nothing. While you are signed in and reminders are on, keeps the phone's scheduled
 * notifications in step with your pending follow-ups: on launch, when you return to the app
 * and whenever follow-ups change.
 */
export function RemindersSync() {
  const router = useRouter()
  const enabled = useReminderSetting()
  const active = enabled && remindersSupported

  useEffect(() => {
    void loadReminderSetting()
  }, [])

  const today = useToday()
  const opportunities = useOpportunities({}, active)
  const pending = useQuery({
    queryKey: ["followups", "pending-all"],
    queryFn: () => request<Followup[]>("/followups", { params: { status: "pending", limit: 200 } }),
    enabled: active,
  })

  // Follow-ups changed (done, snoozed, added): the Today query refetches, so refresh ours too.
  const { refetch } = pending
  useEffect(() => {
    if (active && today.dataUpdatedAt) void refetch()
  }, [active, today.dataUpdatedAt, refetch])

  // Back from the background: things may have changed on another device.
  useEffect(() => {
    if (!active) return
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active") void refetch()
    })
    return () => sub.remove()
  }, [active, refetch])

  useEffect(() => {
    if (!active || !pending.data || !opportunities.data) return
    let cancelled = false
    void hasReminderPermission().then((granted) => {
      if (cancelled || !granted) return
      const names = new Map(opportunities.data.map((o) => [o.id, o.company]))
      return scheduleReminders(planReminders(pending.data, names))
    })
    return () => {
      cancelled = true
    }
  }, [active, pending.data, opportunities.data])

  useEffect(() => onReminderTapped(() => router.navigate("/today")), [router])

  return null
}
