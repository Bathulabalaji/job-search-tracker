import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it } from "vitest"

import { ThemeProvider } from "@/components/theme/theme-provider"
import { ContactPage, type ContactDetails } from "@/pages/contact-page"

const FULL: ContactDetails = {
  name: "Asha Rao",
  email: "asha@example.com",
  phone: "+91 98765 43210",
  linkedinUrl: "https://www.linkedin.com/in/asha-rao",
  githubUrl: "https://github.com/asha",
}

function show(details: ContactDetails) {
  return render(
    <ThemeProvider>
      <MemoryRouter>
        <ContactPage details={details} />
      </MemoryRouter>
    </ThemeProvider>,
  )
}

describe("contact page", () => {
  it("shows every detail that is set, as safe links", () => {
    show(FULL)
    expect(screen.getByRole("heading", { level: 1, name: "Contact" })).toBeInTheDocument()
    expect(screen.getByText(/I'm Asha Rao/)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /asha@example\.com/ })).toHaveAttribute(
      "href",
      expect.stringMatching(/^mailto:asha@example\.com\?subject=/),
    )
    expect(screen.getByRole("link", { name: /\+91 98765 43210/ })).toHaveAttribute(
      "href",
      "tel:+919876543210",
    )
    const linkedin = screen.getByRole("link", { name: /linkedin\.com\/in\/asha-rao/ })
    expect(linkedin).toHaveAttribute("href", "https://www.linkedin.com/in/asha-rao")
    expect(linkedin).toHaveAttribute("rel", expect.stringContaining("noopener"))
    expect(screen.getByRole("link", { name: /github\.com\/asha/ })).toBeInTheDocument()
  })

  it("hides empty details and refuses links that are not http(s)", () => {
    show({
      name: "",
      email: "asha@example.com",
      phone: "",
      linkedinUrl: "javascript:alert(1)",
      githubUrl: "",
    })
    expect(screen.getByRole("link", { name: /asha@example\.com/ })).toBeInTheDocument()
    expect(screen.queryByText("Phone")).not.toBeInTheDocument()
    expect(screen.queryByText("LinkedIn")).not.toBeInTheDocument()
    expect(screen.queryByText("GitHub")).not.toBeInTheDocument()
    expect(screen.queryByText(/I'm/)).not.toBeInTheDocument()
  })

  it("says so when nothing is set", () => {
    show({ name: "", email: "", phone: "", linkedinUrl: "", githubUrl: "" })
    expect(screen.getByText(/have not been set up yet/)).toBeInTheDocument()
  })
})
