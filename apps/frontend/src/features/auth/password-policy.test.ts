import { describe, expect, it } from "vitest"

import { passwordChecks, passwordProblem, safeNextPath } from "./password-policy"

describe("passwordProblem", () => {
  it("accepts a reasonable password", () => {
    expect(passwordProblem("Correct-Horse-9")).toBeNull()
  })

  it.each([
    ["short1", /at least 10/i],
    ["onlyletterspassword", /number/i],
    ["12345678901234", /letter/i],
  ])("rejects %s", (password, message) => {
    expect(passwordProblem(password)).toMatch(message)
  })

  it("rejects passwords built from the email name or the person's name", () => {
    expect(passwordProblem("alice-secret-9", { email: "alice@x.io" })).toMatch(/email/i)
    expect(passwordProblem("Walker-secret-9", { fullName: "Alice Walker" })).toMatch(/name/i)
  })

  it("does not police short name fragments", () => {
    expect(passwordProblem("Correct-Horse-9", { fullName: "Jo Li" })).toBeNull()
  })

  it("rejects absurdly long passwords", () => {
    expect(passwordProblem("a1".repeat(80))).toMatch(/at most/i)
  })
})

describe("passwordChecks", () => {
  it("reports each rule separately", () => {
    const met = (pw: string) => passwordChecks(pw).map((c) => c.met)
    expect(met("abc")).toEqual([false, true, false])
    expect(met("abcdefghij1")).toEqual([true, true, true])
  })
})

describe("safeNextPath (open-redirect protection)", () => {
  it.each(["/", "/prep", "/opportunities/4?tab=jd"])("keeps the local path %s", (path) => {
    expect(safeNextPath(path)).toBe(path)
  })

  it.each([
    null,
    "",
    "https://evil.example",
    "//evil.example",
    "/\\evil.example",
    "javascript:alert(1)",
    "prep",
    "/login",
    "/register?x=1",
    "/reset-password",
  ])("falls back to / for %s", (path) => {
    expect(safeNextPath(path)).toBe("/")
  })
})
