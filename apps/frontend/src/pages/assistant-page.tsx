import { History, MessageSquarePlus, SendHorizontal, Sparkles, Square, Trash2 } from "lucide-react"
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react"
import { useSearchParams } from "react-router-dom"
import { toast } from "sonner"

import {
  useChatConfig,
  useConversation,
  useConversations,
  useCreateConversation,
  useDeleteConversation,
  type ChatConversation,
} from "@/api/chat"
import { ConfirmDeleteDialog } from "@/components/common/confirm-delete-dialog"
import { EmptyState } from "@/components/common/empty-state"
import { ErrorState } from "@/components/common/error-state"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { ConfirmationCard } from "@/features/assistant/confirmation-card"
import { AssistantBubble, UserBubble } from "@/features/assistant/message-views"
import { errorText, useChatStream } from "@/features/assistant/use-chat-stream"
import { cn } from "@/lib/utils"

export function AssistantPage() {
  const config = useChatConfig()
  const [params, setParams] = useSearchParams()
  const selected = Number(params.get("c")) || null
  const [historyOpen, setHistoryOpen] = useState(false)
  // Bumped when the user switches chats, so the panel starts fresh. Not changed when the first
  // message creates a conversation, which would unmount the reply while it streams.
  const [panelKey, setPanelKey] = useState(0)

  const select = (id: number | null) => {
    setParams(id ? { c: String(id) } : {}, { replace: false })
    setPanelKey((k) => k + 1)
    setHistoryOpen(false)
  }

  if (config.isPending) return <Skeleton className="m-6 h-40" />
  if (config.isError) {
    return (
      <div className="p-6">
        <ErrorState message={config.error.message} onRetry={() => void config.refetch()} />
      </div>
    )
  }
  if (!config.data.enabled) {
    return (
      <div className="p-6">
        <EmptyState
          icon={Sparkles}
          title="The assistant isn't switched on"
          description="It needs an AI provider key on the server (GROQ_API_KEY or GOOGLE_AI_API_KEY)."
        />
      </div>
    )
  }

  const list = <ConversationList selected={selected} onSelect={select} />
  return (
    // The layout gives this page the full height below the top bar (see AppLayout).
    <div className="flex h-[calc(100dvh-3.5rem-env(safe-area-inset-top))] min-h-0">
      <aside className="hidden w-64 shrink-0 flex-col border-r lg:flex">{list}</aside>
      <Sheet open={historyOpen} onOpenChange={setHistoryOpen}>
        <SheetContent side="left" className="w-72 p-0">
          <SheetHeader className="sr-only">
            <SheetTitle>Conversations</SheetTitle>
          </SheetHeader>
          {list}
        </SheetContent>
      </Sheet>
      <ChatPanel
        key={panelKey}
        conversationId={selected}
        suggestions={config.data.suggestions}
        maxChars={config.data.max_message_chars}
        quota={config.data.messages_per_day}
        onConversationCreated={(id) => setParams({ c: String(id) }, { replace: true })}
        onOpenHistory={() => setHistoryOpen(true)}
        onNewChat={() => select(null)}
      />
    </div>
  )
}

