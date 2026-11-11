import { addDays, daysUntilNextMonday, formatDate, formatPercent, titleCase } from "./format"
import { isIsoDate, todayIso, weekStartOf } from "./dates"

describe("dates", () => {
  it("formats calendar dates without timezone drift", () => {
    expect(formatDate("2026-11-11")).toBe("Wed 11 Nov")
    expect(addDays("2026-11-30", 1)).toBe("2026-12-01")
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28")
  })

  it("finds the next Monday", () => {
    expect(daysUntilNextMonday("2026-11-11")).toBe(5) // Wed -> Mon
    expect(daysUntilNextMonday("2026-11-09")).toBe(7) // a Monday means the following one
  })

  it("uses the phone's local date for today", () => {
    expect(todayIso(new Date(2026, 10, 11, 23, 59))).toBe("2026-11-11")
    expect(todayIso(new Date(2026, 0, 5, 0, 1))).toBe("2026-01-05")
  })

  it("validates real calendar dates only", () => {
    expect(isIsoDate("2026-02-28")).toBe(true)
    expect(isIsoDate("2026-02-30")).toBe(false)
    expect(isIsoDate("26-02-28")).toBe(false)
    expect(isIsoDate("")).toBe(false)
  })

  it("finds the Monday of a week", () => {
    expect(weekStartOf("2026-11-11")).toBe("2026-11-09")
    expect(weekStartOf("2026-11-15")).toBe("2026-11-09") // Sunday belongs to the previous Monday
    expect(weekStartOf("2026-11-09")).toBe("2026-11-09")
  })
})

describe("text helpers", () => {
  it("title-cases snake case", () => expect(titleCase("interview_scheduled")).toBe("Interview scheduled"))
  it("formats percentages", () => {
    expect(formatPercent(0.456)).toBe("46%")
    expect(formatPercent(null)).toBe("—")
  })
})
