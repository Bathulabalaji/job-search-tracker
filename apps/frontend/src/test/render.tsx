import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, type RenderResult } from "@testing-library/react"
import { createMemoryRouter, RouterProvider, type RouteObject } from "react-router-dom"

import { ThemeProvider } from "@/components/theme/theme-provider"
import { AuthProvider } from "@/features/auth/auth-provider"

interface Options {
  /** Where the test starts, for example "/login?next=%2Fprep". */
  route?: string
}

/** Renders routes with the same providers as the real app (theme, query cache, auth). */
export function renderRoutes(
  routes: RouteObject[],
  { route = "/" }: Options = {},
): RenderResult & {
  router: ReturnType<typeof createMemoryRouter>
  queryClient: QueryClient
} {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(routes, { initialEntries: [route] })
  const result = render(
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>,
  )
  return { ...result, router, queryClient }
}
