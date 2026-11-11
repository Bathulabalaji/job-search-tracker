export type ToastKind = "success" | "error" | "info"
export interface ToastMessage {
  id: number
  kind: ToastKind
  title: string
  description?: string
}

type Listener = (message: ToastMessage) => void

let nextId = 1
const listeners = new Set<Listener>()

type Detail = string | { description?: string }

function emit(kind: ToastKind, title: string, detail?: Detail): void {
  const description = typeof detail === "string" ? detail : detail?.description
  const message: ToastMessage = { id: nextId++, kind, title, description }
  listeners.forEach((listener) => listener(message))
}

/** Usable from anywhere (query hooks, handlers): the <ToastHost> renders what is emitted. */
export const toast = {
  success: (title: string, detail?: Detail) => emit("success", title, detail),
  error: (title: string, detail?: Detail) => emit("error", title, detail),
  info: (title: string, detail?: Detail) => emit("info", title, detail),
}

export function subscribeToToasts(listener: Listener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}
