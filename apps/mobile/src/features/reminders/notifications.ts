import * as Notifications from "expo-notifications"
import { Platform } from "react-native"

import type { PlannedReminder } from "./plan"

const CHANNEL_ID = "followups"

/** Native notifications are not available on the web preview. */
export const remindersSupported = Platform.OS === "ios" || Platform.OS === "android"

if (remindersSupported) {
  // Show the reminder even if the app happens to be open.
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: false,
      shouldSetBadge: false,
    }),
  })
}

export type PermissionResult = "granted" | "denied"

export async function ensureReminderPermission(): Promise<PermissionResult> {
  if (!remindersSupported) return "denied"
  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync(CHANNEL_ID, {
      name: "Follow-up reminders",
      importance: Notifications.AndroidImportance.DEFAULT,
    })
  }
  const current = await Notifications.getPermissionsAsync()
  if (current.granted) return "granted"
  if (!current.canAskAgain) return "denied"
  const asked = await Notifications.requestPermissionsAsync()
  return asked.granted ? "granted" : "denied"
}

export async function hasReminderPermission(): Promise<boolean> {
  if (!remindersSupported) return false
  return (await Notifications.getPermissionsAsync()).granted
}

/** Replaces everything we scheduled before with exactly this plan. */
export async function scheduleReminders(plan: readonly PlannedReminder[]): Promise<void> {
  if (!remindersSupported) return
  await Notifications.cancelAllScheduledNotificationsAsync()
  for (const reminder of plan) {
    await Notifications.scheduleNotificationAsync({
      content: {
        title: reminder.title,
        body: reminder.body,
        data: { screen: "today" },
      },
      trigger: {
        type: Notifications.SchedulableTriggerInputTypes.DATE,
        date: reminder.at,
        channelId: CHANNEL_ID,
      },
    })
  }
}

/** Removes every pending reminder (switching off, or signing out). */
export async function cancelReminders(): Promise<void> {
  if (!remindersSupported) return
  try {
    await Notifications.cancelAllScheduledNotificationsAsync()
  } catch {
    // Nothing scheduled, or the native module is unavailable: nothing to clean up.
  }
}

export function onReminderTapped(handler: () => void): () => void {
  if (!remindersSupported) return () => undefined
  const subscription = Notifications.addNotificationResponseReceivedListener(() => handler())
  return () => subscription.remove()
}
