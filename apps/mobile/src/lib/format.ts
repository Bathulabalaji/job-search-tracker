import type { Stage } from "@/api/types"

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

/** Parse 'YYYY-MM-DD' as a calendar date, ignoring the browser timezone. */
function parseIsoDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number)
  return new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1))
}

export function formatDate(iso: string): string {
  const date = parseIsoDate(iso)
  return `${DAYS[date.getUTCDay()]} ${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]}`
}

export function addDays(iso: string, days: number): string {
  const date = parseIsoDate(iso)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

/** Days from `iso` until the next Monday after it. */
export function daysUntilNextMonday(iso: string): number {
  const weekday = parseIsoDate(iso).getUTCDay() // 0 = Sunday
  return (8 - weekday) % 7 || 7
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso)
  const time = date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
  return `${date.getDate()} ${MONTHS[date.getMonth()]}, ${time}`
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
}

export function titleCase(value: string): string {
  const spaced = value.replace(/_/g, " ")
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

export const STAGE_LABELS: Record<Stage, string> = {
  found: "Found",
  applied: "Applied",
  screening: "Screening",
  interview_scheduled: "Interview scheduled",
  interviewing: "Interviewing",
  offer: "Offer",
  accepted: "Accepted",
  rejected: "Rejected",
  ghosted: "Ghosted",
  parked: "Parked",
}

export const PRIORITY_LABELS: Record<number, string> = { 1: "High", 2: "Medium", 3: "Low" }

/** '2026-11-09' -> '9 Nov' */
export function formatShortDate(iso: string): string {
  const date = parseIsoDate(iso)
  return `${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]}`
}

/** '2026-11-09' -> 'Mon' */
export function formatWeekday(iso: string): string {
  return DAYS[parseIsoDate(iso).getUTCDay()] ?? ""
}

/** 0.5 -> '50%'; null -> '—' */
export function formatPercent(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)}%`
}