function ConversationList({
  selected,
  onSelect,
}: {
  selected: number | null
  onSelect: (id: number | null) => void
}) {
  const conversations = useConversations()
  const remove = useDeleteConversation()
  const [pendingDelete, setPendingDelete] = useState<ChatConversation | null>(null)

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="p-3">
        <Button variant="outline" className="w-full justify-start" onClick={() => onSelect(null)}>
          <MessageSquarePlus /> New chat
        </Button>
      </div>
      <nav aria-label="Conversations" className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {conversations.isPending ? (
          <div className="space-y-2 px-1">
            <Skeleton className="h-8" />
            <Skeleton className="h-8" />
          </div>
        ) : null}
        {conversations.data?.length === 0 ? (
          <p className="px-2 py-4 text-sm text-muted-foreground">No conversations yet.</p>
        ) : null}
        <ul className="space-y-0.5">
          {conversations.data?.map((c) => (
            <li key={c.id} className="group relative">
              <button
                type="button"
                onClick={() => onSelect(c.id)}
                aria-current={c.id === selected ? "page" : undefined}
                className={cn(
                  "w-full truncate rounded-md px-3 py-2 pr-9 text-left text-sm hover:bg-muted",
                  c.id === selected && "bg-muted font-medium",
                )}
              >
                {c.title}
              </button>
              <button
                type="button"
                aria-label={`Delete ${c.title}`}
                onClick={() => setPendingDelete(c)}
                className="absolute top-1/2 right-1.5 -translate-y-1/2 rounded p-1 text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-destructive focus-visible:opacity-100"
              >
                <Trash2 className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      </nav>
      <ConfirmDeleteDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => !open && setPendingDelete(null)}
        title="Delete this conversation?"
        description={`"${pendingDelete?.title ?? ""}" and its messages will be removed.`}
        pending={remove.isPending}
        onConfirm={() => {
          if (!pendingDelete) return
          remove.mutate(pendingDelete.id, {
            onSuccess: () => {
              if (pendingDelete.id === selected) onSelect(null)
              setPendingDelete(null)
            },
            onError: (e) => toast.error("Could not delete", { description: e.message }),
          })
        }}
      />
    </div>
  )
}

interface ChatPanelProps {
  conversationId: number | null
  suggestions: string[]
  maxChars: number
  quota: { limit: number; used: number }
  onConversationCreated: (id: number) => void
  onOpenHistory: () => void
  onNewChat: () => void
}

function ChatPanel({
  conversationId,
  suggestions,
  maxChars,
  quota,
  onConversationCreated,
  onOpenHistory,
  onNewChat,
}: ChatPanelProps) {
  const detail = useConversation(conversationId)
  const create = useCreateConversation()
  const { live, send, resume, decide, stop, busy } = useChatStream()
  const [draft, setDraft] = useState("")
  // Why the last message could not be sent (quota, busy...). Shown above the composer.
  const [notice, setNotice] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  const messages = (detail.data?.messages ?? []).filter(
    (m) => !(live?.resumingRunId && m.role === "assistant" && m.run_id === live.resumingRunId),
  )
  const lastRun = detail.data?.last_run ?? null
  const pending = detail.data?.pending_action ?? null
  const cardUp = pending !== null && pending.status === "pending" && !live

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" })
  }, [messages.length, live?.text, live?.tools.length, live?.error])

  const submit = async (text: string) => {
    const content = text.trim()
    if (!content || busy) return
    setDraft("")
    setNotice(null)
    let id = conversationId
    if (id === null) {
      try {
        id = (await create.mutateAsync()).id
      } catch (e) {
        setDraft(content)
        setNotice((e as Error).message)
        return
      }
      onConversationCreated(id)
    }
    const error = await send(id, content)
    if (error) {
      setDraft(content)
      setNotice(errorText(error))
    }
  }

  const retry = async (runId: string) => {
    if (conversationId === null) return
    setNotice(null)
    const error = await resume(conversationId, runId)
    if (error) setNotice(errorText(error))
  }

  const answerCard = async (
    decision: "confirm" | "reject",
    edits: Record<string, unknown> = {},
  ) => {
    if (conversationId === null || !pending) return
    setNotice(null)
    const error = await decide(conversationId, pending.id, decision, edits)
    if (error) setNotice(errorText(error))
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    void submit(draft)
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      void submit(draft)
    }
  }

  const empty = messages.length === 0 && !live
  return (
    <section className="flex min-w-0 flex-1 flex-col" aria-label="Assistant">
      <div className="flex h-12 shrink-0 items-center gap-2 border-b px-3 sm:px-4">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={onOpenHistory}
          aria-label="Conversations"
        >
          <History />
        </Button>
        <h1 className="min-w-0 flex-1 truncate text-sm font-medium">
          {detail.data?.conversation.title ?? "Assistant"}
        </h1>
        <span className="hidden text-xs text-muted-foreground sm:inline">
          {quota.used}/{quota.limit} today
        </span>
        <Button variant="ghost" size="sm" onClick={onNewChat} aria-label="New chat">
          <MessageSquarePlus />
          <span className="hidden sm:inline">New</span>
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-3xl flex-col gap-5 px-4 py-6">
          {detail.isLoading ? <Skeleton className="h-24" /> : null}
          {detail.isError ? (
            <ErrorState message={detail.error.message} onRetry={() => void detail.refetch()} />
          ) : null}
          {empty && !detail.isLoading ? (
            <div className="flex flex-col items-center gap-4 py-10 text-center">
              <div className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                <Sparkles className="size-6" aria-hidden />
              </div>
              <div className="space-y-1">
                <h2 className="text-lg font-semibold">Ask about your job search</h2>
                <p className="max-w-md text-sm text-muted-foreground">
                  I can look up your pipeline, follow-ups, interviews, contacts, prep and weekly
                  progress. I can't change anything yet.
                </p>
              </div>
              <div className="flex max-w-xl flex-wrap justify-center gap-2">
                {suggestions.map((s) => (
                  <Button
                    key={s}
                    variant="outline"
                    size="sm"
                    className="rounded-full"
                    onClick={() => void submit(s)}
                  >
                    {s}
                  </Button>
                ))}
              </div>
            </div>
          ) : null}

          {messages.map((m, index) =>
            m.role === "user" ? (
              <UserBubble key={m.id} text={m.content} />
            ) : (
              <AssistantBubble
                key={m.id}
                text={m.content}
                tools={m.tool_calls ?? []}
                status={m.status}
                onRetry={
                  m.status === "failed" &&
                  index === messages.length - 1 &&
                  lastRun?.resumable &&
                  lastRun.id === m.run_id &&
                  !busy
                    ? () => void retry(lastRun.id)
                    : undefined
                }
              />
            ),
          )}

          {cardUp ? (
            <ConfirmationCard
              key={pending.id}
              action={pending}
              busy={busy}
              onConfirm={(edits) => void answerCard("confirm", edits)}
              onReject={() => void answerCard("reject")}
            />
          ) : null}

          {live?.userText ? <UserBubble text={live.userText} /> : null}
          {live ? (
            <AssistantBubble
              text={live.text}
              tools={live.tools}
              streaming
              error={live.error}
              onRetry={live.runId ? () => void retry(live.runId ?? "") : undefined}
            />
          ) : null}
          <div ref={endRef} />
        </div>
      </div>

      <form
        onSubmit={onSubmit}
        className="shrink-0 border-t bg-background p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:p-4"
      >
        {notice ? (
          <p role="alert" className="mx-auto mb-2 max-w-3xl text-sm text-destructive">
            {notice}
          </p>
        ) : null}
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={
              cardUp
                ? "Confirm or decline the change above first…"
                : "Ask about your pipeline, follow-ups, interviews…"
            }
            aria-label="Message"
            rows={1}
            maxLength={maxChars}
            className="max-h-40 min-h-10 resize-none"
          />
          {busy ? (
            <Button type="button" variant="outline" size="icon" onClick={stop} aria-label="Stop">
              <Square />
            </Button>
          ) : (
            <Button type="submit" size="icon" disabled={!draft.trim() || cardUp} aria-label="Send">
              <SendHorizontal />
            </Button>
          )}
        </div>
        {draft.length > maxChars * 0.8 ? (
          <p className={cn("mx-auto mt-1 max-w-3xl text-right text-xs text-muted-foreground")}>
            {draft.length}/{maxChars}
          </p>
        ) : null}
      </form>
    </section>
  )
}
