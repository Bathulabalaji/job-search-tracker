import { fetch as expoFetch } from "expo/fetch";

import { API_BASE_URL } from "@/config/env";
import { createSseParser } from "@/lib/sse";
import {
  ApiError,
  baseHeaders,
  errorFromResponse,
  reportSessionProblems,
} from "./client";

/** Waking a sleeping free-tier server can take most of a minute. */
const CONNECT_TIMEOUT_MS = 75_000;

/**
 * POST that answers with server-sent events. React Native's own fetch cannot read a body
 * while it streams; `expo/fetch` can. Errors before the stream starts throw an ApiError.
 */
export async function streamRequest(
  path: string,
  body: unknown,
  onEvent: (event: string, data: unknown) => void,
  signal?: AbortSignal,
): Promise<void> {
  const headers = {
    ...baseHeaders(),
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  const connect = new AbortController();
  const timer = setTimeout(() => connect.abort(), CONNECT_TIMEOUT_MS);
  const forwardAbort = () => connect.abort();
  signal?.addEventListener("abort", forwardAbort);
  try {
    let response: Awaited<ReturnType<typeof expoFetch>>;
    try {
      response = await expoFetch(`${API_BASE_URL}${path}`, {
        method: "POST",
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: connect.signal,
      });
    } catch (error) {
      if (signal?.aborted) throw error;
      throw new ApiError(
        0,
        "Can't reach the server. Check your connection and try again.",
      );
    } finally {
      clearTimeout(timer);
    }
    if (!response.ok) {
      const error = await errorFromResponse(response as unknown as Response);
      reportSessionProblems(error, path);
      throw error;
    }
    if (!response.body)
      throw new ApiError(0, "The server sent an empty response.");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    const feed = createSseParser((event, data) => {
      let parsed: unknown = data;
      try {
        parsed = JSON.parse(data) as unknown;
      } catch {
        // not JSON: pass the raw text through
      }
      onEvent(event, parsed);
    });
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      feed(decoder.decode(value, { stream: true }));
    }
  } finally {
    signal?.removeEventListener("abort", forwardAbort);
  }
}
