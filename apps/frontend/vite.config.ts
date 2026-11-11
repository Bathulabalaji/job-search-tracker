import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import path from "node:path"
import { defineConfig } from "vitest/config"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "./src") },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
    // Tests must not depend on a developer's local .env (e.g. a real Google client ID).
    env: {
      VITE_GOOGLE_CLIENT_ID: "",
      VITE_TERMS_URL: "",
      VITE_PRIVACY_URL: "",
      VITE_API_BASE_URL: "http://localhost:8000/api/v1",
    },
    restoreMocks: true,
  },
})
