import { fireEvent, screen } from "@testing-library/react-native"
import { useState } from "react"

import { renderWithTheme } from "@/test/render"
import { Button } from "./button"
import { ProgressRing } from "./progress"
import { SegmentedControl } from "./segmented-control"
import { Stepper } from "./stepper"
import { TextField } from "./text-field"

describe("Button", () => {
  it("calls onPress", async () => {
    const onPress = jest.fn()
    await renderWithTheme(<Button label="Save" onPress={onPress} />)
    await fireEvent.press(screen.getByRole("button", { name: "Save" }))
    expect(onPress).toHaveBeenCalledTimes(1)
  })

  it("ignores presses while loading and says it is busy", async () => {
    const onPress = jest.fn()
    await renderWithTheme(<Button label="Save" loading onPress={onPress} />)
    const button = screen.getByRole("button", { name: "Save" })
    await fireEvent.press(button)
    expect(onPress).not.toHaveBeenCalled()
    expect(button).toBeDisabled()
  })
})

describe("SegmentedControl", () => {
  function Harness() {
    const [value, setValue] = useState<"a" | "b">("a")
    return (
      <SegmentedControl
        options={[
          { value: "a", label: "First" },
          { value: "b", label: "Second" },
        ]}
        value={value}
        onChange={setValue}
      />
    )
  }
  it("switches the selected tab", async () => {
    await renderWithTheme(<Harness />)
    expect(screen.getByRole("tab", { name: "First" })).toBeSelected()
    await fireEvent.press(screen.getByRole("tab", { name: "Second" }))
    expect(screen.getByRole("tab", { name: "Second" })).toBeSelected()
  })
})

describe("Stepper", () => {
  function Harness({ max = 5 }: { max?: number }) {
    const [value, setValue] = useState(0)
    return <Stepper label="Applications" value={value} max={max} onChange={setValue} />
  }
  it("increments and never goes below zero", async () => {
    await renderWithTheme(<Harness />)
    await fireEvent.press(screen.getByRole("button", { name: "Decrease Applications" }))
    expect(screen.getByDisplayValue("0")).toBeTruthy()
    await fireEvent.press(screen.getByRole("button", { name: "Increase Applications" }))
    expect(screen.getByDisplayValue("1")).toBeTruthy()
  })
  it("clamps typed values to the maximum", async () => {
    await renderWithTheme(<Harness max={5} />)
    await fireEvent.changeText(screen.getByLabelText("Applications"), "99")
    expect(screen.getByDisplayValue("5")).toBeTruthy()
  })
})

describe("ProgressRing", () => {
  it("describes itself for screen readers", async () => {
    await renderWithTheme(<ProgressRing percent={45} label="Applications" caption="9 / 20" />)
    expect(screen.getByLabelText("Applications: 9 / 20, 45 percent")).toBeTruthy()
  })
  it("says when no target is set", async () => {
    await renderWithTheme(<ProgressRing percent={null} label="Messages" caption="3" />)
    expect(screen.getByLabelText(/no target set/)).toBeTruthy()
  })
})

describe("TextField", () => {
  it("shows an error and hides the password until revealed", async () => {
    await renderWithTheme(<TextField label="Password" value="secret" onChangeText={() => undefined} secureToggle error="Too short" />)
    expect(screen.getByText("Too short")).toBeTruthy()
    expect(screen.getByLabelText("Password").props.secureTextEntry).toBe(true)
    await fireEvent.press(screen.getByRole("button", { name: "Show password" }))
    expect(screen.getByLabelText("Password").props.secureTextEntry).toBe(false)
  })
})
