import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RotateCw,
  Search,
  Sparkles,
  XCircle,
} from "lucide-react"

import type { ChatMessage } from "@/api/chat"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { AssistantMarkdown } from "./markdown"
import type { LiveTool, TurnError } from "./use-chat-stream"

const TOOL_LABELS: Record<string, string> = {
  get_today: "Today's plan",
  get_pipeline_summary: "Pipeline summary",
  list_opportunities: "Opportunities",
  get_opportunity: "Opportunity details",
  list_followups: "Follow-ups",
  get_weekly_analytics: "Weekly analytics",
  list_contacts: "Contacts",
  list_prep_items: "Prep topics",
  list_resumes: "Resumes",
  move_opportunity: "Move stage",
  add_followup: "Add follow-up",
  mark_followup: "Update follow-up",
  log_interaction: "Log interaction",
  set_next_action: "Set next action",
  create_opportunity: "Add opportunity",
}

export function ToolChips({
  tools,
}: {
  tools: (LiveTool | { name: string; ok?: boolean | null; summary?: string | null })[]
}) {
  if (!tools.length) return null
  return (
    <ul className="mb-2 flex flex-wrap gap-1.5" aria-label="Looked up">
      {tools.map((tool, index) => {
        const running = tool.ok === undefined
        const Icon = running ? Loader2 : tool.ok ? CheckCircle2 : XCircle
        return (
          <li
            key={`${tool.name}-${index}`}
            className="inline-flex items-center gap-1 rounded-full border bg-muted/50 px-2 py-0.5 text-xs text-muted-foreground"
          >
            <Icon
              className={cn(
                "size-3",
                running && "animate-spin",
                tool.ok === false && "text-destructive",
              )}
              aria-hidden
            />
            <span>{TOOL_LABELS[tool.name] ?? tool.name}</span>
            {tool.summary ? (
              <span className="text-muted-foreground/80">· {tool.summary}</span>
            ) : null}
          </li>
        )
      })}
    </ul>
  )
}

export function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm text-primary-foreground sm:max-w-[75%]">
        {text}
      </div>
    </div>
  )
}

interface AssistantBubbleProps {
  text: string
  tools: Parameters<typeof ToolChips>[0]["tools"]
  streaming?: boolean
  status?: ChatMessage["status"]
  error?: TurnError | null
  onRetry?: () => void
}

export function AssistantBubble({
  text,
  tools,
  streaming,
  status,
  error,
  onRetry,
}: AssistantBubbleProps) {
  const failed = status === "failed" || Boolean(error)
  return (
    <div className="flex gap-3">
      <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Sparkles className="size-3.5" aria-hidden />
      </div>
      <div className="min-w-0 flex-1 text-sm leading-relaxed">
        <ToolChips tools={tools} />
        {text ? <AssistantMarkdown text={text} /> : null}
        {streaming && !text && !error ? (
          <p className="flex items-center gap-2 text-muted-foreground">
            <Search className="size-3.5 animate-pulse" aria-hidden /> Thinking…
          </p>
        ) : null}
        {status === "cancelled" ? (
          <p className="mt-1 text-xs text-muted-foreground">Stopped.</p>
        ) : null}
        {error ? <ErrorNote error={error} onRetry={onRetry} /> : null}
        {failed && !error && onRetry ? (
          <Button size="sm" variant="outline" className="mt-2" onClick={onRetry}>
            <RotateCw /> Retry
          </Button>
        ) : null}
      </div>
    </div>
  )
}

function ErrorNote({ error, onRetry }: { error: TurnError; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="mt-2 flex flex-wrap items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm"
    >
      <AlertTriangle className="size-4 shrink-0 text-destructive" aria-hidden />
      <span className="min-w-0 flex-1">{error.message}</span>
      {error.recoverable && onRetry ? (
        <Button size="sm" variant="outline" onClick={onRetry}>
          <RotateCw /> Retry
        </Button>
      ) : null}
    </div>
  )
}
