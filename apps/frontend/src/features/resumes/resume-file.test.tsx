import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import type { Resume } from "@/api/types"
import { ProtectedRoute } from "@/features/auth/route-guards"
import { authResponse, mockApi } from "@/test/mock-api"
import { renderRoutes } from "@/test/render"
import { ResumeFile } from "./resume-file"

function resume(overrides: Partial<Resume> = {}): Resume {
  return {
    id: 4,
    label: "Backend",
    focus: null,
    file_name: null,
    version: "1",
    notes: null,
    document: null,
    ...overrides,
  }
}

const indexed = resume({
  file_name: "backend.pdf",
  document: {
    file_name: "backend.pdf",
    content_type: "application/pdf",
    size_bytes: 1200,
    page_count: 1,
    uploaded_at: "2026-11-14T10:00:00Z",
    text_status: "ready",
    embed_status: "ready",
    processing_error: null,
    profile: null,
  },
})

function show(r: Resume) {
  const routes = [
    { path: "/login", element: <p>Login page</p> },
    { element: <ProtectedRoute />, children: [{ path: "/r", element: <ResumeFile resume={r} /> }] },
  ]
  return renderRoutes(routes, { route: "/r" })
}

describe("ResumeFile", () => {
  it("uploads a chosen PDF as multipart with the CSRF token", async () => {
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "POST /resumes/4/document": { status: 201, body: indexed },
    })
    show(resume())
    const user = userEvent.setup()
    const input = await screen.findByLabelText("Choose a PDF for Backend")
    await user.upload(
      input,
      new File(["%PDF-1.4 hello"], "backend.pdf", { type: "application/pdf" }),
    )
    await waitFor(() => expect(api.called("POST", "/resumes/4/document")).toHaveLength(1))
    const [call] = api.called("POST", "/resumes/4/document")
    expect(call?.headers["X-CSRF-Token"]).toBe("csrf-abc")
    expect(call?.headers["Content-Type"]).toBeUndefined() // the browser sets the boundary
    const body = call?.body as { file: File } | undefined
    expect(body?.file.name).toBe("backend.pdf")
  })

  it("shows the status, opens the signed link and can remove the file", async () => {
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /resumes/4/document/url": {
        body: { url: "https://files.example/x.pdf", expires_at: "2026-11-14T10:10:00Z" },
      },
      "DELETE /resumes/4/document": { status: 204 },
    })
    const open = vi.spyOn(window, "open").mockImplementation(() => null)
    show(indexed)
    const user = userEvent.setup()
    expect(await screen.findByText("Indexed")).toBeInTheDocument()
    expect(screen.getByText("backend.pdf")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Open backend.pdf" }))
    await waitFor(() =>
      expect(open).toHaveBeenCalledWith("https://files.example/x.pdf", "_blank", "noopener"),
    )
    await user.click(screen.getByRole("button", { name: "Remove file from Backend" }))
    await waitFor(() => expect(api.called("DELETE", "/resumes/4/document")).toHaveLength(1))
  })

  it("offers a retry while indexing is paused", async () => {
    mockApi({
      "GET /auth/me": { body: authResponse() },
      "POST /resumes/4/document/process": { body: indexed },
    })
    const paused = resume({
      document: {
        ...indexed.document!,
        embed_status: "pending",
        processing_error: "Indexing is paused for now (free-tier limit).",
      },
    })
    show(paused)
    expect(await screen.findByText("Indexing paused")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Retry indexing Backend" })).toBeInTheDocument()
  })
})
