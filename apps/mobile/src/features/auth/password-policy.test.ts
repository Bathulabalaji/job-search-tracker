import { passwordChecks, passwordProblem } from "./password-policy"

describe("passwordProblem", () => {
  it.each([
    ["short1", "at least 10"],
    ["longenoughbutnodigits", "number"],
    ["1234567890123", "letter"],
  ])("rejects %s", (password, fragment) => {
    expect(passwordProblem(password)).toContain(fragment)
  })

  it("accepts a good password", () => expect(passwordProblem("Correct-Horse-9")).toBeNull())

  it("refuses passwords containing the email name or the person's name", () => {
    expect(passwordProblem("alicewalker-2026", { email: "alicewalker@example.com" })).toMatch(/email/)
    expect(passwordProblem("Walker-passw0rd!", { fullName: "Alice Walker" })).toMatch(/name/)
  })

  it("reports each requirement for the checklist", () => {
    expect(passwordChecks("abc").map((c) => c.met)).toEqual([false, true, false])
    expect(passwordChecks("abcdefghij1").every((c) => c.met)).toBe(true)
  })
})
