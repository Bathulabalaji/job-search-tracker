import type { Followup } from "@/api/types"
import { planReminders } from "./plan"

const names = new Map([
  [1, "Acme"],
  [2, "Globex"],
  [3, "Initech"],
  [4, "Umbrella"],
  [5, "Stark"],
])

function followup(id: number, opportunityId: number, due: string, status: Followup["status"] = "pending"): Followup {
  return { id, opportunity_id: opportunityId, due_date: due, channel: "email", message_draft: null, status, done_at: null }
}

// Wed 11 Nov 2026, 07:30 local: today's 9:00 reminder is still ahead.
const morning = new Date(2026, 10, 11, 7, 30)
// Same day, 15:00: today's 9:00 has passed.
const afternoon = new Date(2026, 10, 11, 15, 0)

describe("planReminders", () => {
  it("reminds at 9:00 local time on the due date", () => {
    const [reminder] = planReminders([followup(1, 1, "2026-11-13")], names, morning)
    expect(reminder?.at).toEqual(new Date(2026, 10, 13, 9, 0))
    expect(reminder?.title).toBe("1 follow-up to do")
    expect(reminder?.body).toBe("Acme")
  })

  it("combines several follow-ups on one day into one notification", () => {
    const plan = planReminders([followup(1, 1, "2026-11-13"), followup(2, 2, "2026-11-13")], names, morning)
    expect(plan).toHaveLength(1)
    expect(plan[0]?.title).toBe("2 follow-ups to do")
    expect(plan[0]?.body).toBe("Acme, Globex")
  })

  it("names the first three companies and counts the rest", () => {
    const plan = planReminders([1, 2, 3, 4, 5].map((n) => followup(n, n, "2026-11-12")), names, morning)
    expect(plan[0]?.body).toBe("Acme, Globex, Initech and 2 more")
  })

  it("lists a company once even with two follow-ups", () => {
    const plan = planReminders([followup(1, 1, "2026-11-12"), followup(2, 1, "2026-11-12")], names, morning)
    expect(plan[0]?.title).toBe("2 follow-ups to do")
    expect(plan[0]?.body).toBe("Acme")
  })

  it("rolls overdue follow-ups into today's 9:00 when it is still ahead", () => {
    const [reminder] = planReminders([followup(1, 1, "2026-11-08")], names, morning)
    expect(reminder?.at).toEqual(new Date(2026, 10, 11, 9, 0))
  })

  it("rolls overdue and due-today into tomorrow's 9:00 once today's has passed", () => {
    const plan = planReminders([followup(1, 1, "2026-11-08"), followup(2, 2, "2026-11-11")], names, afternoon)
    expect(plan).toHaveLength(1)
    expect(plan[0]?.at).toEqual(new Date(2026, 10, 12, 9, 0))
    expect(plan[0]?.title).toBe("2 follow-ups to do")
  })

  it("never schedules in the past", () => {
    const plan = planReminders([followup(1, 1, "2026-11-01"), followup(2, 2, "2026-11-20")], names, afternoon)
    expect(plan.every((r) => r.at.getTime() > afternoon.getTime())).toBe(true)
  })

  it("ignores done and skipped follow-ups", () => {
    const plan = planReminders([followup(1, 1, "2026-11-13", "done"), followup(2, 2, "2026-11-13", "skipped")], names, morning)
    expect(plan).toEqual([])
  })

  it("ignores follow-ups beyond the two-week window", () => {
    expect(planReminders([followup(1, 1, "2026-12-30")], names, morning)).toEqual([])
  })

  it("orders reminders by date and tolerates an unknown company", () => {
    const plan = planReminders([followup(1, 99, "2026-11-15"), followup(2, 1, "2026-11-12")], names, morning)
    expect(plan.map((r) => r.forDate)).toEqual(["2026-11-12", "2026-11-15"])
    expect(plan[1]?.body).toBe("A follow-up")
  })
})
