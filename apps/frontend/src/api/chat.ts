import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { request } from "./client"
import { queryKeys } from "./keys"

export interface ChatConfig {
  enabled: boolean
  messages_per_day: { limit: number; used: number }
  max_message_chars: number
  suggestions: string[]
  job_search?: boolean
  searches_per_day?: { limit: number; used: number } | null
}

/** A job posting found by the assistant's search_jobs tool, shown as a card. */
export interface JobCardData {
  type: "job"
  id: number
  title: string
  company: string
  location: string | null
  work_mode: string | null
  source_site: string
  provider: string
  apply_url: string
  posted_at: string | null
  salary_text: string | null
  active_status: "active" | "inactive" | "unknown" | string
  active_checked_at: string | null
  tracked_opportunity_id: number | null
}

export type ChatAttachment = JobCardData

export interface ChatConversation {
  id: number
  title: string
  status: "active" | "archived"
  last_message_at: string
  created_at: string
}

export interface ChatToolCall {
  name: string
  ok: boolean | null
  summary: string | null
}

export interface ChatMessage {
  id: number
  seq: number
  role: "user" | "assistant"
  content: string
  tool_calls: ChatToolCall[] | null
  attachments?: ChatAttachment[] | null
  status: "complete" | "awaiting" | "failed" | "cancelled"
  error_code: string | null
  model: string | null
  run_id: string | null
  created_at: string
}

export interface ActionField {
  name: string
  label: string
  value: unknown
  editable: boolean
  type: "text" | "date" | "datetime" | "select" | "number"
  options: string[] | null
}

/** A change the assistant proposed. Nothing happens until it is confirmed. */
export interface PendingAction {
  id: string
  run_id: string
  tool: string
  title: string
  summary: string
  fields: ActionField[]
  status: "pending" | "confirmed" | "rejected" | "expired" | "executed" | "failed"
  expires_at: string
  created_at: string | null
  result_summary: string | null
  error: string | null
  warning: string | null
}

export interface ChatRun {
  id: string
  status: "running" | "awaiting_confirmation" | "completed" | "failed" | "cancelled"
  error_code: string | null
  model_switches: number
  started_at: string
  finished_at: string | null
  resumable: boolean
}

export interface ConversationDetail {
  conversation: ChatConversation
  messages: ChatMessage[]
  last_run: ChatRun | null
  pending_action: PendingAction | null
}

export function useChatConfig() {
  return useQuery({
    queryKey: queryKeys.chat.config,
    queryFn: () => request<ChatConfig>("/chat/config"),
    staleTime: 60_000,
  })
}

export function useConversations() {
  return useQuery({
    queryKey: queryKeys.chat.conversations,
    queryFn: () => request<ChatConversation[]>("/chat/conversations", { params: { limit: 50 } }),
  })
}

export function useConversation(id: number | null) {
  return useQuery({
    queryKey: queryKeys.chat.conversation(id ?? 0),
    queryFn: () => request<ConversationDetail>(`/chat/conversations/${id}`),
    enabled: id !== null,
  })
}

export function useCreateConversation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () =>
      request<ChatConversation>("/chat/conversations", { method: "POST", body: {} }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.chat.conversations }),
  })
}

export function useRenameConversation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, title }: { id: number; title: string }) =>
      request<ChatConversation>(`/chat/conversations/${id}`, { method: "PATCH", body: { title } }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.chat.all }),
  })
}

export function useDeleteConversation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => request<void>(`/chat/conversations/${id}`, { method: "DELETE" }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.chat.conversations }),
  })
}

export function cancelRun(conversationId: number, runId: string): Promise<void> {
  return request<void>(`/chat/conversations/${conversationId}/runs/${runId}/cancel`, {
    method: "POST",
  })
}
