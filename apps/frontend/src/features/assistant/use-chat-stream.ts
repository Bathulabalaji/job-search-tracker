import { useQueryClient } from "@tanstack/react-query"
import { useCallback, useRef, useState } from "react"

import { cancelRun } from "@/api/chat"
import { ApiError, retryMessage, streamRequest } from "@/api/client"
import { queryKeys } from "@/api/keys"

export interface LiveTool {
  id: string
  name: string
  ok?: boolean
  summary?: string
}

export interface TurnError {
  message: string
  code: string
  retryAfterSeconds: number | null
  recoverable: boolean
}

/** The reply being streamed right now, before it is reloaded from the server. */
export interface LiveTurn {
  conversationId: number
  /** The question as typed; null when resuming an earlier reply. */
  userText: string | null
  text: string
  tools: LiveTool[]
  runId: string | null
  resumingRunId: string | null
  error: TurnError | null
  model: string | null
}

type Handler = (event: string, data: unknown) => void

function record(data: unknown): Record<string, unknown> {
  return typeof data === "object" && data !== null ? (data as Record<string, unknown>) : {}
}

function str(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined
}

/**
 * Sends a message (or resumes a failed reply) and exposes the reply as it streams.
 *
 * When the stream ends the conversation is refetched and the live turn is dropped, so the
 * persisted messages take over without a flicker.
 */
export function useChatStream() {
  const queryClient = useQueryClient()
  const [live, setLive] = useState<LiveTurn | null>(null)
  const controller = useRef<AbortController | null>(null)

  const run = useCallback(
    async (turn: LiveTurn, path: string, body: unknown): Promise<ApiError | null> => {
      setLive(turn)
      const abort = new AbortController()
      controller.current = abort
      const update = (fn: (t: LiveTurn) => LiveTurn) => setLive((t) => (t ? fn(t) : t))
      const onEvent: Handler = (event, raw) => {
        const data = record(raw)
        switch (event) {
          case "run_started":
            update((t) => ({ ...t, runId: str(data.run_id) ?? null }))
            break
          case "token":
            update((t) => ({ ...t, text: t.text + (str(data.delta) ?? "") }))
            break
          case "tool_start":
            update((t) => ({
              ...t,
              tools: [...t.tools, { id: str(data.id) ?? "", name: str(data.name) ?? "tool" }],
            }))
            break
          case "tool_end":
            update((t) => ({
              ...t,
              tools: t.tools.map((tool) =>
                tool.id === data.id
                  ? { ...tool, ok: data.ok === true, summary: str(data.summary) }
                  : tool,
              ),
            }))
            break
          case "model_switched":
            update((t) => ({ ...t, model: str(data.model) ?? null }))
            break
          case "error":
            update((t) => ({
              ...t,
              error: {
                message: str(data.message) ?? "Something went wrong.",
                code: str(data.code) ?? "error",
                retryAfterSeconds:
                  typeof data.retry_after_seconds === "number" ? data.retry_after_seconds : null,
                recoverable: data.recoverable === true,
              },
            }))
            break
        }
      }
      try {
        await streamRequest(path, body, onEvent, abort.signal)
      } catch (error) {
        if (abort.signal.aborted) {
          // Stopped by the user: the server has kept whatever was said.
        } else if (error instanceof ApiError && error.status !== 0) {
          setLive(null)
          return error
        } else {
          update((t) => ({
            ...t,
            error: {
              message: "Connection lost. Reloading the conversation…",
              code: "connection_lost",
              retryAfterSeconds: null,
              recoverable: false,
            },
          }))
        }
      } finally {
        controller.current = null
      }
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: queryKeys.chat.conversation(turn.conversationId),
        }),
        queryClient.invalidateQueries({ queryKey: queryKeys.chat.conversations }),
        queryClient.invalidateQueries({ queryKey: queryKeys.chat.config }),
      ])
      setLive(null)
      return null
    },
    [queryClient],
  )

  const send = useCallback(
    (conversationId: number, text: string) =>
      run(
        {
          conversationId,
          userText: text,
          text: "",
          tools: [],
          runId: null,
          resumingRunId: null,
          error: null,
          model: null,
        },
        `/chat/conversations/${conversationId}/messages`,
        { content: text, client_message_id: crypto.randomUUID() },
      ),
    [run],
  )

  const resume = useCallback(
    (conversationId: number, runId: string) =>
      run(
        {
          conversationId,
          userText: null,
          text: "",
          tools: [],
          runId,
          resumingRunId: runId,
          error: null,
          model: null,
        },
        `/chat/conversations/${conversationId}/runs/${runId}/resume`,
        undefined,
      ),
    [run],
  )

  const stop = useCallback(() => {
    const turn = live
    if (turn?.runId) {
      // Ask the server to stop: it keeps what was said and ends the stream cleanly.
      void cancelRun(turn.conversationId, turn.runId).catch(() => controller.current?.abort())
    } else {
      controller.current?.abort()
    }
  }, [live])

  return { live, send, resume, stop, busy: live !== null }
}

export function errorText(error: ApiError): string {
  return error.status === 429 ? retryMessage(error) : error.message
}
