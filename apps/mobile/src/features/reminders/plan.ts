import type { Followup } from "@/api/types"

export interface PlannedReminder {
  /** Local date-time the notification fires. */
  at: Date
  title: string
  body: string
  /** The YYYY-MM-DD this reminder is for (used as a stable id). */
  forDate: string
}

export const REMINDER_HOUR = 9
/** Phones cap scheduled notifications (iOS: 64). Two weeks ahead is plenty. */
export const REMINDER_DAYS_AHEAD = 14
const MAX_NAMES = 3

function isoOf(date: Date): string {
  const m = String(date.getMonth() + 1).padStart(2, "0")
  const d = String(date.getDate()).padStart(2, "0")
  return `${date.getFullYear()}-${m}-${d}`
}

function atNine(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number) as [number, number, number]
  return new Date(y, m - 1, d, REMINDER_HOUR, 0, 0, 0)
}

function describe(count: number, names: string[]): { title: string; body: string } {
  const unique = [...new Set(names)]
  const shown = unique.slice(0, MAX_NAMES).join(", ")
  const more = unique.length > MAX_NAMES ? ` and ${unique.length - MAX_NAMES} more` : ""
  return {
    title: count === 1 ? "1 follow-up to do" : `${count} follow-ups to do`,
    body: `${shown}${more}`,
  }
}

/**
 * Turns pending follow-ups into at most one reminder per day, at 9:00 local time.
 *
 * - A follow-up due in the future is reminded on its due date.
 * - One already overdue (or due today after 9:00 has passed) rolls into the next 9:00, so
 *   a missed one still gets a nudge instead of silence.
 * - Done and skipped follow-ups never produce a reminder.
 */
export function planReminders(
  followups: readonly Followup[],
  companyById: ReadonlyMap<number, string>,
  now: Date = new Date(),
): PlannedReminder[] {
  const today = isoOf(now)
  const lastDay = new Date(now.getFullYear(), now.getMonth(), now.getDate() + REMINDER_DAYS_AHEAD)
  const lastIso = isoOf(lastDay)
  // The first 9:00 still ahead of us: today's if it has not passed, otherwise tomorrow's.
  const tomorrow = isoOf(new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1))
  const firstIso = atNine(today).getTime() > now.getTime() ? today : tomorrow

  const groups = new Map<string, { count: number; names: string[] }>()
  for (const f of followups) {
    if (f.status !== "pending") continue
    // Overdue or due before the first reminder slot: fire at the first slot.
    const day = f.due_date < firstIso ? firstIso : f.due_date
    if (day > lastIso) continue
    const group = groups.get(day) ?? { count: 0, names: [] }
    group.count += 1
    group.names.push(companyById.get(f.opportunity_id) ?? "A follow-up")
    groups.set(day, group)
  }

  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, group]) => {
      const { title, body } = describe(group.count, group.names)
      return { at: atNine(day), forDate: day, title, body }
    })
}
